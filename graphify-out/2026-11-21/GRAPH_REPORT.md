# Graph Report - Jol v2  (2026-11-21)

## Corpus Check
- 109 files · ~56,889 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: (none) 6, .csv 2, .example 1)

## Summary
- 1172 nodes · 2773 edges · 58 communities (49 shown, 9 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 187 edges (avg confidence: 0.85)
- Token cost: 211,973 input · 0 output

## Community Hubs (Navigation)
- Personal Route Building (whole trip, by day)
- worker.py
- JolApp
- pytest
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
- test_osm_pipeline.py
- worker.py
- Ревью Ш-07, Ш-08, Ш-09. Данные мест
- RequestIdMiddleware
- admin/api.py
- test_admin.py
- auth.py
- representative_point
- test_places_api.py
- schemas.py
- upsert.py
- MapView
- Coordinator
- MapView.swift
- Ревью Ш-10. Админка (минимум)
- conftest.py
- test_routing.py
- pathlib
- dedupe.py
- Jol — технический план (ТЗ на реализацию)
- Ревью доработки Ш-08: отношения OSM и связь ручных мест

## God Nodes (most connected - your core abstractions)
1. `fetch_one()` - 67 edges
2. `conn()` - 45 edges
3. `fetch_all()` - 35 edges
4. `db()` - 33 edges
5. `re()` - 32 edges
6. `oe()` - 31 edges
7. `execute()` - 30 edges
8. `ae()` - 27 edges
9. `render()` - 25 edges
10. `He()` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Ф3. Карта` --references--> `MapView`  [INFERRED]
  TECH_PLAN.md → ios/Jol/Features/Map/MapView.swift
- `Что сделано` --references--> `MapView`  [INFERRED]
  docs/reviews/Ш-13.md → ios/Jol/Features/Map/MapView.swift
- `Что проверено ревьюером` --references--> `is_open_now()`  [INFERRED]
  docs/reviews/Ш-17.md → server/app/places/service.py
- `Что сделано` --references--> `RoutingProvider`  [INFERRED]
  docs/reviews/Ш-20.md → server/app/routing/base.py
- `Что сделано` --references--> `FakeRouter`  [INFERRED]
  docs/reviews/Ш-20.md → server/app/routing/fake.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crowdsourced Data and Bonus Flow** — jol_ssot_user_content, jol_ssot_content_moderation, jol_ssot_bonus_system, jol_ssot_demand_coefficient [EXTRACTED 1.00]
- **Living Plan Adaptation Loop** — jol_ssot_principle_living_plan, jol_ssot_weather_recheck, jol_ssot_mountain_morning_alert, jol_ssot_place_crowding, jol_ssot_open_meteo [EXTRACTED 1.00]
- **Route Building Inputs** — jol_ssot_route_building, jol_ssot_trip_budget, jol_ssot_mandatory_wishes, jol_ssot_crowd_tolerance, jol_ssot_memory_personalization [EXTRACTED 1.00]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]

## Communities (58 total, 9 thin omitted)

### Community 0 - "Personal Route Building (whole trip, by day)"
Cohesion: 0.06
Nodes (46): Jol Project Instructions (CLAUDE.md), Almaty Launch Geography, Authentication (email OTP, Sign in with Apple, SMS OTP), Bonus System (1 bonus = ~1 tenge), Bookings and Orders via Partner APIs, Dynamic Single-Branch Chat Graph, Content Verification (auto-filter + moderation), Crowd Tolerance Preference (+38 more)

### Community 1 - "worker.py"
Cohesion: 0.16
Nodes (11): Database, _main(), process_batch(), run_worker(), clean_handlers(), db(), test_each_job_runs_exactly_once_with_two_parallel_workers(), one_worker() (+3 more)

### Community 2 - "JolApp"
Cohesion: 0.22
Nodes (5): JolApp, .body, MapScreen, .body, SwiftUI

### Community 3 - "pytest"
Cohesion: 0.06
Nodes (32): _bool(), CsvError, import_csv(), _int(), link_manual_to_osm(), _opt(), parse_rows(), database_url() (+24 more)

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
Cohesion: 0.10
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
Cohesion: 0.13
Nodes (12): build_record(), database_url(), extract(), find_pbf(), in_bbox(), load(), main(), merge_dropped() (+4 more)

### Community 15 - ".swiftlint.yml"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 16 - "tag_mapping.py"
Cohesion: 0.20
Nodes (12): category_for_food(), category_slug(), classify(), _clean(), _has_wiki(), parse_elevation(), pick_address(), pick_names() (+4 more)

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
Cohesion: 0.13
Nodes (13): _parse_days(), _parse_intervals(), parse_opening_hours(), _to_time(), record(), test_hours_simple(), test_hours_unparsed(), test_hours_variants() (+5 more)

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

### Community 35 - "test_osm_pipeline.py"
Cohesion: 0.31
Nodes (6): collect(), keys(), q(), test_collect_drops_outer_way_and_duplicate_node(), test_load_into_db_and_idempotent(), test_preexisting_duplicate_rows_are_merged_without_losing_data()

### Community 36 - "worker.py"
Cohesion: 0.16
Nodes (7): backoff_seconds(), _cleanup_done_jobs(), enqueue(), enqueue_due_schedules(), register(), Schedule, test_schedule_enqueues_once_per_slot_even_when_called_twice()

### Community 37 - "Ревью Ш-07, Ш-08, Ш-09. Данные мест"
Cohesion: 0.33
Nodes (5): Замечания, Отклонения модели данных от `TECH_PLAN.md §5`, Ревью Ш-07, Ш-08, Ш-09. Данные мест, Что проверено ревьюером, Что сделано

### Community 38 - "RequestIdMiddleware"
Cohesion: 0.15
Nodes (3): JsonFormatter, setup_logging(), RequestIdMiddleware

### Community 39 - "admin/api.py"
Cohesion: 0.08
Nodes (80): admin_get(), admin_post(), AdminError, AdminLoginRequired, categories_list(), category_edit(), _category_options(), category_save() (+72 more)

### Community 40 - "test_admin.py"
Cohesion: 0.12
Nodes (37): place_form_values(), get_place(), fetch_one(), add_category(), add_place(), csrf_of(), logged_in(), login() (+29 more)

### Community 41 - "auth.py"
Cohesion: 0.06
Nodes (37): csrf_for_session(), hash_password(), hash_token(), login(), LoginResult, logout(), new_token(), normalize_email() (+29 more)

### Community 42 - "representative_point"
Cohesion: 0.23
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 43 - "test_places_api.py"
Cohesion: 0.06
Nodes (49): Замечания, Ревью Ш-17. API мест (+ серверная часть Ш-19), Статус шагов, Что проверено ревьюером, Что сделано, AppError, _geojson(), get_curated_route() (+41 more)

### Community 46 - "schemas.py"
Cohesion: 0.17
Nodes (16): CategoriesList, Category, CategoryRef, CuratedRouteDetail, CuratedRouteItem, CuratedRoutesList, CuratedRouteSummary, DayHours (+8 more)

### Community 47 - "upsert.py"
Cohesion: 0.29
Nodes (3): _as_list(), upsert_place(), test_upsert_place_is_exported()

### Community 51 - "MapView.swift"
Cohesion: 0.33
Nodes (3): CoreLocation, AlmatyCamera, MapLibre

### Community 53 - "Ревью Ш-10. Админка (минимум)"
Cohesion: 0.33
Nodes (5): Безопасность — проверено ревьюером, Замечания, Изменения модели данных vs `TECH_PLAN.md §5`, Ревью Ш-10. Админка (минимум), Что сделано

### Community 54 - "conftest.py"
Cohesion: 0.11
Nodes (10): get_settings(), Settings, create_app(), lifespan(), meta(), client(), recreate_database(), scratch_db_url() (+2 more)

### Community 55 - "test_routing.py"
Cohesion: 0.05
Nodes (45): CI, Замечания, Реальные замеры, Ревью Ш-20. Движок маршрутизации (Valhalla), Что сделано, check_mode(), Maneuver, MatrixResult (+37 more)

### Community 56 - "pathlib"
Cohesion: 0.16
Nodes (8): 1. Сборка тайлов (Ш-11), 2. Локальный просмотр (демо), 3. Хостинг, 4. Стили (Ш-12), maps/ — карта Jol (Ш-11, Ш-12), build(), interp(), name_expr()

### Community 57 - "dedupe.py"
Cohesion: 0.19
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 59 - "Jol — технический план (ТЗ на реализацию)"
Cohesion: 0.17
Nodes (11): 0. Правила исполнения, 10. Риски, которые держим в голове, 1. Цель первой версии (v1) и границы, 2. Рабочие допущения по открытым вопросам, 3. Архитектура, 4. Структура репозитория, 5. Модель данных (черновик, уточняется в шагах), 6. API (черновик) (+3 more)

### Community 64 - "Ревью доработки Ш-08: отношения OSM и связь ручных мест"
Cohesion: 0.40
Nodes (4): Замечания, Ревью доработки Ш-08: отношения OSM и связь ручных мест, Что проверено ревьюером, Что сделано

## Knowledge Gaps
- **15 isolated node(s):** `Foundation`, `Jol`, `jol-server`, `MapLibre`, `Authentication (email OTP, Sign in with Apple, SMS OTP)` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 374 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `fetch_one()` connect `test_admin.py` to `worker.py`, `worker.py`, `admin/api.py`, `auth.py`, `test_places_api.py`, `test_osm_import.py`, `conftest.py`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 42 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 42 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Foundation`, `Jol`, `jol-server` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Personal Route Building (whole trip, by day)` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `is_open_now()` connect `test_places_api.py` to `auth.py`, `worker.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Should `pytest` be split into smaller, more focused modules?**
  _Cohesion score 0.06153846153846154 - nodes in this community are weakly interconnected._
- **Why does `conn()` connect `admin/api.py` to `worker.py`, `pytest`, `test_admin.py`, `test_places_api.py`, `import_places.py`, `conftest.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._