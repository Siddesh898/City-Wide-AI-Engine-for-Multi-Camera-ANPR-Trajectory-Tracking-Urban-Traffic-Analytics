"""M4: FastAPI app — cameras registry, trajectory reconstruction, blacklist,
and the live-alerts WebSocket. M5's analytics routes are mounted here too.

Run:  uvicorn backend.main:app --reload --port 8000
"""
import os
import json
import asyncio
import uuid

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from confluent_kafka import Consumer

from backend.db import get_conn
from common.geo import haversine_km

app = FastAPI(title="ANPR City API")

# NOTE (security): open CORS + no auth is fine for the hackathon demo only.
# Gate /blacklist and /ws/alerts behind a token before any real deployment.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")


@app.get("/cameras")
def cameras():
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT camera_id, name, ST_Y(geom) AS lat, ST_X(geom) AS lon,
                   heading_deg, road_segment_id, adjacent_cameras
            FROM cameras
        """)
        return cur.fetchall()


@app.get("/trajectory")
def trajectory(plate: str,
               from_: str = Query(None, alias="from"),
               to: str = None):
    q = """
        SELECT e.camera_id, e.ts, e.direction, e.speed_kmph, e.vehicle_type,
               ST_Y(c.geom) AS lat, ST_X(c.geom) AS lon
        FROM anpr_events e JOIN cameras c USING (camera_id)
        WHERE e.plate_text = %s
    """
    params = [plate]
    if from_:
        q += " AND e.ts >= %s"
        params.append(from_)
    if to:
        q += " AND e.ts <= %s"
        params.append(to)
    q += " ORDER BY e.ts ASC"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q, params)
        rows = cur.fetchall()

    total_km = 0.0
    for i, r in enumerate(rows):
        if i > 0:
            prev = rows[i - 1]
            d = haversine_km(prev["lat"], prev["lon"], r["lat"], r["lon"])
            dt_h = (r["ts"] - prev["ts"]).total_seconds() / 3600
            r["speed_kmph"] = round(d / dt_h, 1) if dt_h > 0 else None
            total_km += d
    duration = ((rows[-1]["ts"] - rows[0]["ts"]).total_seconds()
                if len(rows) > 1 else 0)
    return {"plate": plate, "points": rows,
            "total_km": round(total_km, 2), "duration_s": duration}


@app.post("/blacklist")
def add_blacklist(plate: str, reason: str = "manual"):
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO blacklist (plate_text, reason) VALUES (%s, %s)
            ON CONFLICT (plate_text) DO UPDATE SET reason = EXCLUDED.reason
        """, (plate, reason))
        c.commit()
    return {"status": "ok", "plate": plate}


@app.get("/alerts")
def list_alerts(status: str = "open"):
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT alert_id, alert_type, plate_text, camera_id, ts, detail, status
            FROM alerts WHERE status = %s ORDER BY ts DESC LIMIT 200
        """, (status,))
        return cur.fetchall()


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    """Bridge Kafka topic `anpr.alerts` -> browser over WebSocket."""
    await ws.accept()
    consumer = Consumer({
        "bootstrap.servers": BROKERS,
        "group.id": f"ws-{uuid.uuid4()}",
        "auto.offset.reset": "latest",
    })
    consumer.subscribe(["anpr.alerts"])
    try:
        while True:
            msg = consumer.poll(0.1)
            if msg and not msg.error():
                await ws.send_text(msg.value().decode())
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        consumer.close()


# Mount M5's analytics routes.
from analytics.routes import router as analytics_router  # noqa: E402
app.include_router(analytics_router)
