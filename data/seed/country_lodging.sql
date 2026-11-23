-- Ш-61: places to sleep near the owner's trip (SSOT §5.2, §5.4): Saty (Kolsai Lakes) and Turkistan.
-- Source: OpenStreetMap (Overpass, tourism=hotel|guest_house|hostel with a name), checked 2026-11-23.
-- (c) OpenStreetMap contributors, ODbL. PRICES ARE NOT KNOWN: price_per_night_kzt stays NULL and the budget
-- uses the category default (and says so, `lodging_price_assumed`). Repeatable (an OSM id already present is kept).
INSERT INTO places (osm_type, osm_id, kind, category_id, name_ru, name_en, geom, status, popularity, manual_override)
SELECT v.osm_type, v.osm_id, 'accommodation', (SELECT id FROM place_categories WHERE slug = v.category),
       v.name_ru, v.name_en, ST_SetSRID(ST_MakePoint(v.lon, v.lat), 4326)::geography, 'active', v.popularity, '[]'::jsonb
FROM (VALUES
 -- Saty, around 43.07 N 78.41 E
 ('node', 1870195993::bigint,  'Кулаш-апа',                 'Kulyash-apa hotel',   'hotel',       43.0700548, 78.3985037, 40),
 ('node', 4325585890::bigint,  'Темирхан',                  'Temirkhan guest house','guest_house', 43.068086,   78.413805,  30),
 ('node', 5043260127::bigint,  'EcoHouse',                  'EcoHouse Homestay',   'hostel',      43.0700116, 78.4162731, 30),
 ('node', 13131067101::bigint, 'Алатау',                    'Alatau hotel',        'hotel',       43.069031,  78.4096595, 35),
 -- Turkistan, around 43.30 N 68.27 E
 ('node', 12952210102::bigint, 'Yassir Hostel',             'Yassir Hostel',       'hostel',      43.3024666, 68.2742032, 40),
 ('relation', 15715482::bigint,'Ханака',                    'Hanaka hotel',        'hotel',       43.2997838, 68.2745035, 40),
 ('way',  1031959444::bigint,  'Hampton by Hilton Turkistan','Hampton by Hilton Turkistan','hotel',43.2970001, 68.2764811, 50),
 ('node', 1508487832::bigint,  'Эдем',                      'Edem hotel',          'hotel',       43.3010816, 68.2763949, 30)
) AS v(osm_type, osm_id, name_ru, name_en, category, lat, lon, popularity)
ON CONFLICT (osm_type, osm_id) DO NOTHING;
