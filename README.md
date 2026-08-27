# City-Wide-AI-Engine-for-Multi-Camera-ANPR-Trajectory-Tracking-Urban-Traffic-Analytics
Urban CCTV/ANPR networks currently operate in isolated silos — plates are detected per-camera with no linking across space or time. This blocks two capabilities city authorities need: tracking a specific vehicle's movement across the whole city, and extracting macro traffic trends from existing camera infrastructure.

## Implemented core modules
- **High-Precision OCR Module** (`HighPrecisionOCRModule`): score-based OCR selection across multiple lanes in one processing call.
- **Trajectory Reconstruction Engine** (`TrajectoryReconstructionEngine`): query-based trajectory retrieval by plate and time range.
- **City Traffic Analytics Dashboard** (`CityTrafficAnalyticsDashboard`): GIS-integrated summary output with metrics and GeoJSON features for web mapping.
- **Alert System** (`AlertSystem`): real-time alerts for blacklisted vehicles and route anomalies.

## Running tests
```bash
python -m unittest discover -s tests -p "test_*.py"
```
