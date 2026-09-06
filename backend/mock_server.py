"""Mock API so M6 (frontend) can build on day 1 without the real backend/DB.

Serves the same contract as backend.main with fake data, plus a WebSocket
that emits a random alert every few seconds.

Run:  uvicorn backend.mock_server:app --reload --port 8000
"""
import asyncio
import itertools
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ANPR City API (MOCK)")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

CAMS = [
    {"camera_id": "CAM_01", "name": "MG Road Jn", "lat": 12.9757, "lon": 77.6094, "heading_deg": 90, "adjacent_cameras": ["CAM_02"]},
    {"camera_id": "CAM_02", "name": "Trinity Circle", "lat": 12.9720, "lon": 77.6200, "heading_deg": 135, "adjacent_cameras": ["CAM_01"]},
    {"camera_id": "CAM_03", "name": "Cubbon Rd", "lat": 12.9800, "lon": 77.5980, "heading_deg": 45, "adjacent_cameras": ["CAM_01"]},
    {"camera_id": "CAM_04", "name": "Domlur Flyover", "lat": 12.9610, "lon": 77.6380, "heading_deg": 180, "adjacent_cameras": ["CAM_02"]},
    {"camera_id": "CAM_05", "name": "Vidhana Soudha", "lat": 12.9796, "lon": 77.5905, "heading_deg": 0, "adjacent_cameras": ["CAM_03"]},
]


@app.get("/cameras")
def cameras():
    return CAMS


@app.get("/trajectory")
def trajectory(plate: str, **kw):
    t0 = datetime.now(timezone.utc) - timedelta(minutes=40)
    path = ["CAM_03", "CAM_01", "CAM_02", "CAM_04"]
    pts = []
    for i, cid in enumerate(path):
        c = next(x for x in CAMS if x["camera_id"] == cid)
        pts.append({
            "camera_id": cid, "lat": c["lat"], "lon": c["lon"],
            "ts": (t0 + timedelta(minutes=12 * i)).isoformat(),
            "direction": "E", "speed_kmph": 32 + i * 4, "vehicle_type": "car",
        })
    return {"plate": plate, "points": pts, "total_km": 8.4, "duration_s": 2160}


@app.get("/analytics/heatmap")
def heatmap(**kw):
    return [{"lat": c["lat"], "lon": c["lon"], "weight": 20 + i * 15}
            for i, c in enumerate(CAMS)]


@app.get("/analytics/density")
def density(**kw):
    now = datetime.now(timezone.utc)
    out = []
    for c in CAMS:
        for b in range(12):
            out.append({
                "camera_id": c["camera_id"],
                "ts_bucket": (now - timedelta(minutes=5 * (12 - b))).isoformat(),
                "count": 10 + (b * 3) % 25,
            })
    return out


@app.get("/analytics/od-matrix")
def od_matrix(**kw):
    return [{"origin_cam": "CAM_03", "dest_cam": "CAM_01", "count": 42},
            {"origin_cam": "CAM_01", "dest_cam": "CAM_02", "count": 31}]


@app.get("/analytics/congestion")
def congestion(**kw):
    return [{"camera_id": "CAM_02", "name": "Trinity Circle",
             "lat": 12.9720, "lon": 77.6200, "avg_kmph": 8.5, "vehicles": 60}]


@app.get("/alerts")
def alerts(status: str = "open"):
    return []


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await ws.accept()
    plates = itertools.cycle(["KA01AB1234", "MH12XY9999", "KA05CD4321"])
    types = itertools.cycle(["blacklist", "anomaly"])
    try:
        while True:
            await asyncio.sleep(4)
            await ws.send_json({
                "alert_id": str(datetime.now().timestamp()),
                "alert_type": next(types),
                "plate_text": next(plates),
                "camera_id": "CAM_02",
                "ts": datetime.now(timezone.utc).isoformat(),
                "detail": {"reason": "demo"},
            })
    except Exception:
        pass
