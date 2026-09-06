# Member 4 — Database + API + Trajectory Engine
**Team B (Platform & Analytics)** · Owns `infra/sql/*.sql`, `backend/main.py`, `backend/db.py`

## Your job in one line
Own the database everyone shares, and build the **trajectory reconstruction
engine** — query a plate, get its chronological path across the city with
timestamps, camera locations, per-leg speed, and total distance. That's
deliverable #2 of the four.

## Where you sit
```
M3 → Kafka → DB (yours) → [YOU: /trajectory, /cameras] → M6 map
                        ↘ M5 analytics + alerts read your DB
```

## Files you own
- `infra/sql/init.sql` — schema (hypertable, PostGIS cameras, blacklist, alerts).
- `infra/sql/seed_cameras.sql` — camera registry seed.
- `backend/main.py` — FastAPI: `/cameras`, `/trajectory`, `/blacklist`, `/alerts`, `/ws/alerts`.
- `backend/db.py` — shared DB connection helper (M5 imports this).

## Step 0 — setup + infra (day 1, whole team)
```bash
source .venv/bin/activate && set -a; . ./.env; set +a
cd infra && docker compose up -d && cd ..
```
The DB container auto-runs `init.sql` then `seed_cameras.sql` on first start.

## Step 1 — verify the schema and seed
```bash
docker compose -f infra/docker-compose.yml exec db \
  psql -U anpr -d anpr -c "\dt"                       # tables exist
docker compose -f infra/docker-compose.yml exec db \
  psql -U anpr -d anpr -c "SELECT camera_id,name FROM cameras;"   # CAM_01..08
```

## Step 2 — put in REAL camera coordinates (important)
Trajectory distance and speed are only as good as your lat/lon. Edit
`infra/sql/seed_cameras.sql` with real sites, then re-seed:
```bash
docker compose -f infra/docker-compose.yml exec db \
  psql -U anpr -d anpr -f /docker-entrypoint-initdb.d/02_seed.sql
```
Also fill `adjacent_cameras` — M5 uses adjacency for anomaly detection.

## Step 3 — run the API
```bash
uvicorn backend.main:app --reload --port 8000
```

## Step 4 — test the two headline endpoints
```bash
curl http://localhost:8000/cameras
curl "http://localhost:8000/trajectory?plate=KA01AB1234&from=2026-09-05T00:00:00Z"
```
`/trajectory` returns:
```json
{ "plate": "...", "points": [{ "camera_id","lat","lon","ts","direction","speed_kmph" }],
  "total_km": 8.4, "duration_s": 2160 }
```

## Step 5 — how trajectory is computed (so you can extend it)
In `backend/main.py::trajectory`:
1. Fetch all events for the plate, ordered by `ts`, joined to camera lat/lon.
2. For each consecutive pair: `haversine_km` distance (from `common/geo.py`),
   divide by time delta → per-leg `speed_kmph`, accumulate `total_km`.
3. Return the ordered points + totals.
Extensions when you have time: snap the path to roads, filter impossible legs,
add a `from`/`to` bounding query (params already wired).

## Step 6 — the schema is a shared contract
`anpr_events` columns must match M3's insert in `ingestion/db_consumer.py`. If you
add/rename a column, update **both** files and tell M3. Key design points already
in place:
- `anpr_events` is a **TimescaleDB hypertable** on `ts` (fast time queries).
- Indexes on `(plate_text, ts)` and `(camera_id, ts)` — the two access patterns.
- `cameras.geom` is a **PostGIS point** (4326). Query lat/lon with `ST_Y/ST_X`.

## Definition of done
- All tables + hypertable + indexes created; 8 cameras seeded with real coords.
- `/cameras` and `/trajectory` return correct data.
- `/blacklist`, `/alerts`, `/ws/alerts` live (the WS bridges M5's `anpr.alerts`).

## Watch out for
- The DB only runs the SQL files **on first container start**. After editing
  schema, either re-run the file by hand or `docker compose down -v` to reset.
- `/ws/alerts` needs the `anpr.alerts` topic to exist and M5's worker running.
