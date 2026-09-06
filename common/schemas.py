"""Shared data contracts. FROZEN on day 1 — every module imports from here.

Team A produces ANPREvent; Team B consumes it. Do not change field names
without telling both teams — it breaks the wire format and the DB insert.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class ANPREvent(BaseModel):
    """One confirmed plate sighting at one camera. Flows A -> Kafka -> B."""
    event_id: str                      # uuid4
    camera_id: str                     # FK -> cameras registry
    plate_text: str                    # normalized, e.g. "MH12AB1234"
    plate_confidence: float            # 0..1, final multi-frame score
    ocr_raw: str                       # pre-normalization text (for audit)
    timestamp: datetime                # UTC, ISO8601, ms precision
    vehicle_type: str = "unknown"      # car|truck|bus|bike|auto|unknown
    bbox: BBox
    track_id: int                      # local track id within the camera
    direction: Optional[str] = None    # N|NE|E|SE|S|SW|W|NW estimated heading
    speed_kmph: Optional[float] = None
    lane: Optional[int] = None
    crop_uri: Optional[str] = None     # path/S3 to plate crop for audit


class CameraNode(BaseModel):
    """One physical camera in the city network."""
    camera_id: str
    name: str
    lat: float
    lon: float
    heading_deg: float = 0
    road_segment_id: Optional[str] = None
    adjacent_cameras: list[str] = Field(default_factory=list)


class Alert(BaseModel):
    alert_id: str
    alert_type: str                    # blacklist | anomaly
    plate_text: str
    camera_id: str
    ts: datetime
    detail: dict = Field(default_factory=dict)
    status: str = "open"
