# anpr-city — SIH26-26127

City-wide AI engine for multi-camera ANPR trajectory tracking and urban traffic
analytics. Built by 2 teams of 3.

- **Full build runbook:** see [STEPS.md](STEPS.md).
- **Data contract (freeze first):** `common/schemas.py`.

## Quickstart
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && set -a; . ./.env; set +a
cd infra && docker compose up -d && cd ..
uvicorn backend.main:app --port 8000
```
Frontend (or start here on day 1 with the mock — see STEPS.md §5.3):
```bash
cd frontend && npm install && npm run dev
```

## Layout
```
common/      shared schemas, plate normalization, geo helpers  (all)
vision/      M1 vehicle tracking, M2 plate detection + OCR
ingestion/   M3 camera worker (Kafka producer) + DB consumer
backend/     M4 FastAPI, trajectory, DB, + mock_server for M6
analytics/   M5 analytics routes + real-time alert worker
frontend/    M6 React + MapLibre dashboard
infra/       docker-compose (TimescaleDB+PostGIS, Kafka), SQL schema + seed
```

## Members
Each member has a self-contained guide in `members/`. Do your file plus the
Phase 0 section of [STEPS.md](STEPS.md) on day 1.

| Member | Owns | Guide |
|--------|------|-------|
| M1 | Vehicle detection + multi-object tracking | [M1_vehicle_tracking.md](members/M1_vehicle_tracking.md) |
| M2 | Plate detection + OCR (>90% accuracy core) | [M2_plate_ocr.md](members/M2_plate_ocr.md) |
| M3 | Ingestion pipeline (normalize, dedup, publish, store) | [M3_ingestion.md](members/M3_ingestion.md) |
| M4 | DB schema + API + trajectory engine | [M4_backend_trajectory.md](members/M4_backend_trajectory.md) |
| M5 | Traffic analytics + alert system | [M5_analytics_alerts.md](members/M5_analytics_alerts.md) |
| M6 | GIS dashboard frontend | [M6_frontend_dashboard.md](members/M6_frontend_dashboard.md) |
