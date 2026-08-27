from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Mapping


@dataclass(frozen=True)
class PlateCandidate:
    plate: str
    confidence: float


@dataclass(frozen=True)
class Detection:
    plate: str
    camera_id: str
    lane_id: str
    timestamp: datetime
    latitude: float
    longitude: float


class HighPrecisionOCRModule:
    """Deep-learning style OCR facade with multi-lane processing."""

    def __init__(self, scorer: Callable[[PlateCandidate], float] | None = None) -> None:
        self._scorer = scorer or (lambda candidate: candidate.confidence)

    def process_lanes(self, lane_candidates: Mapping[str, Iterable[PlateCandidate]]) -> dict[str, PlateCandidate]:
        results: dict[str, PlateCandidate] = {}
        for lane_id, candidates in lane_candidates.items():
            lane_candidates_list = list(candidates)
            if not lane_candidates_list:
                continue
            best = max(lane_candidates_list, key=self._scorer)
            results[lane_id] = best
        return results


class TrajectoryReconstructionEngine:
    """Stores detections and provides query-based tracking results."""

    def __init__(self) -> None:
        self._detections: list[Detection] = []

    def ingest_detection(self, detection: Detection) -> None:
        self._detections.append(detection)

    def query_trajectory(
        self,
        plate: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Detection]:
        filtered = [d for d in self._detections if d.plate == plate]
        if start_time is not None:
            filtered = [d for d in filtered if d.timestamp >= start_time]
        if end_time is not None:
            filtered = [d for d in filtered if d.timestamp <= end_time]
        return sorted(filtered, key=lambda detection: detection.timestamp)


class CityTrafficAnalyticsDashboard:
    """Produces GIS-friendly summary objects for web dashboard consumption."""

    def build_gis_summary(self, detections: Iterable[Detection]) -> dict[str, object]:
        detections_list = list(detections)
        volume_by_camera: dict[str, int] = {}
        features: list[dict[str, object]] = []

        for detection in detections_list:
            volume_by_camera[detection.camera_id] = volume_by_camera.get(detection.camera_id, 0) + 1
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [detection.longitude, detection.latitude],
                    },
                    "properties": {
                        "plate": detection.plate,
                        "camera_id": detection.camera_id,
                        "lane_id": detection.lane_id,
                        "timestamp": detection.timestamp.isoformat(),
                    },
                }
            )

        return {
            "metrics": {
                "total_detections": len(detections_list),
                "volume_by_camera": volume_by_camera,
            },
            "geojson": {
                "type": "FeatureCollection",
                "features": features,
            },
        }


class AlertSystem:
    """Real-time alerts for blacklisted plates and route anomalies."""

    def __init__(self, blacklisted_plates: Iterable[str] | None = None) -> None:
        self._blacklisted = set(blacklisted_plates or [])
        self._expected_routes: dict[str, list[str]] = {}
        self._recent_path: dict[str, list[str]] = {}

    def set_expected_route(self, plate: str, ordered_camera_ids: Iterable[str]) -> None:
        self._expected_routes[plate] = list(ordered_camera_ids)

    def process_detection(self, detection: Detection) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []

        if detection.plate in self._blacklisted:
            alerts.append(
                {
                    "type": "blacklisted_vehicle",
                    "plate": detection.plate,
                    "camera_id": detection.camera_id,
                }
            )

        path = self._recent_path.setdefault(detection.plate, [])
        path.append(detection.camera_id)

        expected_route = self._expected_routes.get(detection.plate)
        if expected_route is not None:
            prefix = expected_route[: len(path)]
            if path != prefix:
                alerts.append(
                    {
                        "type": "route_anomaly",
                        "plate": detection.plate,
                        "camera_id": detection.camera_id,
                    }
                )

        return alerts
