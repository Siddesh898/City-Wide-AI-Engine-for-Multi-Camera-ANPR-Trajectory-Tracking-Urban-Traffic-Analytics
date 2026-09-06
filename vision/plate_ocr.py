"""M2: plate detection + OCR with multi-frame voting (the >90% accuracy core).

Accuracy comes from three levers, in order of impact:
  1. Multi-frame voting per track_id (feed() every frame, finalize() at end).
  2. Aggressive preprocessing (deskew/upscale/CLAHE/denoise).
  3. A plate-detection model fine-tuned on Indian plates (plate_yolo.pt).

Falls back to reading the whole vehicle crop if no fine-tuned plate model
is present yet, so M2 can start before the dataset is ready.
"""
import os
import cv2
import numpy as np
from collections import defaultdict, Counter

from common.plate_normalize import normalize_plate, is_valid


class PlateOCR:
    def __init__(self, plate_model="plate_yolo.pt"):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        self.plate_det = None
        if os.path.exists(plate_model):
            from ultralytics import YOLO
            self.plate_det = YOLO(plate_model)
        self.votes = defaultdict(list)  # track_id -> [(normalized_text, conf)]

    @staticmethod
    def _enhance(img):
        """Grayscale, 2x upscale, contrast-limited equalization, denoise."""
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)
        img = cv2.fastNlMeansDenoising(img, h=10)
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    def _crop_plate(self, vehicle_crop):
        """Return the plate region, or the whole crop if no plate model."""
        if self.plate_det is None:
            return vehicle_crop
        det = self.plate_det(vehicle_crop, verbose=False)[0]
        if det.boxes is None or len(det.boxes) == 0:
            return None
        i = int(det.boxes.conf.argmax())
        x1, y1, x2, y2 = map(int, det.boxes.xyxy[i].cpu().numpy())
        plate = vehicle_crop[max(0, y1):y2, max(0, x1):x2]
        return plate if plate.size else None

    def _read(self, vehicle_crop):
        plate = self._crop_plate(vehicle_crop)
        if plate is None or plate.size == 0:
            return None
        res = self.ocr.ocr(self._enhance(plate), cls=True)
        if not res or not res[0]:
            return None
        texts = [(t[1][0], t[1][1]) for t in res[0]]
        raw = "".join(t for t, _ in texts)
        conf = float(np.mean([c for _, c in texts]))
        return raw, conf

    def feed(self, track_id, vehicle_crop):
        """Call every frame for a track. Accumulates a vote if a plate is read."""
        out = self._read(vehicle_crop)
        if not out:
            return
        raw, conf = out
        norm = normalize_plate(raw)
        if norm:
            # boost votes that match the valid Indian plate format
            weight = conf * (1.5 if is_valid(norm) else 1.0)
            self.votes[track_id].append((norm, weight, raw))

    def finalize(self, track_id):
        """Call when the track ends. Returns (plate_text, confidence, raw) or None."""
        votes = self.votes.pop(track_id, [])
        if not votes:
            return None
        weighted = Counter()
        for norm, weight, _ in votes:
            weighted[norm] += weight
        raw_best = max(votes, key=lambda v: v[1])[2]
        plate, score = weighted.most_common(1)[0]
        confidence = min(0.99, score / len(votes))
        return plate, round(confidence, 3), raw_best
