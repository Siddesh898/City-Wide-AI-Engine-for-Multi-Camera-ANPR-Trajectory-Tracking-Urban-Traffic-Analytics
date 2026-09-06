# Member 1 — Vehicle Detection + Multi-Object Tracking
**Team A (Vision & Ingestion)** · Owns `vision/vehicle_tracker.py`

## Your job in one line
Turn a raw camera feed (RTSP url or video file) into stable per-vehicle tracks
with cropped images. M2 votes over all frames of the same `track_id` to read the
plate, so **stable track IDs are your #1 deliverable**.

## Where you sit in the pipeline
```
cameras → [YOU: track vehicles] → M2 read plate → M3 event → Kafka → M4 store
```

## Files you own
- `vision/vehicle_tracker.py` — the tracker (already scaffolded).

## Step 0 — setup (day 1, with the whole team)
```bash
cd ~/Documents/anpr-city
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # pulls ultralytics
cp .env.example .env && set -a; . ./.env; set +a
```
`yolov8n.pt` auto-downloads on first run — no manual step.

## Step 1 — run it on a video
Drop any traffic clip at `datasets/sample.mp4`, then:
```bash
python -m vision.vehicle_tracker datasets/sample.mp4
```
You should see lines like:
```
3 car E
3 car E
7 truck N
```
The **same vehicle keeps the same id** across frames. That is what you verify.

## Step 2 — what the code yields (contract to M2/M3)
Each tracked vehicle, each frame, is one dict:
```python
{
  "track_id": int,          # stable per vehicle within this camera
  "vehicle_type": str,      # car | bike | bus | truck
  "bbox": (x1, y1, x2, y2), # clamped to frame bounds
  "crop": np.ndarray,       # BGR image of the vehicle (goes to M2)
  "direction": str | None,  # 8-point compass heading, None on jitter
  "timestamp": datetime,    # UTC
}
```
Do not rename these keys — M3 reads them in `ingestion/camera_worker.py`.

## Step 3 — tuning (this is your real work)
1. **ID switching too often?** Vehicles that get a new id every few frames wreck
   M2's voting. Fixes, in order:
   - Use a bigger model in the constructor: `VehicleTracker("yolov8s.pt")` or
     `yolov8m.pt`. Bigger = steadier boxes = steadier IDs (slower though).
   - ByteTrack params live in `bytetrack.yaml` (ships with ultralytics). Raise
     `track_buffer` so tracks survive short occlusions.
2. **Direction flickers?** The jitter gate is `dx*dx + dy*dy > 25` in `_heading`.
   Raise it for high-res video (more pixels of movement), lower it for small frames.
3. **Missing bikes/autos?** COCO has no "auto-rickshaw" class. For Indian traffic
   you'll eventually want a custom detector — note it, but `motorcycle`(3) covers
   two-wheelers for the demo.

## Step 4 — optional: real speed
Per-camera speed needs a homography (image pixels → ground metres). Ask M4 for
camera calibration; until then leave `speed_kmph` unset — M4 computes an estimate
between cameras from GPS distance in the trajectory endpoint.

## Definition of done
- `python -m vision.vehicle_tracker <video>` prints stable track IDs.
- Crops are clean vehicle images (not empty, not whole-frame).
- Handles a file **and** an RTSP url as `source`.

## Handy reference
- The `stream()` generator is called by M3's `CameraWorker.run()`.
- COCO vehicle class ids are in `VEHICLE_CLASSES` at the top of your file.
