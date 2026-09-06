"""M3: Kafka consumer that writes ANPREvents into TimescaleDB.

Run one instance (or several in the same consumer group for scale):
    python -m ingestion.db_consumer
"""
import os
import psycopg2
from confluent_kafka import Consumer

from common.schemas import ANPREvent

DSN = os.getenv("PG_DSN", "host=localhost dbname=anpr user=anpr password=anpr")
BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")

INSERT = """
    INSERT INTO anpr_events
      (event_id, camera_id, plate_text, plate_confidence, ocr_raw, ts,
       vehicle_type, direction, speed_kmph, track_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (event_id, ts) DO NOTHING
"""


def run():
    consumer = Consumer({
        "bootstrap.servers": BROKERS,
        "group.id": "db-writer",
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe(["anpr.events"])
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    print("db_consumer: waiting for events...")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None or msg.error():
                continue
            e = ANPREvent.model_validate_json(msg.value())
            cur.execute(INSERT, (
                e.event_id, e.camera_id, e.plate_text, e.plate_confidence,
                e.ocr_raw, e.timestamp, e.vehicle_type, e.direction,
                e.speed_kmph, e.track_id,
            ))
    finally:
        consumer.close()
        conn.close()


if __name__ == "__main__":
    run()
