-- Главные места на карте (Ш-69). Источник: выбрано командой Jol по слою популярных мест
-- (data/seed/popular_places.csv, country_places.csv; поле popularity), источник в таблице: 'jol_seed'.
-- Идемпотентно: можно запускать повторно (upsert по месту). Места находятся по ключу OSM
-- (osm_type, osm_id), для ручных мест без OSM — по названию; отсутствующие в базе пропускаются
-- с предупреждением. Ранг — внутри региона (1 = важнейшее). min_zoom — масштаб карты, с которого
-- показывается подпись: на обзоре города (Алматы ~11) подписей нет; ранги 1-3 с 12, остальные с
-- 12.5-13.5; icon — ключ рисунка в приложении (mosque, cathedral, tv_tower, skating_rink, ski_cable_car,
-- bazaar, park, museum, monument, mausoleum, canyon, mountain_lake, ferris_wheel, theatre, stadium, square); места других регионов — с 11.5.
DO $$
DECLARE
    r record;
    pid uuid;
BEGIN
    FOR r IN
        SELECT * FROM (VALUES
            -- Алматы
            ('node',     4665038995::bigint,  'Медеу',                                    1, 12.0::real, 'skating_rink'),
            ('way',      1254871130,          'Шымбулак',                                 2, 12.0, 'ski_cable_car'),
            ('node',     12985379969,         'Кок-Тобе',                                 3, 12.0, 'tv_tower'),
            ('relation', 3427772,             'Большое Алматинское озеро',                4, 12.5, 'mountain_lake'),
            ('way',      50648292,            'Вознесенский собор (Зенковский)',          5, 13.0, 'cathedral'),
            ('way',      597984193,           'Площадь Республики',                       6, 13.0, 'square'),
            ('relation', 20040804,            'Зелёный базар',                            7, 13.0, 'bazaar'),
            ('way',      1458254422,          'Центральная мечеть Алматы',                8, 13.0, 'mosque'),
            ('way',      444574821,           'Центральный государственный музей Казахстана', 9, 13.5, 'museum'),
            -- Казахстан (за пределами Алматы)
            ('way',      117854803,           'Мавзолей Ходжи Ахмеда Ясави',              1, 11.5, 'mausoleum'),
            ('way',      22722438,            'Чарынский каньон',                         2, 11.5, 'canyon'),
            (NULL,       NULL,                'Кольсайские озёра',                        3, 11.5, 'mountain_lake')
        ) AS t (osm_type, osm_id, name_ru, rank, min_zoom, icon)
    LOOP
        SELECT id INTO pid FROM places
        WHERE status = 'active'
          AND CASE WHEN r.osm_id IS NOT NULL
                   THEN osm_type = r.osm_type AND osm_id = r.osm_id
                   ELSE osm_id IS NULL AND name_ru = r.name_ru END
        LIMIT 1;
        IF pid IS NULL THEN
            RAISE WARNING 'landmarks: place not found, skipped: %', r.name_ru;
            CONTINUE;
        END IF;
        INSERT INTO landmarks (place_id, rank, min_zoom, icon, source, as_of)
        VALUES (pid, r.rank, r.min_zoom, r.icon, 'jol_seed', DATE '2026-11-24')
        ON CONFLICT (place_id) DO UPDATE
            SET rank = EXCLUDED.rank, min_zoom = EXCLUDED.min_zoom, icon = EXCLUDED.icon,
                source = EXCLUDED.source, as_of = EXCLUDED.as_of;
    END LOOP;
END $$;
