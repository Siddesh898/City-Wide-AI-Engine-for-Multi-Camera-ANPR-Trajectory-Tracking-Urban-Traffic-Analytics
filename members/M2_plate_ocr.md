# Member 2 — Plate Detection + OCR (the >90% accuracy core)
**Team A (Vision & Ingestion)** · Owns `vision/plate_ocr.py`, `common/plate_normalize.py`

## Your job in one line
Read the license plate out of each vehicle crop, robustly, across bad lighting,
weather, angles, motion blur, and dirt — and hit **>90% exact-match accuracy**.
This is the single make-or-break deliverable of the whole project.

## The accuracy formula (memorize this)
Accuracy does **not** come from a stock OCR call. It comes from three levers, in
order of impact:
1. **Multi-frame voting per `track_id`** — you read the plate on every frame of a
   track and vote for the consensus. One blurry frame can't sink you.
2. **Aggressive preprocessing** — deskew, upscale, CLAHE contrast, denoise.
3. **A plate-detection model fine-tuned on Indian plates** (`plate_yolo.pt`).

## Where you sit
```
M1 vehicle crop → [YOU: detect plate box → enhance → OCR → vote] → M3 event
```

## Files you own
- `vision/plate_ocr.py` — detection + OCR + voting (scaffolded).
- `common/plate_normalize.py` — cleanup + Indian-format validation (shared with M3).

## Step 0 — setup
```bash
source .venv/bin/activate
pip install -r requirements.txt      # pulls paddleocr + paddlepaddle + ultralytics
```

## Step 1 — run with NO fine-tuned model (day 1)
`PlateOCR` is built to work immediately: if `plate_yolo.pt` doesn't exist, it OCRs
the whole vehicle crop. Get the pipeline moving before you train anything.
Quick smoke test:
```python
python - <<'PY'
import cv2
from vision.plate_ocr import PlateOCR
ocr = PlateOCR()
img = cv2.imread("datasets/plate_sample.jpg")   # any car/plate image
ocr.feed(track_id=1, vehicle_crop=img)
print(ocr.finalize(1))                            # (plate, confidence, raw)
PY
```

## Step 2 — how voting works (the API M3 calls)
- `feed(track_id, vehicle_crop)` — call **every frame** of a track. Reads the
  plate, normalizes it, and stores a confidence-weighted vote. Valid Indian-format
  plates get a 1.5× weight boost.
- `finalize(track_id)` — call **when the track ends**. Returns
  `(plate_text, confidence, raw)` = the winning vote, or `None`.

## Step 3 — train the plate detector (the big accuracy jump)
1. Collect a labeled dataset: **CCPD** + Indian plate sets + your own frames.
2. Write `datasets/plates.yaml` (YOLO format, one `plate` class).
3. Fine-tune and export to repo root — `PlateOCR` auto-detects the file:
   ```bash
   yolo detect train data=datasets/plates.yaml model=yolov8n.pt epochs=80 imgsz=640
   cp runs/detect/train/weights/best.pt plate_yolo.pt
   ```
4. Restart your worker — it now crops the plate region before OCR. Big accuracy
   gain on angled/dirty plates because OCR sees only the plate, not the whole car.

## Step 4 — measure accuracy from DAY 2 (non-negotiable)
Keep a held-out test set (images + ground-truth plate strings). Score exact match:
```python
python - <<'PY'
import cv2, glob, json
from vision.plate_ocr import PlateOCR
truth = json.load(open("datasets/test/labels.json"))   # {filename: "KA01AB1234"}
ocr, correct = PlateOCR(), 0
for i, (fn, gt) in enumerate(truth.items()):
    ocr.feed(i, cv2.imread(f"datasets/test/{fn}"))
    pred = ocr.finalize(i)
    correct += bool(pred and pred[0] == gt)
print(f"accuracy = {correct/len(truth):.1%}")
PY
```
Track this number daily. If it's below 90%, work the three levers above.

## Step 5 — tuning knobs
- `_enhance()`: CLAHE `clipLimit`, denoise `h`, upscale `fx/fy`. Tune against your
  **hardest** images (night, blur, dirt), not the easy ones.
- Vote weight for valid-format plates: the `1.5` multiplier in `feed()`.
- `common/plate_normalize.py`: `PLATE_RE` is the Indian format regex; `DIGIT_FIXES`
  maps common OCR confusions (O→0, I→1, S→5…). Extend if you see recurring errors.

## Definition of done
- `finalize()` returns a confidence-scored plate string.
- **≥90% exact-match** on the held-out set — report the actual number to the team.
- Works with and without `plate_yolo.pt`.

## Watch out for
- Garbage-in from M1: if track IDs switch, your votes scatter. Coordinate with M1.
- Over-aggressive normalization can "correct" a right answer into a wrong one —
  that's why `normalize_plate` keeps imperfect strings and only *flags* validity.
