# SIH26-26127 — City-Wide ANPR Trajectory & Traffic Analytics
## Step-by-step build guide (2 teams × 3 members)

This is the master runbook. Every member: read the section for your role, run
the commands in order. Paths are relative to the repo root `anpr-city/`.

---

## 0. What we are building (the four required deliverables)

| # | Deliverable (from the problem statement) | Owner |
|---|------------------------------------------|-------|
| 1 | High-precision OCR module (>90% accuracy) | M2 |
| 2 | Trajectory reconstruction engine (query a plate → path on map) | M4 |
| 3 | City traffic analytics dashboard (GIS, heatmap, speeds, density) | M5 + M6 |
| 4 | Alert system (blacklist + route anomalies, real time) | M5 |

Data flows one direction:
```
cameras → M1 track → M2 read plate → M3 ANPREvent → Kafka → M4 store
                                                         ↘ M5 alerts/analytics → M6 UI
```

---

## 1. Team split

- **Team A — Vision & Ingestion:** M1 (tracking), M2 (OCR), M3 (pipeline).
- **Team B — Platform & Analytics:** M4 (DB+API+trajectory), M5 (analytics+alerts), M6 (frontend).

The seam between the teams is **`common/schemas.py` (the `ANPREvent`)** and the
**HTTP/WS API contract**. Freeze both on day 1; then everyone works in parallel.

---

## 2. Phase 0 — Day 1, EVERYONE does this first

Do not start feature work until this is green.

### 2.1 Get the code and tools
```bash
cd ~/Documents/anpr-city
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
set -a; . ./.env; set +a       # load env vars into the shell
```

### 2.2 Start infrastructure (DB + Kafka)
```bash
cd infra
docker compose up -d
docker compose ps              # db and kafka should be "running"
```
The DB auto-runs `sql/init.sql` (schema) then `sql/seed_cameras.sql` (8 cameras).

Verify the schema and seed:
```bash
docker compose exec db psql -U anpr -d anpr -c "SELECT camera_id,name FROM cameras;"
```
You should see CAM_01..CAM_08.

### 2.3 Create the Kafka topics
```bash
docker compose exec kafka \
  kafka-topics.sh --create --topic anpr.events --bootstrap-server localhost:9092 --if-not-exists
docker compose exec kafka \
  kafka-topics.sh --create --topic anpr.alerts --bootstrap-server localhost:9092 --if-not-exists
```

### 2.4 Freeze the contract
Everyone opens `common/schemas.py` together and agrees on `ANPREvent`. **No field
renames after this meeting without telling both teams.** This is the one rule
that keeps parallel work from breaking.

**Phase 0 done when:** containers are up, cameras are seeded, both topics exist.

---

## 3. Phase 1 — the vertical slice (prove the pipe end-to-end)

Goal: one real plate detection travels all the way to one trajectory line on the
map. Build this thin path *before* anyone adds features.

1. M1+M2+M3 run one camera worker on a sample video → publishes an `ANPREvent`.
2. M4's `db_consumer` stores it.
3. M6 searches the plate → sees the point/line.

Commands to prove it (run each in its own terminal, all with the venv + env):
```bash
# terminal 1 — store events
python -m ingestion.db_consumer

# terminal 2 — process a video as CAM_01
python -m ingestion.camera_worker CAM_01 datasets/sample.mp4

# terminal 3 — API
uvicorn backend.main:app --port 8000

# check it landed
curl "http://localhost:8000/trajectory?plate=KA01AB1234"
```
When that returns points, the slice works. Now split into feature work.

---

## 4. TEAM A steps

### 4.1 Member 1 — Vehicle detection + tracking
**File:** `vision/vehicle_tracker.py`

1. `pip install -r requirements.txt` pulls ultralytics; `yolov8s.pt` auto-downloads
   on first run.
2. Test on any traffic video:
   ```bash
   python -m vision.vehicle_tracker datasets/sample.mp4
   ```
   You should see `track_id vehicle_type direction` lines. Stable `track_id`
   across frames is the thing to verify — M2's accuracy depends on it.
3. Tune: if IDs switch too often, raise the model (`yolov8s.pt`/`yolov8m.pt`) in
   the constructor. Adjust the jitter threshold (`> 25`) in `_heading` for your
   video resolution.
4. Optional: add per-camera speed via homography once M4 gives you calibration.

**Deliverable:** a generator of `{track_id, vehicle_type, bbox, crop, direction, timestamp}`.

### 4.2 Member 2 — Plate detection + OCR (the >90% core)
**Files:** `vision/plate_ocr.py`, `common/plate_normalize.py`

This is the make-or-break deliverable. Accuracy comes from **multi-frame voting +
preprocessing + a fine-tuned plate model**, not a stock OCR call.

1. Day 1–2: works immediately with no plate model (reads the whole vehicle crop
   via PaddleOCR). Get the pipeline running first.
2. Build the accuracy loop:
   - Collect a labeled dataset (CCPD + Indian plates + your own frames).
   - Fine-tune YOLOv8 to detect the *plate region*, export as `plate_yolo.pt`
     into the repo root. `PlateOCR` auto-detects and uses it.
     ```bash
     yolo detect train data=datasets/plates.yaml model=yolov8n.pt epochs=80 imgsz=640
     cp runs/detect/train/weights/best.pt plate_yolo.pt
     ```
   - Keep a held-out test set. Measure accuracy from **day 2** and track it.
3. Tune preprocessing in `_enhance` (CLAHE clip, denoise strength, upscale factor)
   against your hardest images: angled, blurred, dirty, night.
4. The voting weights valid-format plates 1.5×; adjust in `feed()`.

**Deliverable + acceptance:** `finalize(track_id)` returns `(plate, conf, raw)`;
≥90% exact-match on the held-out set. Report the number.

### 4.3 Member 3 — Ingestion pipeline
**Files:** `ingestion/camera_worker.py`, `ingestion/db_consumer.py`

M3 is the seam with Team B — pair with M4.

1. Run one worker per camera (each in its own process):
   ```bash
   python -m ingestion.camera_worker CAM_01 datasets/cam01.mp4
   python -m ingestion.camera_worker CAM_02 rtsp://user:pass@ip/stream
   ```
2. Run the DB consumer (scale by starting more in the same group):
   ```bash
   python -m ingestion.db_consumer
   ```
3. Verify events land:
   ```bash
   docker compose -f infra/docker-compose.yml exec db \
     psql -U anpr -d anpr -c "SELECT plate_text,camera_id,ts FROM anpr_events ORDER BY ts DESC LIMIT 10;"
   ```
4. Tune the dedup window (`DEDUP_WINDOW_S=30`) and finalize gap (`FINALIZE_AFTER=15`).

**Deliverable:** validated `ANPREvent`s in Kafka and rows in `anpr_events`.

---

## 5. TEAM B steps

### 5.1 Member 4 — DB schema + API + trajectory
**Files:** `infra/sql/init.sql`, `infra/sql/seed_cameras.sql`, `backend/main.py`, `backend/db.py`

1. Own the schema. Replace seed lat/lon in `seed_cameras.sql` with **real camera
   sites** — trajectory distance/speed depend on accurate coordinates.
   Re-seed after edits:
   ```bash
   docker compose -f infra/docker-compose.yml exec db \
     psql -U anpr -d anpr -f /docker-entrypoint-initdb.d/02_seed.sql
   ```
2. Run the API:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
3. Test the two headline endpoints:
   ```bash
   curl http://localhost:8000/cameras
   curl "http://localhost:8000/trajectory?plate=KA01AB1234&from=2026-09-05T00:00:00Z"
   ```
   Trajectory returns points ordered by time with computed per-leg speed and total km.

**Deliverable:** `/cameras`, `/trajectory`, `/blacklist`, `/alerts`, `/ws/alerts` live.

### 5.2 Member 5 — Analytics + alerts
**Files:** `analytics/routes.py`, `analytics/alert_worker.py`

Analytics routes are auto-mounted by `backend/main.py`.

1. Materialize the continuous aggregate once (for fast density/heatmap):
   ```bash
   docker compose -f infra/docker-compose.yml exec db \
     psql -U anpr -d anpr -c "CALL refresh_continuous_aggregate('events_5m', NULL, NULL);"
   ```
2. Test analytics:
   ```bash
   curl "http://localhost:8000/analytics/density?bucket=5%20minutes"
   curl "http://localhost:8000/analytics/heatmap"
   curl "http://localhost:8000/analytics/od-matrix"
   curl "http://localhost:8000/analytics/congestion"
   ```
3. Run the alert worker:
   ```bash
   python -m analytics.alert_worker
   ```
4. Demo the alert path:
   ```bash
   curl -X POST "http://localhost:8000/blacklist?plate=KA01AB1234&reason=stolen"
   # next sighting of KA01AB1234 → alert on /ws/alerts and in alerts table
   ```
   Anomaly alerts fire when the same plate appears at two cameras faster than
   physically possible (`common/geo.implausible_speed`).

**Deliverable:** density/heatmap/O-D/congestion endpoints + live blacklist & anomaly alerts.

### 5.3 Member 6 — Frontend GIS dashboard
**Files:** `frontend/` (`src/App.jsx`, etc.)

M6 can start **day 1** against the mock — no backend needed.

1. Start the mock API (until Team B's real API is up):
   ```bash
   uvicorn backend.mock_server:app --port 8000
   ```
2. Run the UI:
   ```bash
   cd frontend
   npm install
   npm run dev            # http://localhost:5173
   ```
3. You get: camera markers, plate search → animated trajectory playback with
   timestamped popups, a live heatmap layer, and a live alerts panel via WebSocket.
4. Build out the two extra views:
   - **Trends** (Recharts line chart) from `/analytics/density`.
   - **O-D / congestion** table or flow map from `/analytics/od-matrix` and
     `/analytics/congestion`.
5. Point at the real backend by setting `VITE_API` in `frontend/.env`:
   ```
   VITE_API=http://localhost:8000
   ```

**Deliverable:** GIS dashboard covering map, trajectory, heatmap, alerts, trends.

---

## 6. Phase 2 — parallel feature work

- M2: push OCR past 90% (voting + preprocessing + fine-tuned model), measure daily.
- M5: analytics + alerts.
- M6: heatmap, trend charts, alert panel, O-D view.

## 7. Phase 3 — demo polish

- Record multi-camera video clips so the demo runs the same way every time.
- Pre-load a blacklisted plate for a guaranteed live alert.
- Show a congestion bottleneck and an O-D flow on the map.

---

## 8. Run-everything cheatsheet (one terminal each)

```bash
# infra
cd infra && docker compose up -d && cd ..

# ingestion
python -m ingestion.db_consumer
python -m ingestion.camera_worker CAM_01 datasets/sample.mp4

# backend + analytics
uvicorn backend.main:app --port 8000
python -m analytics.alert_worker

# frontend
cd frontend && npm run dev
```

---

## 9. Known risks (call these out to judges)

- **>90% OCR** is the hardest requirement. It comes from multi-frame voting per
  track + aggressive preprocessing + a plate model fine-tuned on Indian plates.
  Give M2 labeled data early and measure on a held-out set from day 2.
- **Camera geo-calibration.** Trajectory speed and congestion need accurate
  lat/lon (and ideally homography for per-camera speed). Fake coords are fine for
  the demo; plan a small calibration step for real sites.
- **Security.** The API uses open CORS and no auth — fine for the hackathon, but
  gate `/blacklist` and `/ws/alerts` behind a token before any real deployment.
