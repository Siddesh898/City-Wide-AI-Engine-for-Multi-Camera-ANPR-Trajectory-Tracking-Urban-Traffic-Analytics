"""M5: real-time alert worker. Subscribes to `anpr.events`, checks the
blacklist and route anomalies, writes to `alerts`, and republishes to
`anpr.alerts` (which the backend WebSocket streams to the UI).

Run:  python -m analytics.alert_worker
"""
import os
import json
import uuid
import psycopg2
from confluent_kafka import Consumer, Producer

from common.schemas import ANPREvent
from common.geo import haversine_km, implausible_speed

DSN = os.getenv("PG_DSN", "host=localhost dbname=anpr user=anpr password=anpr")
BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")


class AlertWorker:
    def __init__(self):
        self.consumer = Consumer({
            "bootstrap.servers": BROKERS,
            "group.id": "alerts",
            "auto.offset.reset": "latest",
        })
        self.consumer.subscribe(["anpr.events"])
        self.producer = Producer({"bootstrap.servers": BROKERS})
        self.conn = psycopg2.connect(DSN)
        self.conn.autocommit = True

    def _blacklisted(self, plate):
        with self.conn.cursor() as cur:
            cur.execute("SELECT reason FROM blacklist WHERE plate_text=%s", (plate,))
            row = cur.fetchone()
            return row[0] if row else None

    def _last_sighting(self, plate, before_event_id):
        """Most recent prior sighting of this plate at a different camera."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT e.camera_id, e.ts, ST_Y(c.geom) AS lat, ST_X(c.geom) AS lon
                FROM anpr_events e JOIN cameras c USING (camera_id)
                WHERE e.plate_text=%s AND e.event_id <> %s
                ORDER BY e.ts DESC LIMIT 1
            """, (plate, before_event_id))
            return cur.fetchone()

    def _cam_location(self, camera_id):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT ST_Y(geom), ST_X(geom) FROM cameras WHERE camera_id=%s",
                (camera_id,))
            return cur.fetchone()

    def _raise(self, atype, e: ANPREvent, detail):
        aid = str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO alerts (alert_id, alert_type, plate_text, camera_id, ts, detail)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (aid, atype, e.plate_text, e.camera_id, e.timestamp, json.dumps(detail)))
        payload = {
            "alert_id": aid, "alert_type": atype, "plate_text": e.plate_text,
            "camera_id": e.camera_id, "ts": e.timestamp.isoformat(), "detail": detail,
        }
        self.producer.produce("anpr.alerts", json.dumps(payload).encode())
        self.producer.poll(0)
        print(f"ALERT [{atype}] {e.plate_text} @ {e.camera_id}")

    def _check_anomaly(self, e: ANPREvent):
        prev = self._last_sighting(e.plate_text, e.event_id)
        here = self._cam_location(e.camera_id)
        if not prev or not here:
            return
        dist = haversine_km(prev["lat"], prev["lon"], here[0], here[1])
        seconds = (e.timestamp - prev["ts"]).total_seconds()
        if dist > 0.1 and implausible_speed(dist, seconds):
            self._raise("anomaly", e, {
                "from_camera": prev["camera_id"],
                "dist_km": round(dist, 2),
                "seconds": round(seconds, 1),
                "note": "impossible travel time between cameras",
            })

    def run(self):
        print("alert_worker: watching anpr.events...")
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None or msg.error():
                    continue
                e = ANPREvent.model_validate_json(msg.value())
                reason = self._blacklisted(e.plate_text)
                if reason:
                    self._raise("blacklist", e, {"reason": reason})
                self._check_anomaly(e)
        finally:
            self.consumer.close()
            self.conn.close()


if __name__ == "__main__":
    AlertWorker().run()
