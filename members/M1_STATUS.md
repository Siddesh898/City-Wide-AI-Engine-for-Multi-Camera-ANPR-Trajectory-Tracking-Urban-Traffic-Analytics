# M1 — Vehicle Detection + Tracking · STATUS: DONE

**Owner:** M1 (Team A · Vision & Ingestion) · **File:** `vision/vehicle_tracker.py`

## Summary
`vision/vehicle_tracker.py` takes any video file or RTSP URL and yields one dict
per tracked vehicle per frame — `track_id`, `vehicle_type` (car/bike/bus/truck),
`bbox`, `crop` (BGR image of just that vehicle), `direction` (8-point compass),
and `timestamp` (UTC) — with stable per-vehicle IDs via YOLO + ByteTrack.
Verified on GPU (RTX 3050): track IDs stay glued to each vehicle (0 fragmentation
on the traffic clip) and crops are clean single-vehicle images (0 blank/whole-frame).
Switched the default model from `yolov8n` to `yolov8s` after measuring that it
eliminates `vehicle_type` label-flips (car↔bus) with identical ID stability
(commit `a2ec9ad`). **Do not rename the dict keys** — M3's
`ingestion/camera_worker.py` reads them by name; that dict is the contract.
Nothing is stored or sent from M1 (it hands off in memory to M2), so the
integration proof is on M3's side: once M2's OCR is installed,
`python -m ingestion.camera_worker CAM_01 datasets/sample.mp4` should print
plates, confirming the M1→M2→M3 chain.

## Definition of done — all met
- [x] Stable track IDs per vehicle (0 fragments on the traffic clip)
- [x] Clean single-vehicle crops (0 blank / whole-frame; verified visually)
- [x] Works for file **and** RTSP (same `source` code path)
- [x] Committed (`a2ec9ad`)

## Output contract (frozen — do not change key names)
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

## How to re-verify (any teammate)
```bash
cd ~/Documents/anpr-city && source .venv/bin/activate
python -m vision.vehicle_tracker datasets/sample.mp4          # text: track IDs
python -m datasets.preview datasets/sample.mp4 yolov8s.pt     # visual: boxes + IDs
```

## Open item for the team (NOT an M1 bug)
The current test clips are sparse and overhead-angle with unreadable plates.
**M2 needs a busier clip with readable Indian plates** to hit the >90% OCR target.
