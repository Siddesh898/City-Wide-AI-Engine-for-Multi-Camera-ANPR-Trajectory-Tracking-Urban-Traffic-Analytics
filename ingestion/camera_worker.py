"""M3: per-camera worker. Runs M1 (tracker) + M2 (OCR), builds ANPREvents,
deduplicates repeat reads, and publishes to Kafka topic `anpr.events`.

Run one process per camera:
    python -m ingestion.camera_worker CAM_01 /path/to/video.mp4
    python -m ingestion.camera_worker CAM_01 rtsp://user:pass@ip/stream
"""
import os
import sys
import uuid
from confluent_kafka import Producer

from vision.vehicle_tracker import VehicleTracker
from vision.plate_ocr import PlateOCR
from common.schemas import ANPREvent, BBox

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
DEDUP_WINDOW_S = 30      # suppress same plate at same camera within this window
FINALIZE_AFTER = 15      # frames a track can be unseen before we finalize it


class CameraWorker:
    def __init__(self, camera_id, source, brokers=BROKERS):
        self.camera_id = camera_id
        self.source = source
        self.tracker = VehicleTracker()
        self.ocr = PlateOCR()
        self.producer = Producer({"bootstrap.servers": brokers})
        self.seen = {}            # plate -> last emit epoch (dedup)
        self.active = {}          # track_id -> last det meta
        self.last_frame = {}      # track_id -> last frame number seen

    def _publish(self, event: ANPREvent):
        self.producer.produce("anpr.events", event.model_dump_json().encode())
        self.producer.poll(0)

    def run(self):
        frame_no = 0
        for det in self.tracker.stream(self.source):
            frame_no += 1
            tid = det["track_id"]
            self.ocr.feed(tid, det["crop"])
            self.active[tid] = det
            self.last_frame[tid] = frame_no

            stale = [t for t, f in self.last_frame.items() if frame_no - f > FINALIZE_AFTER]
            for t in stale:
                self._emit(t)

        # flush any tracks still open at end of stream
        for t in list(self.active.keys()):
            self._emit(t)
        self.producer.flush()

    def _emit(self, tid):
        meta = self.active.pop(tid, None)
        self.last_frame.pop(tid, None)
        result = self.ocr.finalize(tid)
        if not meta or not result:
            return
        plate, conf, raw = result
        now = meta["timestamp"].timestamp()
        if self.seen.get(plate, 0) > now - DEDUP_WINDOW_S:
            return
        self.seen[plate] = now
        x1, y1, x2, y2 = meta["bbox"]
        event = ANPREvent(
            event_id=str(uuid.uuid4()),
            camera_id=self.camera_id,
            plate_text=plate,
            plate_confidence=conf,
            ocr_raw=raw,
            timestamp=meta["timestamp"],
            vehicle_type=meta["vehicle_type"],
            bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
            track_id=tid,
            direction=meta["direction"],
        )
        self._publish(event)
        print(f"[{self.camera_id}] {plate} ({conf})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python -m ingestion.camera_worker <camera_id> <source>")
    CameraWorker(sys.argv[1], sys.argv[2]).run()
