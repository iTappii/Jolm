-- Ш-60: intercity hubs, links and parameters (SSOT §5.4 п. 5).
-- OPEN(SSOT §16.15): this is HAND-MADE DATA, not a schedule feed. Every link is an approximate range
-- (duration, price per person) with its source and as_of date. No train numbers or exact departure times
-- are invented: where the schedule is unknown, `schedule_days` is NULL and `departure_hint` says what was
-- seen. Where a source gave only a minimum fare, the upper bound is a team estimate (stated in `source`).
-- RUB fares of Russian aggregators are converted at an assumed ~6 KZT per RUB (rounded). Check before launch.
-- Repeatable: run after migrations (data/seed/load_seed.py does it).

INSERT INTO intercity_hubs (id, kind, name_ru, name_en, city_ru, city_en, code, location, catchment_km) VALUES
 ('almaty-airport',   'airport', 'Аэропорт Алматы',          'Almaty International Airport', 'Алматы',   'Almaty',   'ALA', ST_SetSRID(ST_MakePoint(77.0426, 43.3557), 4326), 50),
 ('almaty-2',         'rail',    'Вокзал Алматы-2',          'Almaty-2 railway station',     'Алматы',   'Almaty',   NULL,  ST_SetSRID(ST_MakePoint(76.9391, 43.2738), 4326), 50),
 ('almaty-sayran',    'bus',     'Автовокзал Сайран',        'Sayran bus station',           'Алматы',   'Almaty',   NULL,  ST_SetSRID(ST_MakePoint(76.8583, 43.2446), 4326), 50),
 ('almaty-centre',    'city',    'Алматы, центр',            'Almaty, city centre',          'Алматы',   'Almaty',   NULL,  ST_SetSRID(ST_MakePoint(76.9455, 43.2389), 4326), 40),
 ('turkestan-airport','airport', 'Аэропорт Туркестан',       'Turkistan Airport',            'Туркестан','Turkistan','HSA', ST_SetSRID(ST_MakePoint(68.5489, 43.3134), 4326), 60),
 ('turkestan-rail',   'rail',    'Вокзал Туркестан',         'Turkistan railway station',    'Туркестан','Turkistan',NULL,  ST_SetSRID(ST_MakePoint(68.2129, 43.2857), 4326), 60),
 ('turkestan-bus',    'bus',     'Автовокзал Туркестан',     'Turkistan bus station',        'Туркестан','Turkistan',NULL,  ST_SetSRID(ST_MakePoint(68.3668, 43.2666), 4326), 60),
 ('shymkent-airport', 'airport', 'Аэропорт Шымкент',         'Shymkent International Airport','Шымкент',  'Shymkent', 'CIT', ST_SetSRID(ST_MakePoint(69.4809, 42.3648), 4326), 60),
 ('shymkent-rail',    'rail',    'Вокзал Шымкент',           'Shymkent railway station',     'Шымкент',  'Shymkent', NULL,  ST_SetSRID(ST_MakePoint(69.6104, 42.2987), 4326), 60),
 ('astana-airport',   'airport', 'Аэропорт Астана',          'Astana International Airport', 'Астана',   'Astana',   'NQZ', ST_SetSRID(ST_MakePoint(71.4642, 51.0259), 4326), 60),
 ('astana-nurly-zhol','rail',    'Вокзал Нұрлы Жол',         'Nurly Zhol railway station',   'Астана',   'Astana',   NULL,  ST_SetSRID(ST_MakePoint(71.5289, 51.1120), 4326), 60),
 ('saty',             'city',    'Саты (Кольсайские озёра)', 'Saty (Kolsai Lakes)',          'Саты',     'Saty',     NULL,  ST_SetSRID(ST_MakePoint(78.4088, 43.0706), 4326), 25)
ON CONFLICT (id) DO NOTHING;

-- Links are one row per direction. Sources (all seen 2026-11-23, none booked or queried with personal data):
--   [A] https://www.aviasales.ru/routes/ala/hsa, https://www.aviasales.kz/cities/turkistan-hsa  (flight 1 h 25-1 h 33, from ~2-2.6k RUB; SCAT from ~32.6k KZT)
--   [B] https://www.tutu.ru/poezda/Almaty-2/Turkestan/  (trains 14 h 18 - 18 h 9; fares 1501-3359 RUB; evening/night departures)
--   [C] https://avia.tutu.ru/rasp/Almati--Shimkent/  (direct ~1 h, daily; from 3540-7463 RUB)
--   [D] https://avia.tutu.ru/rasp/Almati--Astana/  (direct 1 h 55, daily; from 4396 RUB)
--   [E] https://rasp.yandex.ru/train/astana--almaty-2  (train from 16 h 49 / 17 h 22)
--   [F] https://www.tutu.ru/poezda/view_d.php?np=cbaec6 and the Shymkent search page (train 026T Shymkent-Almaty 11 h 23, avg ~2.5k RUB)
--   [G] https://weproject.media/articles/detail/kolsay-i-kaindy-kak-dobratsya-iz-almaty-skolko-eto-stoit-chto-vzyat-s-soboy/ (2026-07-29: tour from 13k / 27k KZT, drive 3-4 h)
INSERT INTO intercity_links
 (from_hub, to_hub, mode, duration_min_min, duration_max_min, price_kzt_min, price_kzt_max, transfers,
  buffer_min, schedule_days, departure_hint, note_ru, note_en, source, source_url, as_of, approximate) VALUES
-- Almaty <-> Turkestan
 ('almaty-airport','turkestan-airport','plane', 85, 95, 15000, 45000, 0, 120, NULL,
  'Расписание авиакомпаний; у SCAT рейсы не каждый день — проверить на дату',
  'Прямой перелёт около 1,5 часа', 'Direct flight, about 1.5 h',
  'Оценка команды по открытым данным агрегаторов (Aviasales), 2026-11; верхняя граница цены — оценка', 'https://www.aviasales.ru/routes/ala/hsa', '2026-11-23', true),
 ('turkestan-airport','almaty-airport','plane', 85, 100, 15000, 45000, 0, 120, NULL,
  'Расписание авиакомпаний — проверить на дату',
  'Прямой перелёт около 1,5 часа', 'Direct flight, about 1.5 h',
  'Оценка команды по открытым данным агрегаторов (Aviasales), 2026-11; верхняя граница цены — оценка', 'https://www.aviasales.ru/routes/hsa/ala', '2026-11-23', true),
 ('almaty-2','turkestan-rail','train', 858, 1089, 9000, 20000, 0, 45, NULL,
  'Вечерние и ночные отправления (по Tutu на ноябрь 2026 — примерно с 20:00 до 24:00), не каждый день',
  'Ночной поезд; плацкарт — купе — СВ', 'Overnight train; economy, compartment or first class',
  'Оценка команды по открытым данным Tutu.ru, 2026-11 (цены в рублях пересчитаны по ~6 ₸/₽)', 'https://www.tutu.ru/poezda/Almaty-2/Turkestan/', '2026-11-23', true),
 ('turkestan-rail','almaty-2','train', 840, 1140, 9000, 20000, 0, 45, NULL,
  'Расписание не проверено — смотреть на дату',
  'Ночной поезд', 'Overnight train',
  'Оценка команды по открытым данным Tutu.ru, 2026-11 (14-19 ч; цены как в обратном направлении)', 'https://www.tutu.ru/poezda/Turkestan/Almaty-2/', '2026-11-23', true),
 ('almaty-sayran','turkestan-bus','bus', 840, 1080, 8000, 15000, 0, 30, NULL,
  'Расписание не найдено — уточнить на автовокзале',
  'Рейсовый автобус; подтверждённого расписания и цен нет', 'Coach; no confirmed schedule or fares found',
  'НЕ ПОДТВЕРЖДЕНО: оценка команды по длине дороги (~840 км) и типичной скорости автобуса, 2026-11; расписание и цены не найдены', NULL, '2026-11-23', true),
 ('turkestan-bus','almaty-sayran','bus', 840, 1080, 8000, 15000, 0, 30, NULL,
  'Расписание не найдено — уточнить на автовокзале',
  'Рейсовый автобус; подтверждённого расписания и цен нет', 'Coach; no confirmed schedule or fares found',
  'НЕ ПОДТВЕРЖДЕНО: оценка команды по длине дороги (~840 км) и типичной скорости автобуса, 2026-11; расписание и цены не найдены', NULL, '2026-11-23', true),
-- Almaty <-> Shymkent
 ('almaty-airport','shymkent-airport','plane', 60, 75, 21000, 45000, 0, 120, ARRAY[1,2,3,4,5,6,7]::smallint[],
  'Прямой рейс есть ежедневно (Tutu, 2026-11-24); время вылета — на дату',
  'Прямой перелёт около часа', 'Direct flight, about 1 h',
  'Оценка команды по открытым данным Tutu.ru, 2026-11 (от 3,5 до 7,5 тыс. ₽ у разных авиакомпаний)', 'https://avia.tutu.ru/rasp/Almati--Shimkent/', '2026-11-23', true),
 ('shymkent-airport','almaty-airport','plane', 60, 75, 21000, 45000, 0, 120, NULL,
  'Расписание авиакомпаний — проверить на дату',
  'Прямой перелёт около часа', 'Direct flight, about 1 h',
  'Оценка команды по открытым данным Tutu.ru, 2026-11', 'https://avia.tutu.ru/f/Shimkent/Almati/', '2026-11-23', true),
 ('almaty-2','shymkent-rail','train', 683, 900, 10000, 20000, 0, 45, NULL,
  'Расписание не проверено — смотреть на дату',
  'Поезд около 11-15 часов', 'Train, about 11-15 h',
  'Оценка команды по открытым данным Tutu.ru, 2026-11 (поезд 11 ч 23 мин, ~2,5 тыс. ₽; верхняя граница времени и цены — оценка)', 'https://www.tutu.ru/poezda/view_d.php?np=cbaec6', '2026-11-23', true),
 ('shymkent-rail','almaty-2','train', 683, 900, 10000, 20000, 0, 45, NULL,
  'Расписание не проверено — смотреть на дату',
  'Поезд около 11-15 часов', 'Train, about 11-15 h',
  'Оценка команды по открытым данным Tutu.ru, 2026-11 (поезд 11 ч 23 мин; верхняя граница — оценка)', 'https://www.tutu.ru/poezda/view_d.php?np=cbaec6', '2026-11-23', true),
-- Almaty <-> Astana
 ('almaty-airport','astana-airport','plane', 115, 130, 25000, 60000, 0, 120, ARRAY[1,2,3,4,5,6,7]::smallint[],
  'Прямой рейс есть ежедневно (Tutu, 2026-11-24); время вылета — на дату',
  'Прямой перелёт около 2 часов', 'Direct flight, about 2 h',
  'Оценка команды по открытым данным Tutu.ru, 2026-11 (от ~4,4 тыс. ₽; верхняя граница цены — оценка)', 'https://avia.tutu.ru/rasp/Almati--Astana/', '2026-11-23', true),
 ('astana-airport','almaty-airport','plane', 115, 130, 25000, 60000, 0, 120, NULL,
  'Расписание авиакомпаний — проверить на дату',
  'Прямой перелёт около 2 часов', 'Direct flight, about 2 h',
  'Оценка команды по открытым данным Tutu.ru, 2026-11', 'https://avia.tutu.ru/rasp/Almati--Astana/', '2026-11-23', true),
 ('almaty-2','astana-nurly-zhol','train', 1009, 1042, NULL, NULL, 0, 45, NULL,
  'Расписание не проверено — смотреть на дату',
  'Поезд около 17 часов; цены не найдены', 'Train, about 17 h; fares not found',
  'Оценка команды по открытым данным Яндекс.Расписаний, 2026-11 (16 ч 49 мин - 17 ч 22 мин); цен нет', 'https://rasp.yandex.ru/train/astana--almaty-2', '2026-11-23', true),
 ('astana-nurly-zhol','almaty-2','train', 1009, 1042, NULL, NULL, 0, 45, NULL,
  'Расписание не проверено — смотреть на дату',
  'Поезд около 17 часов; цены не найдены', 'Train, about 17 h; fares not found',
  'Оценка команды по открытым данным Яндекс.Расписаний, 2026-11; цен нет', 'https://rasp.yandex.ru/train/astana--almaty-2', '2026-11-23', true),
-- Almaty <-> Saty (Kolsai): road only; an organised tour is the only non-car option found
 ('almaty-centre','saty','tour', 180, 240, 13000, 27000, 0, 15, NULL,
  'Выезд утром в день тура; бронировать у организатора. От 13 тыс. ₸ за день, от 27 тыс. ₸ за 2 дня с ночёвкой',
  'Групповой тур: трансфер, гид и сборы обычно включены', 'Group tour: transfer, guide and fees usually included',
  'Оценка команды по статье WE Project от 2026-07-29 (цены "от"; верхняя граница — цена двухдневного тура)', 'https://weproject.media/articles/detail/kolsay-i-kaindy-kak-dobratsya-iz-almaty-skolko-eto-stoit-chto-vzyat-s-soboy/', '2026-11-23', true),
 ('saty','almaty-centre','tour', 180, 240, 13000, 27000, 0, 15, NULL,
  'Возврат в составе тура',
  'Возврат группой в составе тура', 'Return with the tour group',
  'Оценка команды по статье WE Project от 2026-07-29', 'https://weproject.media/articles/detail/kolsay-i-kaindy-kak-dobratsya-iz-almaty-skolko-eto-stoit-chto-vzyat-s-soboy/', '2026-11-23', true)
ON CONFLICT (from_hub, to_hub, mode) DO NOTHING;

INSERT INTO intercity_settings (key, value, unit, source, as_of) VALUES
 ('fuel_l_per_100km', 9, 'л/100 км', 'Оценка команды 2026-11: средний легковой автомобиль, трасса', '2026-11-23'),
 ('fuel_price_kzt_per_l', 220, '₸/л', 'Оценка команды 2026-11: АИ-92 на АЗС; сверить с ценами на дату', '2026-11-23'),
 ('min_distance_km', 50, 'км', 'Порог: дальше этого расстояния по дороге действуют межгородские тарифы такси и топливо', '2026-11-23'),
 ('max_road_km', 1500, 'км', 'Дальше машина и такси как вариант не предлагаются', '2026-11-23')
ON CONFLICT (key) DO NOTHING;
