# Graph Report - Jol v2  (2026-11-21)

## Corpus Check
- 137 files · ~72,782 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: (none) 6, .csv 4, .osm 2)

## Summary
- 1436 nodes · 3531 edges · 78 communities (65 shown, 13 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 231 edges (avg confidence: 0.86)
- Token cost: 211,973 input · 0 output

## Graph Freshness
- Built from commit: `b6098af0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Personal Route Building (whole trip, by day)
- worker.py
- JolApp
- merge_place
- 8. Шаги
- Jol Logo (PNG + SVG)
- App Icon (PNG)
- App Icon (SVG)
- errors.py
- CLAUDE.md
- server
- .resolveStyleURL
- 0001. Технологический стек
- postgres
- import_places.py
- .swiftlint.yml
- tag_mapping.py
- Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас
- Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol
- base
- test_osm_import.py
- Jol
- JolUITests
- project.yml
- Jol
- Jol iOS
- htmx-1.9.12.min.js
- Ревью Ш-02. ADR по допущениям
- options
- JolTests
- MapLibre
- build_tiles.sh
- jol-server
- save_place
- test_osm_pipeline.py
- routing/service.py
- Ревью Ш-07, Ш-08, Ш-09. Данные мест
- test_admin_validation.py
- admin/api.py
- test_admin.py
- auth.py
- representative_point
- fetch_all
- transit.py
- import_transit.py
- schemas.py
- time
- MapView
- test_transit_search.py
- psycopg
- MapView.swift
- Ревью Ш-10. Админка (минимум)
- db.py
- typing
- pathlib
- dedupe.py
- get_settings
- Jol — технический план (ТЗ на реализацию)
- FakeRouter
- test_directions.py
- Jol — передача работы (2026-11-21)
- Ревью доработки Ш-08: отношения OSM и связь ручных мест
- upsert.py
- Ревью Ш-22. Стоимость и сводка вариантов
- fetch_pbf.sh
- README.md
- sessions.py
- Ревью Ш-20. Движок маршрутизации (Valhalla)
- Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)
- H
- TransitOption
- admin/service.py

## God Nodes (most connected - your core abstractions)
1. `fetch_one()` - 73 edges
2. `conn()` - 53 edges
3. `fetch_all()` - 40 edges
4. `execute()` - 36 edges
5. `db()` - 35 edges
6. `re()` - 32 edges
7. `oe()` - 31 edges
8. `ae()` - 27 edges
9. `render()` - 26 edges
10. `find_transit_options()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Аэропорт` --references--> `FakeRouter`  [INFERRED]
  docs/reviews/Ш-22.md → server/app/routing/fake.py
- `Предыдущая проверка без доступа к сервисам` --references--> `FakeRouter`  [INFERRED]
  docs/reviews/Ш-22.md → server/app/routing/fake.py
- `Что сделано` --references--> `FakeRouter`  [INFERRED]
  docs/reviews/Ш-21.md → server/app/routing/fake.py
- `0. Правила исполнения` --references--> `merge_place()`  [INFERRED]
  TECH_PLAN.md → data/osm/merge.py
- `Ф3. Карта` --references--> `MapView`  [INFERRED]
  TECH_PLAN.md → ios/Jol/Features/Map/MapView.swift

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crowdsourced Data and Bonus Flow** — jol_ssot_user_content, jol_ssot_content_moderation, jol_ssot_bonus_system, jol_ssot_demand_coefficient [EXTRACTED 1.00]
- **Living Plan Adaptation Loop** — jol_ssot_principle_living_plan, jol_ssot_weather_recheck, jol_ssot_mountain_morning_alert, jol_ssot_place_crowding, jol_ssot_open_meteo [EXTRACTED 1.00]
- **Route Building Inputs** — jol_ssot_route_building, jol_ssot_trip_budget, jol_ssot_mandatory_wishes, jol_ssot_crowd_tolerance, jol_ssot_memory_personalization [EXTRACTED 1.00]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]

## Communities (78 total, 13 thin omitted)

### Community 0 - "Personal Route Building (whole trip, by day)"
Cohesion: 0.06
Nodes (46): Jol Project Instructions (CLAUDE.md), Almaty Launch Geography, Authentication (email OTP, Sign in with Apple, SMS OTP), Bonus System (1 bonus = ~1 tenge), Bookings and Orders via Partner APIs, Dynamic Single-Branch Chat Graph, Content Verification (auto-filter + moderation), Crowd Tolerance Preference (+38 more)

### Community 1 - "worker.py"
Cohesion: 0.09
Nodes (18): Database, backoff_seconds(), _cleanup_done_jobs(), enqueue(), enqueue_due_schedules(), _main(), process_batch(), register() (+10 more)

### Community 2 - "JolApp"
Cohesion: 0.22
Nodes (5): JolApp, .body, MapScreen, .body, SwiftUI

### Community 3 - "merge_place"
Cohesion: 0.15
Nodes (7): merge_dropped(), merge_place(), Как работаем, Замечания, Ревью доработки Ш-08: дедупликация мест OSM, Что сделано, 0. Правила исполнения

### Community 4 - "8. Шаги"
Cohesion: 0.11
Nodes (19): 8. Шаги, Ф0. Основа проекта, Ф10. Готовый маршрут в приложении (SSOT §11.3), Ф11. Погода (SSOT §7.1–7.2), Ф12. Память (SSOT §8), Ф13. Скачивание, история, боковая панель, Ф14. Пользовательский контент и бонусы (SSOT §10), Ф15. Загруженность (SSOT §7.3) `[предложено, §2 п.5]` (+11 more)

### Community 5 - "Jol Logo (PNG + SVG)"
Cohesion: 0.38
Nodes (7): Orange and Black Palette, Jol Logo, Jol Logo, Orange and Black Palette, Road Underline Bar, Road Underline Motif, Jol Wordmark

### Community 6 - "App Icon (PNG)"
Cohesion: 0.67
Nodes (4): Jol App Icon (1024px), Jol Wordmark, Orange Brand Color, Underline Bar Motif

### Community 7 - "App Icon (SVG)"
Cohesion: 0.67
Nodes (4): Jol App Icon, Orange and Black Palette, Road Underline Bar Motif, Jol Wordmark (J-o-l)

### Community 8 - "errors.py"
Cohesion: 0.11
Nodes (10): error_response(), install_error_handlers(), _app_error(), _http_error(), _unhandled(), _validation_error(), pick_locale(), translate() (+2 more)

### Community 10 - "server"
Cohesion: 0.07
Nodes (26): DATABASE_URL, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, TEST_DATABASE_URL, jobs, server, name (+18 more)

### Community 11 - ".resolveStyleURL"
Cohesion: 0.09
Nodes (12): Замечания, Ревью Ш-13. iOS: проект и карта, Что проверено ревьюером, Что сделано, Чтобы закрыть шаг, Foundation, AppConfig, .mapStyleURL (+4 more)

### Community 12 - "0001. Технологический стек"
Cohesion: 0.08
Nodes (20): 0001. Технологический стек, Контекст, Последствия, Решение, Ссылки, 0002. «ИИ понимает, движок планирует», Контекст, Последствия (+12 more)

### Community 13 - "postgres"
Cohesion: 0.06
Nodes (34): build_admins, build_elevation, build_tar, build_time_zones, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, serve_tiles (+26 more)

### Community 14 - "import_places.py"
Cohesion: 0.14
Nodes (9): build_record(), extract(), find_pbf(), in_bbox(), load(), main(), relation_outer_members(), report() (+1 more)

### Community 15 - ".swiftlint.yml"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 16 - "tag_mapping.py"
Cohesion: 0.14
Nodes (18): category_for_food(), category_slug(), classify(), _clean(), _has_wiki(), parse_elevation(), pick_address(), pick_names() (+10 more)

### Community 17 - "Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас"
Cohesion: 0.33
Nodes (5): Замечания, Не проверено, Отклонения от плана (приняты как временные), Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас, Что проверено

### Community 18 - "Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol"
Cohesion: 0.33
Nodes (5): Замечания, Интеграция (сделано ревьюером), Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol, Что проверено ревьюером, Что сделано

### Community 19 - "base"
Cohesion: 0.22
Nodes (9): ASSETCATALOG_COMPILER_APPICON_NAME, CURRENT_PROJECT_VERSION, GENERATE_INFOPLIST_FILE, INFOPLIST_FILE, MARKETING_VERSION, PRODUCT_BUNDLE_IDENTIFIER, SWIFT_VERSION, TARGETED_DEVICE_FAMILY (+1 more)

### Community 20 - "test_osm_import.py"
Cohesion: 0.21
Nodes (7): _parse_days(), _parse_intervals(), parse_opening_hours(), _to_time(), test_hours_simple(), test_hours_unparsed(), test_hours_variants()

### Community 21 - "Jol"
Cohesion: 0.25
Nodes (8): package, product, dependencies, platform, settings, sources, type, Jol

### Community 22 - "JolUITests"
Cohesion: 0.25
Nodes (8): target, dependencies, dependencies, platform, settings, sources, type, JolUITests

### Community 23 - "project.yml"
Cohesion: 0.29
Nodes (6): configFiles, Debug, Release, name, settings, targets

### Community 24 - "Jol"
Cohesion: 0.33
Nodes (6): targets, build, test, schemes, Jol, targets

### Community 25 - "Jol iOS"
Cohesion: 0.33
Nodes (5): Build, Jol iOS, Layout, Location, Map style URL

### Community 26 - "htmx-1.9.12.min.js"
Cohesion: 0.08
Nodes (104): A(), ae(), ar(), at(), B(), be(), br(), bt() (+96 more)

### Community 27 - "Ревью Ш-02. ADR по допущениям"
Cohesion: 0.40
Nodes (4): Замечания, Остаётся, Ревью Ш-02. ADR по допущениям, Что проверено

### Community 28 - "options"
Cohesion: 0.40
Nodes (5): iOS, options, bundleIdPrefix, deploymentTarget, developmentLanguage

### Community 29 - "JolTests"
Cohesion: 0.40
Nodes (5): platform, settings, sources, type, JolTests

### Community 30 - "MapLibre"
Cohesion: 0.50
Nodes (4): exactVersion, url, packages, MapLibre

### Community 34 - "save_place"
Cohesion: 0.21
Nodes (13): check_event_refs(), clean_text(), _norm(), parse_bool(), save_place(), validate_category(), validate_event(), text() (+5 more)

### Community 35 - "test_osm_pipeline.py"
Cohesion: 0.31
Nodes (6): collect(), keys(), q(), test_collect_drops_outer_way_and_duplicate_node(), test_load_into_db_and_idempotent(), test_preexisting_duplicate_rows_are_merged_without_losing_data()

### Community 36 - "routing/service.py"
Cohesion: 0.07
Nodes (20): directions(), RoutingProvider, calculate_cost(), load_tariffs(), recommend(), _recommendation_rank(), Tariff, AlmatyPoint (+12 more)

### Community 37 - "Ревью Ш-07, Ш-08, Ш-09. Данные мест"
Cohesion: 0.33
Nodes (5): Замечания, Отклонения модели данных от `TECH_PLAN.md §5`, Ревью Ш-07, Ш-08, Ш-09. Данные мест, Что проверено ревьюером, Что сделано

### Community 38 - "test_admin_validation.py"
Cohesion: 0.36
Nodes (8): validate_place(), validate_storage_key(), place_form(), test_place_needs_a_name(), test_place_ok_and_empty_strings_become_none(), test_place_rejects_bad_numbers_and_enums(), test_place_text_length_limit(), test_storage_key()

### Community 39 - "admin/api.py"
Cohesion: 0.11
Nodes (61): admin_get(), admin_post(), AdminError, AdminLoginRequired, categories_list(), category_edit(), _category_options(), category_save() (+53 more)

### Community 40 - "test_admin.py"
Cohesion: 0.13
Nodes (36): place_form_values(), get_place(), fetch_one(), add_category(), add_place(), csrf_of(), logged_in(), login() (+28 more)

### Community 41 - "auth.py"
Cohesion: 0.12
Nodes (15): csrf_for_session(), hash_password(), login(), LoginResult, new_token(), normalize_email(), password_error(), tokens_equal() (+7 more)

### Community 42 - "representative_point"
Cohesion: 0.23
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 43 - "fetch_all"
Cohesion: 0.06
Nodes (49): Замечания, Ревью Ш-17. API мест (+ серверная часть Ш-19), Статус шагов, Что проверено ревьюером, Что сделано, fetch_all(), _geojson(), get_curated_route() (+41 more)

### Community 44 - "transit.py"
Cohesion: 0.11
Nodes (13): _candidates(), find_transit_options(), get_network(), _in_service(), _line_key(), _local_hour(), _materialize(), _ride_leg() (+5 more)

### Community 45 - "import_transit.py"
Cohesion: 0.10
Nodes (19): database_url(), apply_manual_stops(), build_network(), extract(), haversine_m(), load_seed(), localized_names(), main() (+11 more)

### Community 46 - "schemas.py"
Cohesion: 0.18
Nodes (16): CategoriesList, Category, CategoryRef, CuratedRouteDetail, CuratedRouteItem, CuratedRoutesList, CuratedRouteSummary, DayHours (+8 more)

### Community 47 - "time"
Cohesion: 0.20
Nodes (10): format_hours_day(), parse_hours_day(), _parse_time(), validate_hours(), group_hours(), test_format_hours_roundtrip(), test_hours_day_errors(), test_hours_day_multiple_intervals_sorted() (+2 more)

### Community 48 - "MapView"
Cohesion: 0.18
Nodes (3): MapView, Coordinator, Ф3. Карта

### Community 49 - "test_transit_search.py"
Cohesion: 0.06
Nodes (52): hop_speed_boost(), airport_routes(), build_network(), bus(), ride_from_terminal(), test_airport_real_pbf(), test_airport_real_valhalla(), find() (+44 more)

### Community 50 - "psycopg"
Cohesion: 0.05
Nodes (44): _bool(), CsvError, import_csv(), _int(), link_manual_to_osm(), _opt(), parse_rows(), database_url() (+36 more)

### Community 51 - "MapView.swift"
Cohesion: 0.33
Nodes (3): CoreLocation, AlmatyCamera, MapLibre

### Community 53 - "Ревью Ш-10. Админка (минимум)"
Cohesion: 0.33
Nodes (5): Безопасность — проверено ревьюером, Замечания, Изменения модели данных vs `TECH_PLAN.md §5`, Ревью Ш-10. Админка (минимум), Что сделано

### Community 54 - "db.py"
Cohesion: 0.14
Nodes (5): client(), recreate_database(), scratch_db_url(), test_db_url(), TransactionalDatabase

### Community 55 - "typing"
Cohesion: 0.12
Nodes (17): Что сделано, check_mode(), Maneuver, MatrixResult, NoRoute, RouteResult, RoutingError, RoutingUnavailable (+9 more)

### Community 56 - "pathlib"
Cohesion: 0.18
Nodes (8): 1. Сборка тайлов (Ш-11), 2. Локальный просмотр (демо), 3. Хостинг, 4. Стили (Ш-12), maps/ — карта Jol (Ш-11, Ш-12), build(), interp(), name_expr()

### Community 57 - "dedupe.py"
Cohesion: 0.19
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 58 - "get_settings"
Cohesion: 0.11
Nodes (9): get_settings(), Settings, JsonFormatter, setup_logging(), create_app(), lifespan(), RequestIdMiddleware, meta() (+1 more)

### Community 59 - "Jol — технический план (ТЗ на реализацию)"
Cohesion: 0.20
Nodes (10): 10. Риски, которые держим в голове, 1. Цель первой версии (v1) и границы, 2. Рабочие допущения по открытым вопросам, 3. Архитектура, 4. Структура репозитория, 5. Модель данных (черновик, уточняется в шагах), 6. API (черновик), 7. Порядок фаз и вехи (+2 more)

### Community 60 - "FakeRouter"
Cohesion: 0.31
Nodes (4): FakeRouter, haversine_m(), make_router(), test_fake_route_speeds_and_order()

### Community 61 - "test_directions.py"
Cohesion: 0.13
Nodes (16): encode_polyline6(), decode_polyline6(), TransitLeg, directions_api(), StubDatabase, test_directions_contract_and_almaty_tariff_date(), test_directions_empty_vs_unavailable(), test_directions_motor_range_for_local_departure() (+8 more)

### Community 63 - "Jol — передача работы (2026-11-21)"
Cohesion: 0.22
Nodes (6): Jol — передача работы (2026-11-21), Незакоммиченное, Нужно от владельца, Окружение (этот Mac), Статус плана, Что делать дальше

### Community 64 - "Ревью доработки Ш-08: отношения OSM и связь ручных мест"
Cohesion: 0.40
Nodes (4): Замечания, Ревью доработки Ш-08: отношения OSM и связь ручных мест, Что проверено ревьюером, Что сделано

### Community 65 - "upsert.py"
Cohesion: 0.29
Nodes (3): _as_list(), upsert_place(), test_upsert_place_is_exported()

### Community 66 - "Ревью Ш-22. Стоимость и сводка вариантов"
Cohesion: 0.33
Nodes (6): API маршрутов, Аэропорт, Повторное ревью на локальных сервисах, Предыдущая проверка без доступа к сервисам, Ревью Ш-22. Стоимость и сводка вариантов, Тарифы

### Community 71 - "sessions.py"
Cohesion: 0.15
Nodes (15): logout(), me(), refresh(), RefreshRequest, current_user(), digest(), revoke(), rotate() (+7 more)

### Community 76 - "Ревью Ш-20. Движок маршрутизации (Valhalla)"
Cohesion: 0.40
Nodes (4): CI, Замечания, Реальные замеры, Ревью Ш-20. Движок маршрутизации (Valhalla)

### Community 77 - "Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)"
Cohesion: 0.40
Nodes (4): Замечания, Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20), Что сделано, Эталонные пары (лучший вариант)

### Community 80 - "admin/service.py"
Cohesion: 0.15
Nodes (14): add_route_place(), like_pattern(), list_places(), move_route_item(), page_number(), parse_int(), parse_local_dt(), parse_uuid() (+6 more)

## Knowledge Gaps
- **15 isolated node(s):** `Jol`, `jol-server`, `MapLibre`, `Foundation`, `Authentication (email OTP, Sign in with Apple, SMS OTP)` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 446 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `merge_place()` connect `merge_place` to `psycopg`, `import_places.py`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Are the 50 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 50 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Jol`, `jol-server`, `MapLibre` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Personal Route Building (whole trip, by day)` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `Jol — технический план (ТЗ на реализацию)` connect `Jol — технический план (ТЗ на реализацию)` to `merge_place`, `8. Шаги`, `Jol — передача работы (2026-11-21)`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Should `worker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09302325581395349 - nodes in this community are weakly interconnected._
- **Why does `0. Правила исполнения` connect `merge_place` to `Jol — технический план (ТЗ на реализацию)`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._