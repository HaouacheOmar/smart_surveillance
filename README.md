# Smart Surveillance

**Real-time queue and checkout monitoring from existing CCTV cameras.**

Smart Surveillance watches the hallways that lead to the checkouts of a store. It counts the people waiting, works out which checkouts are **free**, **busy** or **closed**, and shows it live on **LCD screens** for shoppers and on a **CCTV dashboard** for the supervisor. Faces are always blurred.

It needs no hardware per checkout and no POS integration. The existing cameras' RTSP streams are enough: an admin draws the zones once on a camera snapshot, and computer vision does the rest.

| Document | Contents |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Functional requirements (French) |
| [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | Original technical specification (French) |
| [docs/SCHEMA_DATABASE.md](docs/SCHEMA_DATABASE.md) | Database schema, indexes, write load |
| [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | Design system: tokens, components, motion, LCD and video-overlay rules |
| [PRODUCT.md](PRODUCT.md) | Users, context, positioning |

---

## Contents
1. [What the app does](#1-what-the-app-does)
2. [How detection works](#2-how-detection-works)
3. [Architecture](#3-architecture)
4. [Technical stack](#4-technical-stack)
5. [Project structure](#5-project-structure)
6. [API](#6-api)
7. [Security and privacy](#7-security-and-privacy)
8. [Configuration](#8-configuration)
9. [Running the app](#9-running-the-app)
10. [Testing with simulated cameras](#10-testing-with-simulated-cameras)
11. [Tests](#11-tests)
12. [Performance](#12-performance)
13. [Limits and roadmap](#13-limits-and-roadmap)

---

## 1. What the app does

### Users
| Who | Where | What they do |
|---|---|---|
| **Store supervisor** (operator) | Back-office screen | Watches the queues and decides when to open or close checkouts. Read-only access. |
| **Admin** | Same console | Adds cameras, maps zones, manages everything. Full access. |
| **Shoppers** | In front of the LCD screens, 2–8 m away | Read which checkout to go to. No login. |

### Features

**Authentication**
- A login page with JWT tokens stored only in **HttpOnly cookies** (access 10 min, refresh 24 h, rotated and blacklisted on logout).
- Two roles: `admin` (read and write) and `operator` (read-only). Superusers are admins.
- Login is rate-limited to 10 attempts per minute.

**Camera management** (*Caméras* page)
- Add or delete a camera: name, IP address, RTSP URL, and RTSP username and password.
- The password is **encrypted** in the database (Fernet) and never sent back by the API. URLs that embed credentials are rejected.
- Live **online / offline** status for each camera, from the vision service's heartbeat (offline after 15 s without one).
- Deleting a camera is confirmed inline and removes its zones.

**Interactive mapping** (*Cartographie* page)
- Takes a **face-blurred snapshot** from the camera.
- Three drawing tools, each in its own color:
  - **Couloir** (hallway): the queue area where waiting people are counted.
  - **Caisse (côté client)** (checkout, customer side): where a customer stands while being served.
  - **Zone caissier** (cashier zone): where the cashier stands. People there count as **staff**.
- Click to add points, **Enter** to save, **Esc** to clear, **Backspace** to remove the last point. Zones are stored as normalised polygons (0–1), so they survive resolution changes.
- A hallway can contain several checkouts, and each checkout can have one cashier zone.

**Supervision dashboard** (*Supervision* page)
- The live **annotated video** of every camera (MJPEG). It shows faces blurred, 4-corner boxes around people (yellow for customers, purple for staff), and colored zones: hallway blue, free checkout green, busy red, closed gray.
- A side panel per hallway: the people waiting (an animated counter) and each checkout's state (*Libre*, *Occupée* or *Fermée*), shown with a drawn shape and a label, never color alone.
- **Spotlight:** clicking a hallway or checkout dims the video everywhere except that zone, and opens an **inspector** (state, hallway, cashier zone, last change, camera).
- **Activité:** the latest state changes, from the occupancy history.
- A "maj il y a N s" freshness stamp that turns into *données périmées* when updates stop.

**Public LCD screen** (`/#/lcd`, no login)
- Large type for each hallway: the number of people waiting and each checkout's state, with **"→ Allez à la Caisse N"** pointing to the best free checkout.
- Updates are **pushed over a WebSocket** the moment something changes, with a full refresh every 10 s. Screens reconnect automatically with random jitter.
- Offline hallways show *Données indisponibles*, and a banner appears if the connection to the server is lost. A slow sub-pixel shift protects screens from burn-in.

**History**
- Every change of a hallway's count or of a checkout's state is written to `occupancylog`, which is used by the Activité panel and available through the API.

---

## 2. How detection works

The vision service runs one worker per camera:

1. **Read.** A reader thread decodes the RTSP stream continuously. The analysis thread always takes the **newest** frame, up to `TARGET_FPS` per second.
2. **Detect.** **YOLO26-pose** (Ultralytics) finds every person and 17 body keypoints. It runs on the GPU in FP16.
3. **Track.** **DeepSORT** follows each person across frames. Its appearance features (MobileNetV2) are computed in one batched GPU pass. Someone only counts after being tracked for 3 frames, which removes single-frame false detections.
4. **Anonymise.** Every detected face is blurred. The face is located from the pose keypoints (nose, eyes, ears); when it isn't visible, the head region is blurred instead.
5. **Locate.** Each tracked person is reduced to one point: the **middle of the bottom of the box**, their feet on the floor.
6. **Classify.**
   - A person whose feet are in a **cashier zone** is **staff**: never counted as waiting and never making a checkout busy.
   - **Hallway count** = the customers whose feet are inside the hallway polygon.
   - **Checkout busy** = at least one customer's feet are inside the checkout polygon.
   - **Checkout open** = someone is in its cashier zone. It only switches to **closed** after 5 s with nobody there, so a cashier hidden for a frame doesn't make it flash "closed". A checkout without a cashier zone is always considered open.
7. **Publish.** Every second the worker sends the counts and states to Django. Django writes only the rows that changed, records history, and pushes the new state to every LCD screen. The worker also encodes the annotated frame as JPEG for the dashboard stream.

Every 15 s the vision service fetches cameras and zones from Django, and restarts a camera's worker when its configuration changes. Editing a zone takes effect without any restart.

---

## 3. Architecture

```
                 Browser: admin console (React)          LCD screens (React, public)
                        │  HTTPS · HttpOnly JWT cookies        │  WebSocket /ws/display/
                        ▼                                       ▼
            ┌──────────────── nginx (frontend container) ────────────────┐
            │ /            → React SPA (static)                           │
            │ /api/*       → Django        /api/internal/* → 404 (blocked)│
            │ /ws/*        → Django Channels (WebSocket)                  │
            │ /stream/*    → vision service, only after auth_request      │
            └──────────────┬───────────────────────────────┬─────────────┘
                           ▼                               ▼
          ┌──── Django 6 + DRF + Channels (uvicorn, ASGI) ────┐      ┌─ FastAPI vision service (GPU) ─┐
          │ auth · cameras · zones · ingest · history · LCD   │◄─────│ pulls config every 15 s        │
          │ OpenAPI docs                                       │ 1 Hz │ pushes counts and states       │
          └──────┬───────────────────────────┬────────────────┘ ───► │ YOLO26-pose → DeepSORT → blur  │
                 ▼                           ▼               snapshot│ → zones → MJPEG                │
          PostgreSQL 17               Redis 8                         └──────────────▲─────────────────┘
          (data, history)             (WebSocket fan-out,                            │ RTSP
                                      rate-limit cache)                       IP cameras (or simulated)
```

- **Django is the only stateful service.** The vision service is stateless: it pulls its configuration and pushes results, so more vision nodes can be added.
- The **service token** (`SERVICE_TOKEN`) authenticates the two internal endpoints and the snapshot call between Django and the vision service.
- Redis fans WebSocket messages out across all backend workers and hosts. Each change is serialised once, whatever the number of screens.

---

## 4. Technical stack

### Backend: business logic and API
| Component | Version | Role |
|---|---|---|
| Python | 3.12 | Runtime |
| Django | 6.1.2 | Modular monolith (apps under `modules/`) |
| Django REST Framework | 3.18.3 | REST API (ViewSets) |
| djangorestframework-simplejwt | 5.5.1 | JWT in HttpOnly cookies, rotation and blacklist |
| Django Channels + channels-redis | 4.3.2 / 4.3.0 | WebSocket for the LCD screens |
| drf-spectacular | 0.30.0 | OpenAPI schema and Swagger UI |
| cryptography (Fernet) | 50.0.2 | Encrypting camera passwords |
| psycopg | 3.3.6 | PostgreSQL driver |
| httpx | 0.28.1 | HTTP client to the vision service |
| uvicorn | 0.54.0 | ASGI server (HTTP and WebSocket, 4 workers) |

### Vision service: computer vision
| Component | Version | Role |
|---|---|---|
| FastAPI + uvicorn | 0.162.0 / 0.54.0 | Internal API: snapshot, MJPEG streams, health |
| PyTorch + torchvision | 2.14.1, CUDA 13.0 | Inference on the NVIDIA GPU (CPU build also possible) |
| Ultralytics | 8.4.192 | **YOLO26n-pose**: person detection and 17 keypoints |
| deep-sort-realtime | 1.3.2 | **DeepSORT** multi-object tracking (MobileNetV2 appearance embedder) |
| OpenCV (headless) | 5.0 | RTSP decoding (FFmpeg), blur, drawing, JPEG encoding |
| NumPy | 2.5.4 | Geometry |

### Frontend
| Component | Version | Role |
|---|---|---|
| React | 19.3 | Single-page application (admin console and LCD screen) |
| Vite + @vitejs/plugin-react | 8.3 / 6.1 | Build and dev server (proxies `/api`, `/ws`, `/stream`) |
| Motion (`motion/react`) | 14.8 | Animations: rolling counters, state cross-fades, spotlight, toasts |
| lucide-react | 1.64 | SVG icons |
| Inter Variable + JetBrains Mono | via Fontsource | Fonts bundled locally, so offline LCD kiosks need no CDN |

### Infrastructure
| Component | Version | Role |
|---|---|---|
| Docker + Docker Compose | 29.x | One container per service; GPU through the NVIDIA runtime |
| PostgreSQL | 17 (alpine) | Database |
| Redis | 8 (alpine) | Channels layer and shared cache |
| nginx | 1.29 (alpine) | Static frontend, reverse proxy, WebSocket upgrade, `auth_request` on streams |
| MediaMTX | 1.x | RTSP server for the simulated cameras (testing only) |

---

## 5. Project structure

```
smart_surveillance/
├── manage.py
├── requirements.txt                 # backend Python dependencies (pinned)
├── .env.example                     # configuration template; copy to .env
├── PRODUCT.md                       # product context: users, positioning
│
├── config/                          # Django project
│   ├── settings.py                  # all settings from env vars; refuses to start in production without secrets
│   ├── urls.py                      # /api/* routes, /api/docs, /api/health
│   ├── asgi.py                      # HTTP + WebSocket routing (Channels)
│   └── wsgi.py
│
├── modules/                         # business modules (Django apps)
│   ├── authentication/              # User (roles), cookie JWT + CSRF, login/refresh/logout/me, service token
│   ├── cameras/                     # Camera model (encrypted password, RTSP URL), CRUD, snapshot
│   ├── monitoring/                  # Hallway, Checkout (+ cashier zone), OccupancyLog, ingest, LCD feed, WebSocket consumer
│   └── ai_bridge/services.py        # HTTP client to the vision service
│
├── vision_service/                  # FastAPI computer-vision service
│   ├── main.py                      # API, one worker per camera (reader thread + analysis), config sync, MJPEG
│   ├── model_loader.py              # YOLO26-pose and DeepSORT setup, thread settings
│   ├── tracker.py                   # detection, batched embeddings, blur, zone logic, overlay drawing
│   ├── test_tracker.py
│   └── requirements.txt
│
├── frontend/                        # React + Vite
│   ├── src/api.js                   # fetch wrapper: CSRF header, single-flight token refresh
│   ├── src/App.jsx                  # app shell, navigation, auth gate, Motion config
│   ├── src/components.jsx           # StatusShape/Badge, RollingNumber, Flash, LiveIndicator, ConfirmDelete, toasts
│   ├── src/styles.css               # design tokens and styles (docs/SYSTEM_DESIGN.md)
│   └── src/pages/                   # Login, Dashboard, Cameras, Mapping, Lcd
│
├── docker/                          # everything Docker
│   ├── docker-compose.yml           # db, redis, backend, vision (GPU), frontend
│   ├── docker-compose.sim.yml       # add-on: RTSP server + simulated cameras from video files
│   ├── backend.Dockerfile           # + backend.Dockerfile.dockerignore
│   ├── vision.Dockerfile            # + vision.Dockerfile.dockerignore (CUDA or CPU PyTorch)
│   ├── frontend.Dockerfile          # + frontend.Dockerfile.dockerignore (Vite build → nginx)
│   └── nginx.conf                   # SPA, /api, /ws, auth-gated /stream, /api/internal blocked
│
├── sim/                             # video files for the simulated cameras (git-ignored)
├── tests/test_api.py                # backend API tests
└── docs/                            # PRD, implementation spec, database schema, design system
```

---

## 6. API

Interactive documentation is at `GET /api/docs/` (Swagger, after login), and the schema at `GET /api/schema/`.

| Method | Path | Access | Description |
|---|---|---|---|
| GET | `/api/health/` | public | Health check |
| POST | `/api/auth/login/` | public, 10/min | `{username, password}` → sets the `access_token` (10 min), `refresh_token` (24 h) and `csrftoken` cookies |
| POST | `/api/auth/refresh/` | refresh cookie | Issues new tokens; the old refresh token is blacklisted |
| POST | `/api/auth/logout/` | — | Blacklists the refresh token and clears the cookies |
| GET | `/api/auth/me/` | user | Current user. Also used by nginx to authorise video streams |
| GET, POST | `/api/cameras/` | read: user · write: admin | List cameras / create one (`name, ip_address, rtsp_url, username, password`) |
| GET, PUT, PATCH, DELETE | `/api/cameras/{id}/` | read: user · write: admin | Camera details (`password` is write-only; `online`, `last_seen_at` are read-only) |
| GET | `/api/cameras/{id}/snapshot/` | user | Face-blurred JPEG for mapping (502 if the camera can't be reached) |
| GET, POST | `/api/hallways/?camera={id}` | read: user · write: admin | Hallways with `polygon`, live `people_count`, nested checkouts |
| GET, PUT, PATCH, DELETE | `/api/hallways/{id}/` | read: user · write: admin | |
| GET, POST | `/api/checkouts/?hallway={id}` | read: user · write: admin | Checkouts: `polygon`, `staff_polygon`, live `is_occupied`, `is_open` |
| GET, PUT, PATCH, DELETE | `/api/checkouts/{id}/` | read: user · write: admin | `PATCH {"staff_polygon": null}` removes the cashier zone |
| GET | `/api/occupancy-logs/?hallway={id}` | user | History, cursor-paginated, newest first |
| GET | `/api/display/` | public | LCD feed: hallway name, count, `online`, checkout states (no coordinates, no camera details) |
| WS | `/ws/display/` | public | Same payload: full state on connect, then a push on every change |
| GET | `/api/internal/vision-config/` | `X-Service-Token` | Active cameras with decrypted RTSP URL and all zones |
| POST | `/api/internal/ingest/` | `X-Service-Token` | `{camera_id, hallways: {id: count}, checkouts: {id: busy}, open: {id: staffed}}` |
| GET | `/stream/{camera_id}` | user (nginx `auth_request`) | Annotated MJPEG stream |

`/api/internal/*` returns 404 from outside, through nginx. Vision service endpoints (internal only): `GET /health`, `POST /snapshot`, `GET /streams/{id}`.

---

## 7. Security and privacy

- **No tokens visible to JavaScript.** JWTs live only in `HttpOnly`, `Secure`, `SameSite=Strict` cookies. Every write needs a CSRF token (double-submit).
- **Roles** are enforced on every endpoint; operators are read-only.
- **Camera credentials** are encrypted with Fernet. The key is derived from `FIELD_ENCRYPTION_KEY`. They're decrypted only for the vision service and never shown in the UI or API.
- **Service-to-service authentication** uses `SERVICE_TOKEN`, compared in constant time. The internal endpoints are also blocked at nginx, and the vision service has no published port.
- **Video streams** go through nginx `auth_request`: only logged-in users can watch.
- **Privacy:** faces are blurred in streams *and* snapshots, and no raw frames are stored. The public LCD feed contains no images, coordinates or camera details.
- **Startup checks:** in production the backend refuses to start without `DJANGO_SECRET_KEY`, `FIELD_ENCRYPTION_KEY` and `SERVICE_TOKEN`. Login is rate-limited, and WebSocket connections from foreign origins are rejected.
- **Containers:** the backend runs as a non-root user.

---

## 8. Configuration

All configuration comes from `.env` at the repository root. Copy `.env.example` and fill in the secrets; generate each one with `python -c "import secrets; print(secrets.token_urlsafe(50))"`.

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | — **required** | Django signing key (sessions, JWT) |
| `FIELD_ENCRYPTION_KEY` | — **required** | Encrypts camera passwords. **Never change it once cameras exist; back it up.** |
| `SERVICE_TOKEN` | — **required** | Shared secret between the backend and the vision service. Any long random value; safe to change. |
| `POSTGRES_PASSWORD` | — **required** | Database password |
| `POSTGRES_USER` / `POSTGRES_DB` | `surveillance` | Database user and name |
| `DJANGO_ALLOWED_HOSTS` | `localhost` | Host names users type in the browser (comma-separated) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Needed only behind a proxy that changes the origin |
| `DJANGO_DEBUG` | `0` | `1` for local development only |
| `AUTH_COOKIE_SECURE` | `1` | `1` = cookies only over HTTPS (localhost also works). `0` only for a plain-HTTP LAN install |
| `TIME_ZONE` | `UTC` | e.g. `Europe/Paris` |
| `HTTP_PORT` | `80` | Port published by nginx |
| `TORCH_INDEX` | CUDA 13.0 index | `https://download.pytorch.org/whl/cpu` to build the vision image for a CPU-only machine |
| `TARGET_FPS` | `15` (compose) | Frames analysed per second per camera |
| `LOG_LEVEL` | `INFO` | Logging level |

Vision service tuning (set in `docker/docker-compose.yml` → `vision.environment`):

| Variable | Default | Description |
|---|---|---|
| `DETECTION_CONF` | `0.4` | Minimum detection confidence |
| `CLOSE_AFTER_SECONDS` | `5` | Seconds a cashier zone must stay empty before its checkout shows *Fermée* |
| `STREAM_WIDTH` | `1280` | Width of the dashboard video stream (analysis always uses full frames) |
| `PUSH_INTERVAL` | `1` | Seconds between metric pushes to the backend |
| `CONFIG_REFRESH` | `15` | Seconds between configuration syncs |
| `POSE_MODEL` | `yolo26n-pose.pt` | Ultralytics pose model (a larger model is more accurate but slower) |

---

## 9. Running the app

### Requirements
- Docker Desktop (Windows / macOS) or Docker Engine + Compose (Linux).
- **NVIDIA GPU (recommended):** an NVIDIA driver supporting CUDA 13 and Docker GPU support (Docker Desktop on WSL2, or the NVIDIA Container Toolkit on Linux).
- **No GPU:** set `TORCH_INDEX=https://download.pytorch.org/whl/cpu` in `.env` and delete the `deploy:` block of the `vision` service in `docker/docker-compose.yml`. Expect around 3–5 fps per camera.
- About 15 GB of free disk space for the images.

### Production (Docker)
All commands run from the **repository root**:
```bash
cp .env.example .env                       # then fill in the secrets
docker compose -f docker/docker-compose.yml --env-file .env up -d --build
docker compose -f docker/docker-compose.yml --env-file .env exec backend python manage.py createsuperuser
```
- Console: **http://localhost**. LCD screens: **http://\<server\>/#/lcd**. API docs: http://localhost/api/docs/
- Put TLS in front of nginx, with a load balancer or certificates in `docker/nginx.conf`. Login cookies are `Secure`.
- Database data lives in the Docker volume `smart_surveillance_pgdata`. `down -v` deletes it.

To shorten the commands, set once in your shell: `COMPOSE_FILE=docker/docker-compose.yml` and `COMPOSE_ENV_FILES=.env`. After that, `docker compose up -d` is enough.

### Local development (without Docker)
```bash
# Backend: port 8000
pip install -r requirements.txt
export DJANGO_DEBUG=1 AUTH_COOKIE_SECURE=0          # PowerShell: $env:DJANGO_DEBUG=1; $env:AUTH_COOKIE_SECURE=0
python manage.py migrate && python manage.py createsuperuser
uvicorn config.asgi:application --reload --port 8000    # runserver can't serve WebSockets

# Vision service: port 8001 (same SERVICE_TOKEN as the backend; the dev default is "dev-service_token")
cd vision_service && pip install -r requirements.txt
SERVICE_TOKEN=dev-service_token uvicorn main:app --port 8001

# Frontend: port 5173 (Vite proxies /api, /ws and /stream)
cd frontend && npm install && npm run dev
```
Without `POSTGRES_HOST` the backend uses SQLite, and without `REDIS_URL` it uses an in-memory channel layer (single process).

### First use
1. Log in as the admin.
2. **Caméras → Ajouter une caméra**: name, IP address, RTSP URL (without credentials), username and password.
3. **Zones** on that camera: draw the **Couloir**, then each **Caisse (côté client)**, then each **Zone caissier** behind its counter.
4. Open **Supervision** to watch, and put `/#/lcd` on the store's screens.

---

## 10. Testing with simulated cameras

[docker/docker-compose.sim.yml](docker/docker-compose.sim.yml) turns video files into RTSP cameras, through a MediaMTX server and one ffmpeg loop per video.

```bash
# 1. Put videos in sim/ (e.g. sim/queue.mp4, sim/checkout.mp4); free stock footage works well.
# 2. Start the stack with the simulation add-on:
docker compose -f docker/docker-compose.yml -f docker/docker-compose.sim.yml --env-file .env up -d
# 3. In the app, add cameras with RTSP URLs rtsp://rtsp:8554/cam1 and rtsp://rtsp:8554/cam2 (no credentials).
```
To change a video, edit its service's `command: ["<file in sim/>", "<stream name>"]`, restart that service, then redraw its zones. To add a camera, copy a `camera-sim-N` block with a new stream name.

---

## 11. Tests

```bash
DJANGO_DEBUG=1 python manage.py test tests             # backend: 8 tests
cd vision_service && pytest test_tracker.py            # vision: 5 tests
```
- **Backend:** login with HttpOnly cookies, CSRF enforcement, token refresh and logout, read-only operators, encrypted camera passwords, RTSP URL validation, ingest (only the camera's own zones, only changed rows written, history), closed checkouts never counted as free, the public LCD feed (no coordinates), the service token, polygon validation, and the WebSocket push sent once per change.
- **Vision:** zone counting on scaled polygons, a cashier zone excluding staff and opening or closing a checkout, the face region, blur clipping, and that batched GPU embeddings match DeepSORT's own embedder (cosine similarity > 0.999).

---

## 12. Performance

Measured on an RTX 4060 (8 GB) with two 1080p cameras:

| Stage | Time per frame |
|---|---|
| YOLO26n-pose (FP16) | ~15–30 ms |
| DeepSORT appearance embeddings (batched on the GPU) | ~15 ms |
| DeepSORT matching | ~25 ms |
| **Stream delivered to the dashboard** | **11–13 fps per camera** |

Three choices made the biggest difference: decoding RTSP on its own thread, batching embeddings on the GPU, and limiting the CPU math libraries to one thread each. Together they took the dashboard from 5 to 12 fps and vision CPU use from 750% to about 180%.

Database load is about one small write per camera per second, plus only the rows that changed. Each LCD update is serialised once and fanned out through Redis.

---

## 13. Limits and roadmap

| Today | Next step |
|---|---|
| One store per deployment | Add `Organization` to cameras and users and scope every query (multi-store SaaS) |
| Staff are recognised only inside cashier zones | Uniform recognition for staff out on the floor |
| Counts are taken frame by frame (they can jump by ±1) | Smooth over 2–3 seconds before publishing |
| The zone spotlight assumes 16:9 cameras | Read the stream's real aspect ratio |
| One shared model behind a lock (about 10–13 cameras per GPU) | Batch frames across cameras; one vision node per GPU, sharded by camera |
| Migrations run when the backend container starts | A dedicated release step when running several backend replicas |
| `occupancylog` grows without limit | Monthly partitioning or TimescaleDB |
| Video overlay labels are ASCII only (OpenCV font) | TrueType rendering for accented names |
