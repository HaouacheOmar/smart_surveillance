"""Zone counting, face anonymisation and overlay drawing. Zones use normalised [0..1] coordinates."""
import os
import time

import cv2
import numpy as np
import torch

from model_loader import inference_lock, load_pose_model, new_tracker

FACE_KEYPOINTS = 5  # COCO pose: nose, left/right eye, left/right ear
KEYPOINT_CONF = 0.5
DETECTION_CONF = float(os.environ.get("DETECTION_CONF", "0.4"))
# BGR mirror of the UI semantic tokens (docs/SYSTEM_DESIGN.md §3.2, frontend/src/styles.css): change both together.
HALLWAY_COLOR = (253, 139, 61)   # --zone-hallway #3d8bfd
FREE_COLOR = (113, 191, 47)      # --state-free   #2fbf71
BUSY_COLOR = (79, 86, 240)       # --state-busy   #f0564f
CLOSED_COLOR = (150, 136, 125)   # --state-closed #7d8896
STAFF_COLOR = (240, 115, 182)    # --zone-staff   #b673f0
PERSON_COLOR = (63, 210, 255)    # --person       #ffd23f
CLOSE_AFTER_SECONDS = float(os.environ.get("CLOSE_AFTER_SECONDS", "5"))
ZONE_FILL_ALPHA = 0.25
EMBED_SIZE, IMAGENET_MEAN, IMAGENET_STD = 224, (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)


def to_px(polygon, w, h):
    return np.array([[x * w, y * h] for x, y in polygon], np.float32)


def inside(point, polygon_px):
    return cv2.pointPolygonTest(polygon_px, (float(point[0]), float(point[1])), False) >= 0


def zone_metrics(feet, hallways, w, h):
    """feet: (x, y) ground-contact points of tracked people, in pixels.
    People standing in a checkout's staff_polygon are cashiers: they open that checkout and are
    excluded from hallway counts and from checkout occupancy. Returns metrics + per-person staff flags."""
    staff_zones = {co["id"]: to_px(co["staff_polygon"], w, h)
                   for hw in hallways for co in hw["checkouts"] if co.get("staff_polygon")}
    is_staff = [any(inside(p, z) for z in staff_zones.values()) for p in feet]
    customers = [p for p, staff in zip(feet, is_staff) if not staff]
    staff = [p for p, s in zip(feet, is_staff) if s]

    counts, occupied, is_open = {}, {}, {}
    for hallway in hallways:
        poly = to_px(hallway["polygon"], w, h)
        counts[hallway["id"]] = sum(inside(p, poly) for p in customers)
        for checkout in hallway["checkouts"]:
            cpoly = to_px(checkout["polygon"], w, h)
            occupied[checkout["id"]] = any(inside(p, cpoly) for p in customers)
            zone = staff_zones.get(checkout["id"])
            is_open[checkout["id"]] = zone is None or any(inside(p, zone) for p in staff)
    return {"hallways": counts, "checkouts": occupied, "open": is_open}, is_staff


def face_box(box, keypoints):
    """Square around visible face keypoints; falls back to the top of the body box (privacy first)."""
    x1, y1, x2, y2 = box
    face = keypoints[:FACE_KEYPOINTS]
    visible = face[face[:, 2] > KEYPOINT_CONF][:, :2]
    if len(visible) >= 2:
        cx, cy = visible.mean(axis=0)
        size = max(np.ptp(visible, axis=0).max() * 2.2, (x2 - x1) * 0.3)
    else:
        cx, cy, size = (x1 + x2) / 2, y1 + (y2 - y1) * 0.1, (x2 - x1) * 0.6
    return cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2


def blur(frame, x1, y1, x2, y2):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = max(0, int(x1)), max(0, int(y1)), min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 2 or y2 - y1 < 2:
        return
    k = max(3, (x2 - x1) // 3 | 1)
    frame[y1:y2, x1:x2] = cv2.GaussianBlur(frame[y1:y2, x1:x2], (k, k), 0)


def stroke(w):
    """Line thickness that stays visible once the frame is scaled down in the browser."""
    return max(2, w // 400)


def draw_corners(frame, box, color):
    x1, y1, x2, y2 = map(int, box)
    length, t = max(4, int(min(x2 - x1, y2 - y1) * 0.2)), stroke(frame.shape[1])
    for x, y, dx, dy in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv2.line(frame, (x, y), (x + dx * length, y), color, t)
        cv2.line(frame, (x, y), (x, y + dy * length), color, t)


def draw_zones(frame, zones):
    """zones: [(polygon, color, label)], later entries on top. Translucent fill + outline + label badge."""
    h, w = frame.shape[:2]
    polys = [(to_px(p, w, h).astype(np.int32), color, label) for p, color, label in zones]
    overlay = frame.copy()
    for pts, color, _ in polys:
        cv2.fillPoly(overlay, [pts], color)
    cv2.addWeighted(overlay, ZONE_FILL_ALPHA, frame, 1 - ZONE_FILL_ALPHA, 0, dst=frame)

    t, scale = stroke(w), w / 1600
    for pts, color, label in polys:
        cv2.polylines(frame, [pts], True, color, t, cv2.LINE_AA)
        (tw, th), base = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, t)
        x, y = (int(v) for v in pts.min(axis=0))
        cv2.rectangle(frame, (x, y), (x + tw + 2 * t, y + th + base + 2 * t), color, -1)
        cv2.putText(frame, label, (x + t, y + th + t), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), t, cv2.LINE_AA)


def detect(frame):
    with inference_lock:
        result = load_pose_model()(frame, conf=DETECTION_CONF, quantize=16, verbose=False)[0]  # FP16 on GPU, FP32 on CPU
    boxes = result.boxes.xyxy.cpu().numpy()
    confs = result.boxes.conf.cpu().numpy()
    kpts = result.keypoints.data.cpu().numpy() if result.keypoints is not None else np.zeros((len(boxes), 17, 3))
    return boxes, confs, kpts


def embed_people(embedder, frame, boxes):
    """DeepSORT appearance features. Same math as deep_sort_realtime's MobileNetv2_Embedder.predict
    (BGR->RGB, 224x224, ImageNet norm) but one batched GPU pass instead of per-crop CPU torchvision (~50x slower)."""
    if not len(boxes):
        return []
    h, w = frame.shape[:2]
    crops = []
    for x1, y1, x2, y2 in boxes:
        l, t = min(max(0, int(x1)), w - 1), min(max(0, int(y1)), h - 1)
        crops.append(cv2.resize(frame[t:max(t + 1, min(h, int(y2))), l:max(l + 1, min(w, int(x2)))], (EMBED_SIZE, EMBED_SIZE)))
    device = next(embedder.model.parameters()).device
    batch = torch.from_numpy(np.stack(crops)).to(device).flip(-1).permute(0, 3, 1, 2).float().div_(255)
    batch = (batch - torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)) / torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
    with torch.inference_mode():
        return list(embedder.model(batch.half() if embedder.half else batch).float().cpu().numpy())


def anonymize(frame):
    boxes, _, kpts = detect(frame)
    for box, k in zip(boxes, kpts):
        blur(frame, *face_box(box, k))
    return frame


class CameraAnalyzer:
    def __init__(self, hallways):
        self.hallways = hallways
        self.tracker = new_tracker()
        self.staff_seen = {}  # checkout id -> last time a cashier was in its staff zone

    def process(self, frame):
        """Returns (annotated face-blurred frame, metrics dict). Mutates `frame`."""
        h, w = frame.shape[:2]
        boxes, confs, kpts = detect(frame)
        tracks = self.tracker.update_tracks(
            [([x1, y1, x2 - x1, y2 - y1], c, 0) for (x1, y1, x2, y2), c in zip(boxes, confs)],
            embeds=embed_people(self.tracker.embedder, frame, boxes),
        )
        # Blur every raw detection (not only confirmed tracks) after the tracker has embedded the crops.
        for box, k in zip(boxes, kpts):
            blur(frame, *face_box(box, k))
        people = [t.to_ltrb() for t in tracks if t.is_confirmed() and t.time_since_update == 0]
        metrics, is_staff = zone_metrics([((x1 + x2) / 2, y2) for x1, _, x2, y2 in people], self.hallways, w, h)
        # A cashier lost for a few frames (occlusion, tracking gap) must not flash "closed" on the LCD.
        now = time.monotonic()
        for cid, staffed in metrics["open"].items():
            if staffed:
                self.staff_seen[cid] = now
            metrics["open"][cid] = staffed or now - self.staff_seen.get(cid, -CLOSE_AFTER_SECONDS) < CLOSE_AFTER_SECONDS

        zones = [(hw["polygon"], HALLWAY_COLOR, f"{hw['name']}: {metrics['hallways'][hw['id']]}") for hw in self.hallways]
        for co in (co for hw in self.hallways for co in hw["checkouts"]):
            if not metrics["open"][co["id"]]:
                zones.append((co["polygon"], CLOSED_COLOR, f"{co['name']} (fermee)"))
            else:
                zones.append((co["polygon"], BUSY_COLOR if metrics["checkouts"][co["id"]] else FREE_COLOR, co["name"]))
            if co.get("staff_polygon"):
                zones.append((co["staff_polygon"], STAFF_COLOR, "Caissier"))
        draw_zones(frame, zones)  # checkouts and staff zones drawn over their hallway
        for box, staff in zip(people, is_staff):
            draw_corners(frame, box, STAFF_COLOR if staff else PERSON_COLOR)
        return frame, metrics
