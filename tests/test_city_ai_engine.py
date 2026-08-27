from datetime import datetime, timedelta
import unittest

from city_ai_engine import (
    AlertSystem,
    CityTrafficAnalyticsDashboard,
    Detection,
    HighPrecisionOCRModule,
    PlateCandidate,
    TrajectoryReconstructionEngine,
)


def make_detection(plate: str, camera: str, lane: str, at: datetime) -> Detection:
    return Detection(
        plate=plate,
        camera_id=camera,
        lane_id=lane,
        timestamp=at,
        latitude=12.9716,
        longitude=77.5946,
    )


class CityAIEngineTests(unittest.TestCase):
    def test_high_precision_ocr_module_supports_multiple_lanes(self):
        ocr = HighPrecisionOCRModule()
        result = ocr.process_lanes(
            {
                "lane-1": [PlateCandidate("KA01AB1234", 0.94), PlateCandidate("KA01AB1239", 0.91)],
                "lane-2": [PlateCandidate("KA05XY9999", 0.89), PlateCandidate("KA05XY9988", 0.93)],
            }
        )

        self.assertEqual(result["lane-1"].plate, "KA01AB1234")
        self.assertEqual(result["lane-2"].plate, "KA05XY9988")

    def test_trajectory_engine_supports_query_based_tracking(self):
        engine = TrajectoryReconstructionEngine()
        t0 = datetime(2026, 8, 27, 9, 0, 0)
        engine.ingest_detection(make_detection("KA01AB1234", "cam-1", "lane-a", t0))
        engine.ingest_detection(make_detection("KA01AB1234", "cam-2", "lane-c", t0 + timedelta(minutes=5)))
        engine.ingest_detection(make_detection("MH12ZZ0001", "cam-3", "lane-b", t0 + timedelta(minutes=10)))

        trajectory = engine.query_trajectory("KA01AB1234", start_time=t0)

        self.assertEqual([step.camera_id for step in trajectory], ["cam-1", "cam-2"])

    def test_dashboard_returns_gis_integrated_summary(self):
        dashboard = CityTrafficAnalyticsDashboard()
        t0 = datetime(2026, 8, 27, 9, 0, 0)

        summary = dashboard.build_gis_summary(
            [
                make_detection("KA01AB1234", "cam-1", "lane-a", t0),
                make_detection("KA01AB1235", "cam-1", "lane-b", t0 + timedelta(minutes=1)),
            ]
        )

        self.assertEqual(summary["metrics"]["total_detections"], 2)
        self.assertEqual(summary["metrics"]["volume_by_camera"]["cam-1"], 2)
        self.assertEqual(summary["geojson"]["type"], "FeatureCollection")
        self.assertEqual(len(summary["geojson"]["features"]), 2)

    def test_alert_system_handles_blacklist_and_route_anomaly_in_real_time(self):
        alerts = AlertSystem(blacklisted_plates=["KA01AB1234"])
        alerts.set_expected_route("KA01AB1234", ["cam-1", "cam-2"])
        t0 = datetime(2026, 8, 27, 9, 0, 0)

        first = alerts.process_detection(make_detection("KA01AB1234", "cam-1", "lane-a", t0))
        second = alerts.process_detection(
            make_detection("KA01AB1234", "cam-9", "lane-a", t0 + timedelta(minutes=1))
        )

        self.assertEqual({alert["type"] for alert in first}, {"blacklisted_vehicle"})
        self.assertEqual({alert["type"] for alert in second}, {"blacklisted_vehicle", "route_anomaly"})


if __name__ == "__main__":
    unittest.main()
