# Member 3 — Ingestion Pipeline (normalize, dedup, publish, store)
**Team A (Vision & Ingestion)** · Owns `ingestion/camera_worker.py`, `ingestion/db_consumer.py`

## Your job in one line
Wire M1 + M2 into a per-camera worker that builds `ANPREvent`s, drops duplicate
reads, publishes to Kafka, and (consumer side) writes them into the database.
**You are the seam between Team A and Team B — pair closely with M4.**

## Where you sit
```
M1 track + M2 plate → [YOU: build event → dedup → Kafka anpr.events] → [YOU: consume → DB]
```

## Files you own
- `ingestion/camera_worker.py` — runs tracker + OCR, produces events (scaffolded).
- `ingestion/db_consumer.py` — Kafka → TimescaleDB writer (scaffolded).

## Step 0 — setup + infra (day 1, whole team)
```bash
source .venv/bin/activate && set -a; . ./.env; set +a
cd infra && docker compose up -d && cd ..
# create the topics
docker compose -f infra/docker-compose.yml exec kafka \
  kafka-topics.sh --create --topic anpr.events --bootstrap-server localhost:9092 --if-not-exists
docker compose -f infra/docker-compose.yml exec kafka \
  kafka-topics.sh --create --topic anpr.alerts --bootstrap-server localhost:9092 --if-not-exists
```

## Step 1 — run one camera worker
One process per camera. `camera_id` must match a row in the `cameras` table
(CAM_01..CAM_08 are seeded).
```bash
python -m ingestion.camera_worker CAM_01 datasets/sample.mp4
# or a live stream:
python -m ingestion.camera_worker CAM_02 rtsp://user:pass@ip/stream
```
It prints `[CAM_01] KA01AB1234 (0.93)` as it emits events.

## Step 2 — run the DB consumer
Separate terminal. Scale by starting more instances in the same consumer group.
```bash
python -m ingestion.db_consumer
```

## Step 3 — verify events land in the DB
```bash
docker compose -f infra/docker-compose.yml exec db \
  psql -U anpr -d anpr -c \
  "SELECT plate_text, camera_id, ts FROM anpr_events ORDER BY ts DESC LIMIT 10;"
```

## Step 4 — how the worker works (so you can tune it)
Per frame it calls `self.ocr.feed(track_id, crop)`. It **finalizes** a track when
that track hasn't been seen for `FINALIZE_AFTER` frames (default 15), then:
1. `ocr.finalize()` → `(plate, conf, raw)`.
2. **Dedup:** if the same plate was emitted at this camera within
   `DEDUP_WINDOW_S` seconds (default 30), skip it.
3. Build a validated `ANPREvent` and `produce()` to `anpr.events`.

Tuning knobs at the top of `camera_worker.py`:
- `DEDUP_WINDOW_S` — raise if the same car is emitted twice; lower if a car that
  legitimately passes twice gets swallowed.
- `FINALIZE_AFTER` — lower to emit sooner (more responsive), raise to collect more
  votes (more accurate). Trade-off with M2.

## Step 5 — the event contract (do not drift from this)
Every event is a `common.schemas.ANPREvent`. The DB insert in `db_consumer.py`
lists the exact columns. If M4 changes the schema, update **both** the insert and
`infra/sql/init.sql` together, and tell M2 if any plate field changes.

## Definition of done
- Worker publishes validated `ANPREvent`s to `anpr.events`.
- Consumer writes them to `anpr_events` with no duplicates (dedup + `ON CONFLICT`).
- End-to-end: run worker on a video → rows appear in the DB.

## Watch out for
- Kafka not ready yet → producer errors. Confirm `docker compose ps` shows kafka up.
- `camera_id` not in `cameras` table → the DB insert fails on the FK. Seed first.
- This is the vertical-slice owner: get **one** event from video → DB → API working
  before Team A adds features. See STEPS.md §3.
