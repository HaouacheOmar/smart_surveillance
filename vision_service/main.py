"""Vision service: pulls camera/zone config from Django, runs one worker thread per camera,
pushes metrics back to Django and serves annotated MJPEG streams."""
import asyncio
import hmac
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

import cv2
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from model_loader import load_pose_model
from tracker import CameraAnalyzer, anonymize

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("vision")

SERVICE_TOKEN = os.environ["SERVICE_TOKEN"]
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
TARGET_FPS = float(os.environ.get("TARGET_FPS", "5"))
PUSH_INTERVAL = float(os.environ.get("PUSH_INTERVAL", "1"))
CONFIG_REFRESH = float(os.environ.get("CONFIG_REFRESH", "15"))
STREAM_WIDTH = int(os.environ.get("STREAM_WIDTH", "1280"))  # MJPEG is downscaled; analysis runs on full frames
CAPTURE_PARAMS = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000]

backend = httpx.Client(base_url=BACKEND_URL, headers={"X-Service-Token": SERVICE_TOKEN}, timeout=5)
workers: dict[int, "CameraWorker"] = {}


class CameraWorker(threading.Thread):
    def __init__(self, config):
        super().__init__(daemon=True, name=f"camera-{config['id']}")
        self.config = config
        self.stopped = threading.Event()
        self.jpeg: bytes | None = None

    def run(self):
        analyzer = CameraAnalyzer(self.config["hallways"])
        while not self.stopped.is_set():
            cap = cv2.VideoCapture(self.config["rtsp_url"], cv2.CAP_FFMPEG, CAPTURE_PARAMS)
            if cap.isOpened():
                self._loop(cap, analyzer)
            else:
                log.warning("camera %s unreachable, retrying", self.config["id"])
            cap.release()
            self.stopped.wait(3)

    def _loop(self, cap, analyzer):
        # Decoding runs on its own thread and analysis always takes the newest frame: decoding every
        # 25-30 fps H.264 frame on the analysis thread (grab() decodes too) was what capped throughput.
        latest, fresh = [None], threading.Event()

        def read():
            while not self.stopped.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                latest[0] = frame
                fresh.set()
            fresh.set()  # wake the analysis loop so it sees the reader ended

        reader = threading.Thread(target=read, daemon=True, name=f"{self.name}-reader")
        reader.start()
        next_push = 0.0
        while not self.stopped.is_set() and reader.is_alive():
            if not fresh.wait(timeout=1):
                continue
            fresh.clear()
            frame, latest[0] = latest[0], None
            if frame is None:
                continue
            now = time.monotonic()
            annotated, metrics = analyzer.process(frame)
            h, w = annotated.shape[:2]
            if w > STREAM_WIDTH:
                annotated = cv2.resize(annotated, (STREAM_WIDTH, h * STREAM_WIDTH // w), interpolation=cv2.INTER_AREA)
            self.jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()
            if now >= next_push:
                next_push = now + PUSH_INTERVAL
                try:
                    backend.post("/api/internal/ingest/", json={"camera_id": self.config["id"], **metrics}).raise_for_status()
                except httpx.HTTPError as exc:
                    log.warning("metrics push failed for camera %s: %s", self.config["id"], exc)
            self.stopped.wait(max(0.0, 1 / TARGET_FPS - (time.monotonic() - now)))  # cap at TARGET_FPS
        reader.join()  # the reader owns cap.read(); run() releases cap only after it exits


def sync_workers():
    response = backend.get("/api/internal/vision-config/")
    response.raise_for_status()
    configs = {c["id"]: c for c in response.json()}
    for cid, worker in list(workers.items()):
        if configs.get(cid) != worker.config:  # removed or zones/URL changed -> restart
            worker.stopped.set()
            del workers[cid]
    for cid, config in configs.items():
        if cid not in workers:
            workers[cid] = CameraWorker(config)
            workers[cid].start()


def sync_loop(stop):
    while not stop.is_set():
        try:
            sync_workers()
        except httpx.HTTPError as exc:
            log.warning("config sync failed: %s", exc)
        stop.wait(CONFIG_REFRESH)


@asynccontextmanager
async def lifespan(app):
    load_pose_model()
    stop = threading.Event()
    threading.Thread(target=sync_loop, args=(stop,), daemon=True, name="config-sync").start()
    yield
    stop.set()
    for worker in workers.values():
        worker.stopped.set()


app = FastAPI(title="Vision Service", lifespan=lifespan)


def require_service_token(x_service_token: str = Header("")):
    if not hmac.compare_digest(x_service_token, SERVICE_TOKEN):
        raise HTTPException(403)


class SnapshotRequest(BaseModel):
    rtsp_url: str


@app.get("/health")
def health():
    return {"status": "ok", "cameras": {cid: w.jpeg is not None for cid, w in workers.items()}}


@app.post("/snapshot", dependencies=[Depends(require_service_token)])
def snapshot(body: SnapshotRequest):
    if not body.rtsp_url.startswith(("rtsp://", "rtsps://")):
        raise HTTPException(422, "rtsp:// URL required")
    cap = cv2.VideoCapture(body.rtsp_url, cv2.CAP_FFMPEG, CAPTURE_PARAMS)
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise HTTPException(502, "camera unreachable")
    return Response(cv2.imencode(".jpg", anonymize(frame))[1].tobytes(), media_type="image/jpeg")


@app.get("/streams/{camera_id}")
async def stream(camera_id: int):
    """Annotated MJPEG. Not exposed publicly: nginx gates it behind Django auth (auth_request)."""
    if camera_id not in workers:
        raise HTTPException(404)

    async def frames():
        sent = None
        while worker := workers.get(camera_id):
            jpeg = worker.jpeg
            if jpeg is not None and jpeg is not sent:  # each new frame exactly once, as soon as it exists
                sent = jpeg
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")
