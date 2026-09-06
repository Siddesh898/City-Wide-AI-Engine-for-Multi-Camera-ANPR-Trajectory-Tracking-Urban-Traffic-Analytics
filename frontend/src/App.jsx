import { useEffect, useState, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const API = import.meta.env.VITE_API || "http://localhost:8000";
const WS = API.replace(/^http/, "ws");

export default function App() {
  const mapRef = useRef(null);
  const [plate, setPlate] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [info, setInfo] = useState(null);

  useEffect(() => {
    const map = new maplibregl.Map({
      container: "map",
      style: "https://demotiles.maplibre.org/style.json",
      center: [77.5946, 12.9716],
      zoom: 12,
    });
    mapRef.current = map;

    map.on("load", async () => {
      const cams = await fetch(`${API}/cameras`).then((r) => r.json());
      cams.forEach((c) =>
        new maplibregl.Marker({ color: "#2563eb" })
          .setLngLat([c.lon, c.lat])
          .setPopup(new maplibregl.Popup().setText(c.name))
          .addTo(map)
      );

      // Heatmap layer from analytics.
      const heat = await fetch(`${API}/analytics/heatmap`).then((r) => r.json());
      map.addSource("heat", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: heat.map((h) => ({
            type: "Feature",
            properties: { weight: h.weight },
            geometry: { type: "Point", coordinates: [h.lon, h.lat] },
          })),
        },
      });
      map.addLayer({
        id: "heat-layer",
        type: "heatmap",
        source: "heat",
        paint: {
          "heatmap-weight": ["get", "weight"],
          "heatmap-radius": 40,
          "heatmap-opacity": 0.6,
        },
      });
    });

    const ws = new WebSocket(`${WS}/ws/alerts`);
    ws.onmessage = (e) => setAlerts((a) => [JSON.parse(e.data), ...a].slice(0, 50));
    return () => {
      ws.close();
      map.remove();
    };
  }, []);

  async function search() {
    if (!plate) return;
    const data = await fetch(`${API}/trajectory?plate=${plate}`).then((r) => r.json());
    setInfo(data);
    const coords = data.points.map((p) => [p.lon, p.lat]);
    const map = mapRef.current;
    if (map.getSource("traj")) {
      map.removeLayer("traj-line");
      map.removeSource("traj");
    }
    map.addSource("traj", {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "LineString", coordinates: coords } },
    });
    map.addLayer({
      id: "traj-line",
      type: "line",
      source: "traj",
      paint: { "line-color": "#e11d48", "line-width": 4 },
    });
    // Animated playback: drop timestamped markers in sequence.
    data.points.forEach((p, i) =>
      setTimeout(() => {
        new maplibregl.Marker({ color: "#e11d48" })
          .setLngLat([p.lon, p.lat])
          .setPopup(
            new maplibregl.Popup().setText(
              `${p.camera_id}\n${new Date(p.ts).toLocaleTimeString()}` +
                (p.speed_kmph ? `\n${p.speed_kmph} km/h` : "")
            )
          )
          .addTo(map);
      }, i * 600)
    );
    if (coords.length)
      map.fitBounds([coords[0], coords[coords.length - 1]], { padding: 90 });
  }

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "system-ui" }}>
      <div id="map" style={{ flex: 1 }} />
      <aside style={{ width: 360, padding: 16, overflow: "auto", background: "#0f172a", color: "#e2e8f0" }}>
        <h2 style={{ marginTop: 0 }}>ANPR City</h2>

        <h3>Trajectory search</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={plate}
            onChange={(e) => setPlate(e.target.value.toUpperCase())}
            placeholder="KA01AB1234"
            style={{ flex: 1, padding: 8, borderRadius: 6, border: "1px solid #334155" }}
          />
          <button onClick={search} style={{ padding: "8px 14px", borderRadius: 6, background: "#2563eb", color: "#fff", border: 0 }}>
            Track
          </button>
        </div>
        {info && (
          <p style={{ fontSize: 13, color: "#94a3b8" }}>
            {info.points.length} sightings · {info.total_km} km ·{" "}
            {Math.round(info.duration_s / 60)} min
          </p>
        )}

        <h3>Live alerts</h3>
        {alerts.length === 0 && <p style={{ color: "#64748b" }}>Listening…</p>}
        {alerts.map((a) => (
          <div
            key={a.alert_id}
            style={{
              borderLeft: "4px solid " + (a.alert_type === "blacklist" ? "#e11d48" : "#f59e0b"),
              padding: 8,
              marginBottom: 6,
              background: "#1e293b",
              borderRadius: 4,
            }}
          >
            <b>{a.alert_type}</b> — {a.plate_text}
            <br />
            <small style={{ color: "#94a3b8" }}>
              {a.camera_id} · {new Date(a.ts).toLocaleTimeString()}
            </small>
          </div>
        ))}
      </aside>
    </div>
  );
}
