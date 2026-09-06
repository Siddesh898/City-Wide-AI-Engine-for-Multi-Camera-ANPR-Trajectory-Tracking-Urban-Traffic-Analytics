"""M1: vehicle detection + multi-object tracking + heading estimation.

Turns a raw camera feed (RTSP url or video file) into stable per-vehicle
tracks with crops. Each yielded dict is one tracked vehicle in one frame;
M2 votes over all frames of the same track_id to read the plate.
"""
import math
from datetime import datetime, timezone
from ultralytics import YOLO

# COCO class ids for vehicles.
VEHICLE_CLASSES = {2: "car", 3: "bike", 5: "bus", 7: "truck"}
_COMPASS = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]


class VehicleTracker:
    def __init__(self, model_path="yolov8n.pt"):
        # ByteTrack ships with ultralytics; the tracker yaml selects it.
        self.model = YOLO(model_path)
        self.prev_centroid = {}  # track_id -> (cx, cy)

    def _heading(self, tid, cx, cy):
        """8-point compass heading from centroid movement, or None if jitter."""
        if tid in self.prev_centroid:
            px, py = self.prev_centroid[tid]
            dx, dy = cx - px, cy - py
            if dx * dx + dy * dy > 25:  # ignore sub-5px jitter
                ang = (math.degrees(math.atan2(-dy, dx)) + 360) % 360
                self.prev_centroid[tid] = (cx, cy)
                return _COMPASS[int(((ang + 22.5) % 360) / 45)]
        self.prev_centroid[tid] = (cx, cy)
        return None

    def stream(self, source):
        """Yield one dict per tracked vehicle per frame."""
        for res in self.model.track(
            source=source, stream=True, tracker="bytetrack.yaml",
            classes=list(VEHICLE_CLASSES), verbose=False,
        ):
            ts = datetime.now(timezone.utc)
            if res.boxes is None or res.boxes.id is None:
                continue
            frame = res.orig_img
            h, w = frame.shape[:2]
            for box, tid, cls in zip(
                res.boxes.xyxy.cpu().numpy(),
                res.boxes.id.int().cpu().tolist(),
                res.boxes.cls.int().cpu().tolist(),
            ):
                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 <= x1 or y2 <= y1:
                    continue
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                yield {
                    "track_id": tid,
                    "vehicle_type": VEHICLE_CLASSES.get(cls, "unknown"),
                    "bbox": (x1, y1, x2, y2),
                    "crop": frame[y1:y2, x1:x2].copy(),
                    "direction": self._heading(tid, cx, cy),
                    "timestamp": ts,
                }


if __name__ == "__main__":
    import sys
    vt = VehicleTracker()
    for det in vt.stream(sys.argv[1]):  # video path or rtsp url
        print(det["track_id"], det["vehicle_type"], det["direction"])
