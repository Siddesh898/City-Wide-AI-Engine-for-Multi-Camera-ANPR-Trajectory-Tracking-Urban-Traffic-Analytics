# Member 5 — Traffic Analytics + Alert System
**Team B (Platform & Analytics)** · Owns `analytics/routes.py`, `analytics/alert_worker.py`

## Your job in one line
Build the **macro traffic analytics** (density, heatmap, origin-destination
matrix, congestion) and the **real-time alert system** (blacklisted vehicles +
route anomalies). That's deliverables #3 (analytics half) and #4 (alerts).

## Where you sit
```
DB (M4) → [YOU: /analytics/*] → M6 charts + heatmap
Kafka anpr.events → [YOU: alert_worker] → anpr.alerts → M4 WS → M6 alert panel
```

## Files you own
- `analytics/routes.py` — analytics endpoints, **auto-mounted** by `backend/main.py`.
- `analytics/alert_worker.py` — Kafka consumer that raises alerts (scaffolded).

## Step 0 — setup (infra already up from day 1)
```bash
source .venv/bin/activate && set -a; . ./.env; set +a
```

## Step 1 — materialize the continuous aggregate (fast density/heatmap)
```bash
docker compose -f infra/docker-compose.yml exec db \
  psql -U anpr -d anpr -c "CALL refresh_continuous_aggregate('events_5m', NULL, NULL);"
```

## Step 2 — test the four analytics endpoints
The API is M4's app; your routes ride along on it. With `uvicorn backend.main:app`
running:
```bash
curl "http://localhost:8000/analytics/density?bucket=5%20minutes"   # per-camera counts over time
curl "http://localhost:8000/analytics/heatmap"                       # weighted lat/lon for heatmap
curl "http://localhost:8000/analytics/od-matrix"                     # origin→destination flows
curl "http://localhost:8000/analytics/congestion"                    # cameras below speed baseline
```

## Step 3 — what each endpoint does (so you can tune it)
- **density** — `time_bucket` counts per camera. Powers M6's trend chart and heatmap.
- **heatmap** — detections per camera location in the last hour → `{lat,lon,weight}`.
- **od-matrix** — uses SQL `lead()` over each plate's ordered sightings: origin =
  camera *i*, destination = camera *i+1*. This is your movement-pattern analytics.
- **congestion** — cameras whose recent avg speed is below `baseline_kmph`.
  Tune `window` and `baseline_kmph` query params to your city's normal speeds.

## Step 4 — run the alert worker
```bash
python -m analytics.alert_worker
```
It subscribes to `anpr.events` and raises two alert types:
1. **blacklist** — plate is in the `blacklist` table.
2. **anomaly** — same plate seen at two cameras faster than physically possible
   (`common.geo.implausible_speed`, default cap 200 km/h).
Each alert is written to the `alerts` table **and** published to `anpr.alerts`,
which M4's WebSocket streams to M6.

## Step 5 — demo the alert path end-to-end
```bash
# add a plate to the blacklist
curl -X POST "http://localhost:8000/blacklist?plate=KA01AB1234&reason=stolen"
# now the next time CAM_xx sees KA01AB1234, an alert fires on /ws/alerts
```
For the anomaly demo: feed the same plate into two far-apart cameras seconds apart
(easy with two `camera_worker` runs on the same clip labeled different CAM ids).

## Step 6 — tuning knobs
- Anomaly speed cap: `max_kmph` in `common/geo.py::implausible_speed`.
- Congestion baseline: `baseline_kmph` query param (or change the default).
- Aggregate bucket size: the `events_5m` view in `infra/sql/init.sql`.

## Definition of done
- All four `/analytics/*` endpoints return correct data.
- Blacklist alert fires on the next sighting; anomaly alert fires on impossible
  travel; both appear in M6's live panel via the WebSocket.

## Watch out for
- `alert_worker` uses `auto.offset.reset=latest` — it only sees **new** events
  after it starts. Start it before running camera workers for the demo.
- Analytics read the DB directly (via `backend/db.py`); make sure M4's schema and
  seed are in place first.
