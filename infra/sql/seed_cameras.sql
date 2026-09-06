-- Seed 8 demo cameras around Bengaluru. M4: replace lat/lon with real sites.
INSERT INTO cameras (camera_id, name, geom, heading_deg, adjacent_cameras) VALUES
  ('CAM_01', 'MG Road Jn',        ST_SetSRID(ST_MakePoint(77.6094, 12.9757), 4326),  90, ARRAY['CAM_02','CAM_03']),
  ('CAM_02', 'Trinity Circle',    ST_SetSRID(ST_MakePoint(77.6200, 12.9720), 4326), 135, ARRAY['CAM_01','CAM_04']),
  ('CAM_03', 'Cubbon Rd',         ST_SetSRID(ST_MakePoint(77.5980, 12.9800), 4326),  45, ARRAY['CAM_01','CAM_05']),
  ('CAM_04', 'Domlur Flyover',    ST_SetSRID(ST_MakePoint(77.6380, 12.9610), 4326), 180, ARRAY['CAM_02','CAM_06']),
  ('CAM_05', 'Vidhana Soudha',    ST_SetSRID(ST_MakePoint(77.5905, 12.9796), 4326),   0, ARRAY['CAM_03','CAM_07']),
  ('CAM_06', 'Indiranagar 100ft', ST_SetSRID(ST_MakePoint(77.6410, 12.9719), 4326),  90, ARRAY['CAM_04','CAM_08']),
  ('CAM_07', 'Majestic',          ST_SetSRID(ST_MakePoint(77.5720, 12.9770), 4326), 270, ARRAY['CAM_05']),
  ('CAM_08', 'KR Puram',          ST_SetSRID(ST_MakePoint(77.6760, 12.9990), 4326),  45, ARRAY['CAM_06'])
ON CONFLICT (camera_id) DO NOTHING;
