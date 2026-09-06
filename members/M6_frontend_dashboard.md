# Member 6 — Frontend GIS Dashboard
**Team B (Platform & Analytics)** · Owns `frontend/`

## Your job in one line
Build the centralized, GIS-integrated web dashboard: camera map, plate search with
animated trajectory playback, live traffic heatmap, real-time alert panel, and
trend charts. That's the presentation half of deliverable #3 — **what the judges
actually look at.**

## Your superpower: you don't wait for anyone
There's a **mock API** (`backend/mock_server.py`) that serves the exact same
contract as the real backend, with fake data and a WebSocket that emits demo
alerts. You build the entire UI on day 1 while Team B builds the real thing.

## Files you own
- `frontend/src/App.jsx` — map + trajectory + heatmap + alerts (scaffolded).
- `frontend/src/main.jsx`, `index.html`, `package.json`, `vite.config.js`.

## Step 0 — start the mock API
```bash
source .venv/bin/activate
uvicorn backend.mock_server:app --port 8000
```

## Step 1 — run the UI
```bash
cd frontend
npm install
npm run dev            # opens http://localhost:5173
```
Out of the box you get: blue camera markers, a plate search box, a red animated
trajectory line with timestamped popups, a live heatmap layer, and a live alerts
panel filling from the WebSocket.

## Step 2 — understand the API contract you consume
| Call | Returns | Used for |
|------|---------|----------|
| `GET /cameras` | `[{camera_id,name,lat,lon,...}]` | map markers |
| `GET /trajectory?plate=X` | `{points:[{lat,lon,ts,speed_kmph,camera_id}], total_km, duration_s}` | trajectory playback |
| `GET /analytics/heatmap` | `[{lat,lon,weight}]` | heatmap layer |
| `GET /analytics/density` | `[{camera_id,ts_bucket,count}]` | trend chart |
| `GET /analytics/od-matrix` | `[{origin_cam,dest_cam,count}]` | flow view |
| `GET /analytics/congestion` | `[{camera_id,name,lat,lon,avg_kmph}]` | bottleneck markers |
| `WS /ws/alerts` | stream of `{alert_type,plate_text,camera_id,ts}` | live alert panel |

## Step 3 — the two views to build out (scaffolds exist for the rest)
1. **Trends view** — Recharts `LineChart` fed by `/analytics/density`. Group by
   `camera_id`, x-axis `ts_bucket`, y-axis `count`. `recharts` is already in
   `package.json`.
2. **O-D / congestion view** — either a table of `/analytics/od-matrix` sorted by
   count, or draw flow arrows on the map. Overlay `/analytics/congestion` cameras
   as red markers.

Suggested structure: split `App.jsx` into `MapView`, `TrendsView`, `AlertsPanel`
components with a simple tab switcher.

## Step 4 — how the existing pieces work (in App.jsx)
- **Map**: MapLibre GL, centered on Bengaluru. Camera markers loaded on `load`.
- **Trajectory search**: `search()` fetches `/trajectory`, draws a `LineString`
  layer, then drops markers on a `setTimeout` stagger for the "playback" effect,
  and `fitBounds` to the route.
- **Heatmap**: a MapLibre `heatmap` layer from the analytics feed.
- **Alerts**: a `WebSocket` to `/ws/alerts`, newest first, color-coded by type
  (red = blacklist, amber = anomaly).

## Step 5 — point at the real backend
When Team B's API is ready, create `frontend/.env`:
```
VITE_API=http://localhost:8000
```
`App.jsx` already reads `import.meta.env.VITE_API` and derives the WS url from it.
No code change needed to switch mock → real.

## Definition of done
- Map with camera markers.
- Plate search → animated trajectory with timestamped, speed-labeled popups.
- Live heatmap layer.
- Live alerts panel updating over WebSocket.
- Trends chart + an O-D/congestion view.

## Watch out for
- CORS: the backend allows all origins (demo only), so local dev just works.
- MapLibre needs its CSS imported (already done in `App.jsx`) or markers misplace.
- The demo tile style is a public MapLibre demo; swap for a real style/key if you
  want proper street tiles for the final demo.
