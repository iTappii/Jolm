-- Place categories seed (TECH_PLAN Ш-07). Idempotent: upsert by slug, safe to re-run.
-- outdoor = true: the place suffers from bad weather (SSOT §7.1).
-- Columns: slug, parent_slug, name_ru, name_en, outdoor, sort_order

INSERT INTO place_categories (slug, parent_id, name_ru, name_en, outdoor, sort_order)
SELECT v.slug,
       (SELECT p.id FROM place_categories p WHERE p.slug = v.parent_slug),
       v.name_ru, v.name_en, v.outdoor, v.sort_order
FROM (VALUES
    -- groups (parents) first so that children can resolve them
    ('sights',        NULL,     'Достопримечательности',      'Sights',                  true,  10),
    ('culture',       NULL,     'Культура и досуг',           'Culture & leisure',       false, 20),
    ('nature',        NULL,     'Природа и горы',             'Nature & mountains',      true,  30),
    ('shopping',      NULL,     'Рынки и магазины',           'Markets & shopping',      false, 40),
    ('food',          NULL,     'Еда и напитки',              'Food & drink',            false, 50),
    ('accommodation', NULL,     'Жильё',                      'Accommodation',           false, 60)
) AS v(slug, parent_slug, name_ru, name_en, outdoor, sort_order)
ON CONFLICT (slug) DO UPDATE
SET name_ru = EXCLUDED.name_ru, name_en = EXCLUDED.name_en, outdoor = EXCLUDED.outdoor,
    sort_order = EXCLUDED.sort_order, parent_id = EXCLUDED.parent_id;

INSERT INTO place_categories (slug, parent_id, name_ru, name_en, outdoor, sort_order)
SELECT v.slug,
       (SELECT p.id FROM place_categories p WHERE p.slug = v.parent_slug),
       v.name_ru, v.name_en, v.outdoor, v.sort_order
FROM (VALUES
    -- sights
    ('landmark',      'sights',  'Достопримечательности',          'Landmarks',               true,  11),
    ('monument',      'sights',  'Памятники и монументы',          'Monuments',               true,  12),
    ('historic',      'sights',  'Исторические места',             'Historic sites',          true,  13),
    ('religious',     'sights',  'Храмы и мечети',                 'Religious sites',         false, 14),
    -- culture & leisure
    ('museum',        'culture', 'Музеи',                          'Museums',                 false, 21),
    ('gallery',       'culture', 'Выставки и галереи',             'Exhibitions & galleries', false, 22),
    ('theatre',       'culture', 'Театры и концертные залы',       'Theatres & concert halls', false, 23),
    ('entertainment', 'culture', 'Развлечения',                    'Entertainment',           false, 24),
    ('amusement',     'culture', 'Парки аттракционов',             'Amusement parks',         true,  25),
    ('spa',           'culture', 'Бани и спа',                     'Baths & spa',             false, 26),
    -- nature
    ('park',          'nature',  'Парки',                          'Parks',                   true,  31),
    ('garden',        'nature',  'Сады и ботанические сады',       'Gardens',                 true,  32),
    ('mountain',      'nature',  'Горы и природа',                 'Mountains & nature',      true,  33),
    ('viewpoint',     'nature',  'Смотровые площадки',             'Viewpoints',              true,  34),
    ('lake',          'nature',  'Озёра и водопады',               'Lakes & waterfalls',      true,  35),
    ('ski',           'nature',  'Горнолыжные курорты',            'Ski resorts',             true,  36),
    -- shopping
    ('market',        'shopping', 'Рынки',                         'Markets',                 false, 41),
    ('mall',          'shopping', 'Торговые центры',               'Shopping malls',          false, 42),
    -- food and drink
    ('restaurant',    'food',    'Рестораны',                      'Restaurants',             false, 51),
    ('cafe_kazakh',   'food',    'Казахская кухня',                'Kazakh cuisine',          false, 52),
    ('cafe_oriental', 'food',    'Восточная и среднеазиатская кухня', 'Oriental & Central Asian cuisine', false, 53),
    ('cafe_chinese',  'food',    'Китайская кухня',                'Chinese cuisine',         false, 54),
    ('cafe_korean',   'food',    'Корейская кухня',                'Korean cuisine',          false, 55),
    ('cafe_japanese', 'food',    'Японская кухня',                 'Japanese cuisine',        false, 56),
    ('cafe_european', 'food',    'Европейская кухня',              'European cuisine',        false, 57),
    ('cafe_caucasian','food',    'Кавказская и грузинская кухня',  'Caucasian & Georgian cuisine', false, 58),
    ('cafe_fast_food','food',    'Фастфуд',                        'Fast food',               false, 59),
    ('coffee',        'food',    'Кофейни',                        'Coffee shops',            false, 60),
    ('bakery',        'food',    'Пекарни и кондитерские',         'Bakeries & pastry',       false, 61),
    ('bar',           'food',    'Бары и пабы',                    'Bars & pubs',             false, 62),
    ('nightclub',     'food',    'Ночные клубы',                   'Nightclubs',              false, 63),
    -- accommodation
    ('hotel',         'accommodation', 'Отели',                    'Hotels',                  false, 71),
    ('hostel',        'accommodation', 'Хостелы',                  'Hostels',                 false, 72),
    ('guest_house',   'accommodation', 'Гостевые дома и апартаменты', 'Guest houses & apartments', false, 73)
) AS v(slug, parent_slug, name_ru, name_en, outdoor, sort_order)
ON CONFLICT (slug) DO UPDATE
SET name_ru = EXCLUDED.name_ru, name_en = EXCLUDED.name_en, outdoor = EXCLUDED.outdoor,
    sort_order = EXCLUDED.sort_order, parent_id = EXCLUDED.parent_id;
