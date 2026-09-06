# Member 1 — Vehicle Detection + Tracking · Full Step-by-Step Guide
**Team A (Vision & Ingestion)** · Owns `vision/vehicle_tracker.py`

This is the long-form walkthrough. For the one-page summary see
[M1_vehicle_tracking.md](M1_vehicle_tracking.md).

---

## What M1 actually does (the goal)
You take a video (or live camera) and, for every vehicle, draw a box around it and
give it an **ID that stays the same the whole time that vehicle is on screen**. You
also cut out a small image ("crop") of each vehicle and estimate its heading.

**Why the ID matters:** M2 reads the number plate. A single frame can be blurry, so
M2 reads the plate on *every* frame and takes a vote. That voting only works if
every frame of the same car carries the **same** ID. So your #1 job is **stable
track IDs**. Everything else is secondary.

Your only file: `vision/vehicle_tracker.py`.

---

## Step 0 — one-time setup
```bash
cd ~/Documents/anpr-city
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
The prompt shows `(.venv)` when the environment is active. The install pulls
`ultralytics` (YOLO + ByteTrack); it can take a few minutes.

**GPU (you have an RTX 3050):** after the NVIDIA driver is installed and you've
rebooted, install the CUDA build of PyTorch so tracking runs on the GPU:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
Want to see `True NVIDIA GeForce RTX 3050 ...`. If it prints `False`, tracking still
works on CPU — just slower. Not a blocker.

---

## Step 1 — get a test video
```bash
mkdir -p datasets
cp /path/to/your/traffic-video.mp4 datasets/sample.mp4
```
Any clip of cars on a road works (dashcam, CCTV, phone). It does **not** need
readable plates — you're testing tracking, not OCR.

---

## Step 2 — run the tracker
```bash
python -m vision.vehicle_tracker datasets/sample.mp4
```
First run auto-downloads `yolov8n.pt` (~6 MB) once. Then lines scroll:
```
3 car E
3 car E
7 truck N
12 bike NE
```
`3 car E` = track ID 3, a car, heading East. Run from the repo root so Python finds
the `vision` package.

---

## Step 3 — the ONE thing to verify
Watch the **first number** (track ID) as one car crosses the frame. It should stay
the same for many lines in a row (`3 3 3 ...`). One car = one stable ID.

**Bad sign:** the same car keeps getting new numbers (`3` → `9` → `21`). That is
"ID switching" and it breaks M2. If you see it, go to Step 5.

---

## Step 4 — your output contract (do not break this)
The `__main__` block only prints 3 fields for eyeballing. The real output M3
consumes is the dict yielded by `stream()`:
```python
{
  "track_id": 3,                    # stable ID
  "vehicle_type": "car",            # car | bike | bus | truck
  "bbox": (x1, y1, x2, y2),         # box corners in pixels
  "crop": <image of just that car>, # goes to M2 to read the plate
  "direction": "E",                 # heading, or None if barely moving
  "timestamp": <UTC time>,
}
```
**Do not rename these keys** — M3 reads them by name in
`ingestion/camera_worker.py`. This dict *is* your agreement with Team A.

How it works, briefly:
- `VEHICLE_CLASSES` — the 4 COCO ids for vehicles, so people/dogs are ignored.
- `self.model.track(..., stream=True)` — detects vehicles **and** assigns stable IDs
  (ByteTrack) in one call; frame-by-frame so it doesn't load the whole video.
- bbox clamping — keeps crops inside the frame so they're never empty.
- `_heading()` — center now vs. previous frame → compass direction; returns `None`
  on jitter instead of a random heading.

---

## Step 5 — tuning (your real work this week)

### 5a. Fix ID switching (most important)
Edit the constructor in `vision/vehicle_tracker.py` to use a bigger model:
```python
def __init__(self, model_path="yolov8s.pt"):   # was yolov8n.pt
```
`n` = fastest/least accurate, `s`/`m` = steadier detection → steadier IDs (slower).
On the RTX 3050, start with `s`; move to `m` only if IDs still jump.

If IDs still break after occlusions (car passes behind a pole, returns with a new
id), raise ByteTrack's memory. Locate its config:
```bash
python -c "import ultralytics, os; print(os.path.join(os.path.dirname(ultralytics.__file__), 'cfg', 'trackers', 'bytetrack.yaml'))"
```
Copy it into the repo, raise `track_buffer` (e.g. 30 → 60 frames a lost track is
remembered), and point `tracker=` at your copy in `stream()`.

### 5b. Direction flickers
Raise the jitter gate in `_heading`: `dx*dx + dy*dy > 25`. Bigger number = the car
must move more pixels before a heading is reported. Raise for high-res video, lower
for small frames.

### 5c. Missing two-wheelers / autos
COCO has no "auto-rickshaw"; bikes are labeled `motorcycle`. Fine for the demo. If
Indian two/three-wheelers matter for grading, note it — the real fix is a custom
detector later (overlaps M2's dataset work).

---

## Step 6 — watch it with your own eyes (recommended)
Fastest visual check is Ultralytics' built-in viewer:
```bash
yolo track model=yolov8s.pt source=datasets/sample.mp4 show=True tracker=bytetrack.yaml classes=[2,3,5,7]
```
A window opens with labeled, ID-tagged boxes. Confirm IDs stay glued to each car.
This is a diagnostic — your real code is still `vehicle_tracker.py`. There's also a
repo helper: `python -m datasets.preview datasets/sample.mp4` (see `datasets/preview.py`).

---

## Step 7 — check the crops are clean
M2 gets the `crop`; empty/wrong crops mean M2 reads nothing. Temporarily dump a few:
```python
import cv2
cv2.imwrite(f"datasets/crop_{det['track_id']}.jpg", det["crop"])
```
Open `datasets/crop_*.jpg` — each should be a clean single vehicle, not blank, not
the whole frame. Remove the line when satisfied.

---

## Definition of done
- Running on a video prints track IDs that **stay stable** per vehicle.
- Saved crops are clean single-vehicle images.
- Works with both a **file** and an **RTSP url** as `source`.

## Handoff
Nothing to "send" — M3 imports your `VehicleTracker` class directly. Your job is
that the class behaves. When M3 can run
`python -m ingestion.camera_worker CAM_01 datasets/sample.mp4` and see plates print,
your link in the chain is proven.

## The mental model
You are the first link. Unstable tracks here quietly wreck M2's accuracy — and M2's
accuracy is the graded deliverable. Your bar isn't "it runs," it's "IDs are
rock-steady and crops are clean." Spend your time on Step 5.
