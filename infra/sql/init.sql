-- M4 owns this schema. Runs automatically on first DB container start.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS cameras (
  camera_id        TEXT PRIMARY KEY,
  name             TEXT,
  geom             geometry(Point, 4326),
  heading_deg      REAL DEFAULT 0,
  road_segment_id  TEXT,
  adjacent_cameras TEXT[]
);

CREATE TABLE IF NOT EXISTS anpr_events (
  event_id         UUID,
  camera_id        TEXT REFERENCES cameras(camera_id),
  plate_text       TEXT NOT NULL,
  plate_confidence REAL,
  ocr_raw          TEXT,
  ts               TIMESTAMPTZ NOT NULL,
  vehicle_type     TEXT,
  direction        TEXT,
  speed_kmph       REAL,
  track_id         BIGINT,
  PRIMARY KEY (event_id, ts)
);
SELECT create_hypertable('anpr_events', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_events_plate ON anpr_events (plate_text, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_cam   ON anpr_events (camera_id, ts DESC);

CREATE TABLE IF NOT EXISTS blacklist (
  plate_text TEXT PRIMARY KEY,
  reason     TEXT,
  added_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alerts (
  alert_id   UUID PRIMARY KEY,
  alert_type TEXT,          -- blacklist | anomaly
  plate_text TEXT,
  camera_id  TEXT,
  ts         TIMESTAMPTZ,
  detail     JSONB,
  status     TEXT DEFAULT 'open'
);

-- Continuous aggregate for fast density/heatmap queries (M5).
CREATE MATERIALIZED VIEW IF NOT EXISTS events_5m
WITH (timescaledb.continuous) AS
SELECT camera_id,
       time_bucket('5 minutes', ts) AS bucket,
       count(*) AS cnt
FROM anpr_events
GROUP BY camera_id, bucket
WITH NO DATA;
