"""M5: macro traffic analytics endpoints. Mounted on M4's FastAPI app.

Density, heatmap, O-D matrix, and congestion — all read from anpr_events.
"""
from fastapi import APIRouter, Query
from backend.db import get_conn

router = APIRouter(prefix="/analytics")


@router.get("/density")
def density(bucket: str = "5 minutes", hours: int = 6):
    """Per-camera detection counts bucketed over time (traffic density)."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT camera_id,
                   time_bucket(%s::interval, ts) AS ts_bucket,
                   count(*) AS count
            FROM anpr_events
            WHERE ts > now() - (%s || ' hours')::interval
            GROUP BY camera_id, ts_bucket
            ORDER BY ts_bucket
        """, (bucket, hours))
        return cur.fetchall()


@router.get("/heatmap")
def heatmap(hours: int = 1):
    """Weighted points for a live traffic heatmap layer."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT ST_Y(c.geom) AS lat, ST_X(c.geom) AS lon, count(*) AS weight
            FROM anpr_events e JOIN cameras c USING (camera_id)
            WHERE e.ts > now() - (%s || ' hours')::interval
            GROUP BY c.geom
        """, (hours,))
        return cur.fetchall()


@router.get("/od-matrix")
def od_matrix(hours: int = 3):
    """Origin-destination counts from consecutive sightings of each plate."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            WITH seq AS (
              SELECT plate_text, camera_id, ts,
                     lead(camera_id) OVER (
                       PARTITION BY plate_text ORDER BY ts) AS dest
              FROM anpr_events
              WHERE ts > now() - (%s || ' hours')::interval)
            SELECT camera_id AS origin_cam, dest AS dest_cam, count(*) AS count
            FROM seq
            WHERE dest IS NOT NULL AND dest <> camera_id
            GROUP BY origin_cam, dest_cam
            ORDER BY count DESC
        """, (hours,))
        return cur.fetchall()


@router.get("/congestion")
def congestion(window: str = "15 minutes", baseline_kmph: float = 15.0):
    """Cameras whose recent average speed is below a congestion baseline."""
    with get_conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT e.camera_id, cam.name,
                   ST_Y(cam.geom) AS lat, ST_X(cam.geom) AS lon,
                   avg(e.speed_kmph) AS avg_kmph, count(*) AS vehicles
            FROM anpr_events e JOIN cameras cam USING (camera_id)
            WHERE e.ts > now() - %s::interval AND e.speed_kmph IS NOT NULL
            GROUP BY e.camera_id, cam.name, cam.geom
            HAVING avg(e.speed_kmph) < %s
            ORDER BY avg_kmph ASC
        """, (window, baseline_kmph))
        return cur.fetchall()
