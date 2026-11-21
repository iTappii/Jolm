-- Illustrative estimates for development. These amounts are not verified fares.
-- Explicit negative IDs make this seed repeatable and keep manual versions newer.
INSERT INTO transport_tariffs (
    version_id, mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, approximate, source
) VALUES
    (-1, 'walk',    '1970-01-01',   0,  0,   0, false, 'Пешком бесплатно'),
    (-2, 'scooter', '1970-01-01', 100, 40,   0, true,  'Пример для разработки'),
    (-3, 'bus',     '1970-01-01', 100,  0,   0, true,  'Пример для разработки'),
    (-4, 'metro',   '1970-01-01', 100,  0,   0, true,  'Пример для разработки'),
    (-5, 'taxi',    '1970-01-01', 400, 30, 100, true,  'Пример для разработки'),
    (-6, 'car',     '1970-01-01',   0,  0,  25, true,  'Пример для разработки')
ON CONFLICT (version_id) DO NOTHING;
