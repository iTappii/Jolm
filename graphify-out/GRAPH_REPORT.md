# Graph Report - Jol v2  (2026-11-21)

## Corpus Check
- 295 files · ~161,032 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 25 file(s) not represented in the graph (top: (none) 6, .csv 4, .xcstrings 3)

## Summary
- 3511 nodes · 9612 edges · 167 communities (128 shown, 39 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 801 edges (avg confidence: 0.89)
- Token cost: 211,973 input · 0 output

## Graph Freshness
- Built from commit: `eaedf976`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Personal Route Building (whole trip, by day)
- worker.py
- Foundation
- Jol — передача работы (2026-11-21)
- 8. Шаги
- Jol Logo (PNG + SVG)
- App Icon (PNG)
- App Icon (SVG)
- apple.py
- CLAUDE.md
- server
- build.py
- 0001. Технологический стек
- postgres
- import_places.py
- .swiftlint.yml
- tag_mapping.py
- Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас
- Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol
- base
- edit.py
- Jol
- JolUITests
- project.yml
- Jol
- App
- htmx-1.9.12.min.js
- Ревью Ш-02. ADR по допущениям
- options
- JolTests
- MapLibre
- build_tiles.sh
- jol-server
- admin/service.py
- merge_place
- routing/service.py
- Ревью Ш-07, Ш-08, Ш-09. Данные мест
- budget.py
- admin/api.py
- test_admin.py
- Sendable
- representative_point
- test_places_api.py
- transit.py
- import_transit.py
- get_settings
- test_transit_search.py
- MapCoordinator
- pytest
- test_transit_import.py
- test_otp.py
- Ревью Ш-10. Админка (минимум)
- fetch_all
- typing
- pathlib
- dedupe.py
- otp_api.py
- Jol — технический план (ТЗ на реализацию)
- FakeRouter
- test_directions.py
- test_chat.py
- Ревью доработки Ш-08: отношения OSM и связь ручных мест
- import_popular.py
- .install
- test_llm.py
- fetch_pbf.sh
- README.md
- SessionTokens
- execute
- TECH_PLAN.md
- test_apple.py
- psycopg
- test_chat_guest.py
- send_message
- chat/api.py
- edit_tools.py
- layout.py
- PlacesModel
- View
- APIError
- test_airport.py
- Ревью Ш-20. Движок маршрутизации (Valhalla)
- test_trip_edits.py
- test_planner_budget.py
- trips/api.py
- test_planner_layout.py
- test_weather.py
- entitlements
- ServerMeta
- deps.py
- test_planner_scoring.py
- llm/__init__.py
- brief.py
- AppLanguage
- CodingKeys
- Place
- SwiftUI
- APIClient
- test_account_deletion.py
- apple_grants.py
- places/schemas.py
- HaversineMatrix
- select_candidates
- candidates.py
- HomeScreenUITests
- tools.py
- read.py
- open_meteo.py
- ChatPanel
- scoring.py
- View
- SmsProvider
- CuratedRoutesSheet
- XCTestCase
- ForecastView
- errors.py
- .stream
- PlaceCardSheet
- Ревью Ш-33 — отбор кандидатов
- PlacesService
- .today
- CodingKeys
- PlaceCategoryStyle
- SignInEntryView
- pool_sizes
- DeleteState
- Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта
- Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки
- resolve
- DetailState
- ListState
- Ревью Ш-17. API мест (+ серверная часть Ш-19)
- .__call__
- Metrics.swift
- TransactionalDatabase
- PlacesTests
- weather/__init__.py

## God Nodes (most connected - your core abstractions)
1. `fetch_one()` - 144 edges
2. `fetch_all()` - 104 edges
3. `conn()` - 82 edges
4. `Step` - 67 edges
5. `execute()` - 67 edges
6. `get_settings()` - 61 edges
7. `AppError` - 58 edges
8. `Place` - 42 edges
9. `sign_in()` - 39 edges
10. `APIClient` - 39 edges

## Surprising Connections (you probably didn't know these)
- `Как работаем` --references--> `merge_place()`  [INFERRED]
  docs/HANDOFF.md → data/osm/merge.py
- `Ревью координатора (2026-11-21)` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-36.md → data/osm/merge.py
- `Ревью координатора (2026-11-21)` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-38.md → data/osm/merge.py
- `0. Правила исполнения` --references--> `merge_place()`  [INFERRED]
  TECH_PLAN.md → data/osm/merge.py
- `Проверки` --references--> `PlacesUITests`  [INFERRED]
  docs/reviews/Ш-19.md → ios/JolUITests/PlacesUITests.swift

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crowdsourced Data and Bonus Flow** — jol_ssot_user_content, jol_ssot_content_moderation, jol_ssot_bonus_system, jol_ssot_demand_coefficient [EXTRACTED 1.00]
- **Living Plan Adaptation Loop** — jol_ssot_principle_living_plan, jol_ssot_weather_recheck, jol_ssot_mountain_morning_alert, jol_ssot_place_crowding, jol_ssot_open_meteo [EXTRACTED 1.00]
- **Route Building Inputs** — jol_ssot_route_building, jol_ssot_trip_budget, jol_ssot_mandatory_wishes, jol_ssot_crowd_tolerance, jol_ssot_memory_personalization [EXTRACTED 1.00]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]

## Communities (167 total, 39 thin omitted)

### Community 0 - "Personal Route Building (whole trip, by day)"
Cohesion: 0.06
Nodes (46): Jol Project Instructions (CLAUDE.md), Almaty Launch Geography, Authentication (email OTP, Sign in with Apple, SMS OTP), Bonus System (1 bonus = ~1 tenge), Bookings and Orders via Partner APIs, Dynamic Single-Branch Chat Graph, Content Verification (auto-filter + moderation), Crowd Tolerance Preference (+38 more)

### Community 1 - "worker.py"
Cohesion: 0.06
Nodes (30): move_route_item(), Database, fetch_one(), _apple_revoke(), backoff_seconds(), _cleanup_done_jobs(), enqueue(), enqueue_due_schedules() (+22 more)

### Community 2 - "Foundation"
Cohesion: 0.08
Nodes (10): CoreLocation, Foundation, FixtureURLProtocol, UITestSupport, .isStubbed, .placesJSON, .routeJSON, .routesJSON (+2 more)

### Community 3 - "Jol — передача работы (2026-11-21)"
Cohesion: 0.25
Nodes (7): Jol — передача работы (2026-11-21), Как работаем, Коммиты, Нужно от владельца, Окружение (этот Mac), Статус плана, Что делать дальше

### Community 4 - "8. Шаги"
Cohesion: 0.12
Nodes (16): 8. Шаги, Ф0. Основа проекта, Ф10. Готовый маршрут в приложении (SSOT §11.3), Ф12. Память (SSOT §8), Ф13. Скачивание, история, боковая панель, Ф14. Пользовательский контент и бонусы (SSOT §10), Ф15. Загруженность (SSOT §7.3) `[предложено, §2 п.5]`, Ф16. Мероприятия и бронирования (+8 more)

### Community 5 - "Jol Logo (PNG + SVG)"
Cohesion: 0.38
Nodes (7): Orange and Black Palette, Jol Logo, Jol Logo, Orange and Black Palette, Road Underline Bar, Road Underline Motif, Jol Wordmark

### Community 6 - "App Icon (PNG)"
Cohesion: 0.67
Nodes (4): Jol App Icon (1024px), Jol Wordmark, Orange Brand Color, Underline Bar Motif

### Community 7 - "App Icon (SVG)"
Cohesion: 0.67
Nodes (4): Jol App Icon, Orange and Black Palette, Road Underline Bar Motif, Jol Wordmark (J-o-l)

### Community 8 - "apple.py"
Cohesion: 0.09
Nodes (9): AppleSignIn, Challenge, JsonFormatter, setup_logging(), create_app(), lifespan(), RequestIdMiddleware, meta() (+1 more)

### Community 10 - "server"
Cohesion: 0.07
Nodes (26): DATABASE_URL, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, TEST_DATABASE_URL, jobs, server, name (+18 more)

### Community 11 - "build.py"
Cohesion: 0.06
Nodes (36): SSE `route_ready` (точная форма), Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-36 — сборка в поездку (`build_trip`), `POST /v1/trips/{id}/items/{item_id}/remove`  тело необязательно: `{"force": false}`, `POST /v1/trips/{id}/items/{item_id}/replace`  `{"place_id"? | "category"? | "query"?, "force"?}`, REST (+28 more)

### Community 12 - "0001. Технологический стек"
Cohesion: 0.12
Nodes (14): 0001. Технологический стек, Контекст, Последствия, Решение, Ссылки, 0002. «ИИ понимает, движок планирует», Контекст, Последствия (+6 more)

### Community 13 - "postgres"
Cohesion: 0.06
Nodes (34): build_admins, build_elevation, build_tar, build_time_zones, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, serve_tiles (+26 more)

### Community 14 - "import_places.py"
Cohesion: 0.12
Nodes (14): build_record(), collect(), database_url(), extract(), find_pbf(), load(), main(), merge_dropped() (+6 more)

### Community 15 - ".swiftlint.yml"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 16 - "tag_mapping.py"
Cohesion: 0.09
Nodes (25): _parse_days(), _parse_intervals(), parse_opening_hours(), _to_time(), category_for_food(), category_slug(), classify(), _clean() (+17 more)

### Community 17 - "Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас"
Cohesion: 0.33
Nodes (5): Замечания, Не проверено, Отклонения от плана (приняты как временные), Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас, Что проверено

### Community 18 - "Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol"
Cohesion: 0.33
Nodes (5): Замечания, Интеграция (сделано ревьюером), Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol, Что проверено ревьюером, Что сделано

### Community 19 - "base"
Cohesion: 0.22
Nodes (9): ASSETCATALOG_COMPILER_APPICON_NAME, CURRENT_PROJECT_VERSION, GENERATE_INFOPLIST_FILE, INFOPLIST_FILE, MARKETING_VERSION, PRODUCT_BUNDLE_IDENTIFIER, SWIFT_VERSION, TARGETED_DEVICE_FAMILY (+1 more)

### Community 20 - "edit.py"
Cohesion: 0.10
Nodes (31): Ревью координатора (2026-11-21), Что сделано, KeptStop, RetimedDay, Place, place_from_row(), _apply_retime(), budget_summary() (+23 more)

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

### Community 25 - "App"
Cohesion: 0.11
Nodes (11): JolApp, .body, RootView, .body, .content, Navigator, App, appleMaps (+3 more)

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

### Community 34 - "admin/service.py"
Cohesion: 0.07
Nodes (45): add_route_place(), check_event_refs(), clean_text(), format_hours_day(), like_pattern(), list_places(), _norm(), page_number() (+37 more)

### Community 35 - "merge_place"
Cohesion: 0.11
Nodes (14): merge_place(), Замечания, Ревью доработки Ш-08: дедупликация мест OSM, Что сделано, Что сделано, keys(), q(), sconn() (+6 more)

### Community 36 - "routing/service.py"
Cohesion: 0.06
Nodes (24): leg_seconds(), pick_default(), directions(), NoRoute, RouteResult, RoutingProvider, calculate_cost(), load_tariffs() (+16 more)

### Community 37 - "Ревью Ш-07, Ш-08, Ш-09. Данные мест"
Cohesion: 0.33
Nodes (5): Замечания, Отклонения модели данных от `TECH_PLAN.md §5`, Ревью Ш-07, Ш-08, Ш-09. Данные мест, Что проверено ревьюером, Что сделано

### Community 38 - "budget.py"
Cohesion: 0.10
Nodes (29): Что сделано, _cheaper_replacement(), cheaper_variant(), choose_lodging(), Costs, drop_variant(), _in_pool_order(), layout_centre() (+21 more)

### Community 39 - "admin/api.py"
Cohesion: 0.06
Nodes (84): admin_get(), admin_post(), AdminError, AdminLoginRequired, categories_list(), category_edit(), _category_options(), category_save() (+76 more)

### Community 40 - "test_admin.py"
Cohesion: 0.15
Nodes (31): place_form_values(), get_place(), add_category(), add_place(), csrf_of(), logged_in(), login(), make_admin() (+23 more)

### Community 41 - "Sendable"
Cohesion: 0.10
Nodes (34): MeInfo, .identity, CuratedRouteDetail, .stops, CuratedRoutesList, CuratedRouteStop, CodingKeys, ord (+26 more)

### Community 42 - "representative_point"
Cohesion: 0.23
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 43 - "test_places_api.py"
Cohesion: 0.15
Nodes (25): is_open_now(), add_place(), at(), make_route(), set_names(), test_categories(), test_curated_routes_published_only(), test_open_now_across_midnight() (+17 more)

### Community 44 - "transit.py"
Cohesion: 0.10
Nodes (14): RoutingError, _candidates(), find_transit_options(), get_network(), _in_service(), _line_key(), _local_hour(), _materialize() (+6 more)

### Community 45 - "import_transit.py"
Cohesion: 0.10
Nodes (19): in_bbox(), apply_manual_stops(), build_network(), extract(), haversine_m(), load_seed(), localized_names(), main() (+11 more)

### Community 46 - "get_settings"
Cohesion: 0.14
Nodes (13): get_sms_provider(), normalize_phone(), _StubSmsProvider, get_settings(), signing_secret(), signing_secret(), test_invalid_phone(), test_normalize_phone() (+5 more)

### Community 47 - "test_transit_search.py"
Cohesion: 0.19
Nodes (20): hop_speed_boost(), build(), _load(), _load_dev_network(), run(), search(), stop_row(), test_best_of_each_mode_is_kept() (+12 more)

### Community 48 - "MapCoordinator"
Cohesion: 0.12
Nodes (5): MapCoordinator, Layer, MapView, MapLibre, Ф3. Карта

### Community 49 - "pytest"
Cohesion: 0.11
Nodes (22): parse_bbox(), make_router(), test_parse_bbox_ok(), test_parse_bbox_rejects(), load(), _router(), run(), test_client_error_mapping() (+14 more)

### Community 50 - "test_transit_import.py"
Cohesion: 0.14
Nodes (13): sconn(), by_rel(), network(), rows(), sconn(), test_empty_extract_does_not_wipe_network(), test_metro_directions_share_stations(), test_migration_constraints() (+5 more)

### Community 51 - "test_otp.py"
Cohesion: 0.06
Nodes (23): Замечания (не исправлены, записаны), Проверки, Ревью Ш-25 — вход по почте (код), Что сделано, AppleKeyCache, fetch_keys(), DevEmailProvider, EmailProvider (+15 more)

### Community 53 - "Ревью Ш-10. Админка (минимум)"
Cohesion: 0.33
Nodes (5): Безопасность — проверено ревьюером, Замечания, Изменения модели данных vs `TECH_PLAN.md §5`, Ревью Ш-10. Админка (минимум), Что сделано

### Community 54 - "fetch_all"
Cohesion: 0.16
Nodes (32): fetch_all(), brief_call(), build(), day(), event(), items(), over_budget_trip(), pick() (+24 more)

### Community 55 - "typing"
Cohesion: 0.14
Nodes (14): MatrixResult, RoutingUnavailable, _costing_body(), _loc(), parse_matrix(), ValhallaRouter, test_directions_partial_engine_failure(), route() (+6 more)

### Community 56 - "pathlib"
Cohesion: 0.09
Nodes (11): database_url(), main(), 1. Сборка тайлов (Ш-11), 2. Локальный просмотр (демо), 3. Хостинг, 4. Стили (Ш-12), maps/ — карта Jol (Ш-11, Ш-12), H (+3 more)

### Community 57 - "dedupe.py"
Cohesion: 0.19
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 58 - "otp_api.py"
Cohesion: 0.12
Nodes (8): _client_ip(), OtpRequest, OtpVerifyRequest, request_code(), verify_code(), pick_locale(), test_health_db_down_returns_503_uniform_error(), test_pick_locale()

### Community 59 - "Jol — технический план (ТЗ на реализацию)"
Cohesion: 0.20
Nodes (10): 0. Правила исполнения, 10. Риски, которые держим в голове, 1. Цель первой версии (v1) и границы, 3. Архитектура, 4. Структура репозитория, 5. Модель данных (черновик, уточняется в шагах), 6. API (черновик), 7. Порядок фаз и вехи (+2 more)

### Community 60 - "FakeRouter"
Cohesion: 0.13
Nodes (16): Замечания, Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20), Что сделано, Эталонные пары (лучший вариант), API маршрутов, Аэропорт, Повторное ревью на локальных сервисах, Предыдущая проверка без доступа к сервисам (+8 more)

### Community 61 - "test_directions.py"
Cohesion: 0.11
Nodes (17): Maneuver, encode_polyline6(), decode_polyline6(), TransitLeg, TransitOption, parse_route(), directions_api(), StubDatabase (+9 more)

### Community 63 - "test_chat.py"
Cohesion: 0.19
Nodes (37): Step, call(), day(), new_chat(), open_stream(), say(), sign_in(), StallingLLM (+29 more)

### Community 64 - "Ревью доработки Ш-08: отношения OSM и связь ручных мест"
Cohesion: 0.40
Nodes (4): Замечания, Ревью доработки Ш-08: отношения OSM и связь ручных мест, Что проверено ревьюером, Что сделано

### Community 65 - "import_popular.py"
Cohesion: 0.14
Nodes (19): _bool(), CsvError, import_csv(), _int(), link_manual_to_osm(), _opt(), parse_rows(), _csv() (+11 more)

### Community 66 - ".install"
Cohesion: 0.08
Nodes (6): APIClientTests, ClearedFlag, .value, ProfileTests, StubURLProtocol, .requests

### Community 67 - "test_llm.py"
Cohesion: 0.16
Nodes (27): collect(), ErrorEvent, LLMError, LLMTimeout, FakeLLM, ResilientLLM, BriefUpdate, events() (+19 more)

### Community 70 - "SessionTokens"
Cohesion: 0.10
Nodes (9): EphemeralTokenStore, SessionStore, .query, SessionTokens, CodingKeys, accessToken, refreshToken, MemoryTokenStore (+1 more)

### Community 71 - "execute"
Cohesion: 0.12
Nodes (20): delete_account(), challenge(), sign_in(), verify_identity(), _digest(), issue(), _latest(), _lock() (+12 more)

### Community 72 - "TECH_PLAN.md"
Cohesion: 0.05
Nodes (31): Замечания, Повторная проверка — 2026-11-21, Ревью Ш-13. iOS: проект и карта, Что проверено ревьюером, Что сделано, Чтобы закрыть шаг, Замечания и отложенное, Ревью координатора (2026-11-21) (+23 more)

### Community 73 - "test_apple.py"
Cohesion: 0.26
Nodes (11): apple_jwks(), get_nonce(), issue(), private_key(), submit(), test_invalid_signature_does_not_consume_challenge(), test_outage_is_rate_limited(), test_rejects_expired_nonce_and_wrong_algorithm_before_fetch() (+3 more)

### Community 74 - "psycopg"
Cohesion: 0.10
Nodes (18): apply_migrations(), checksum_of(), discover(), main(), MigrationError, Проверки, chat_env(), client() (+10 more)

### Community 75 - "test_chat_guest.py"
Cohesion: 0.16
Nodes (25): SlidingWindowLimiter, FakeToolCall, parse_sse(), post(), test_bad_tool_arguments_come_back_as_a_tool_error(), test_failure_after_text_keeps_the_text_and_sends_no_done(), test_guest_chat_writes_nothing_to_the_database(), test_history_at_the_limits_is_accepted() (+17 more)

### Community 76 - "send_message"
Cohesion: 0.09
Nodes (31): Что сделано, _chat_json(), create_chat(), CreateChat, _finish(), get_chat(), lease_sec(), list_chats() (+23 more)

### Community 77 - "chat/api.py"
Cohesion: 0.07
Nodes (20): error_payload(), run_turn(), TurnRecord, ChatTurn, guest_chat(), frames(), handle_tool(), GuestChatRequest (+12 more)

### Community 78 - "edit_tools.py"
Cohesion: 0.14
Nodes (21): _add_graph_node(), _build_trip(), _search_places(), handle_tool(), _update_trip_brief(), _after_edit(), _chat_trip(), get_trip_plan() (+13 more)

### Community 79 - "layout.py"
Cohesion: 0.08
Nodes (34): Что сделано, _assign_activities(), assign(), best_day(), item_for(), _assign_meals(), _at(), _centroid() (+26 more)

### Community 80 - "PlacesModel"
Cohesion: 0.11
Nodes (9): .body, GeoBounds, .height, .queryValue, .width, PlacesModel, .routeStops, RouteBar (+1 more)

### Community 83 - "View"
Cohesion: 0.16
Nodes (7): JolFont, PlaceCardView, .detail, .failedRow, .openChip, PlacePhotoView, .body

### Community 84 - "APIError"
Cohesion: 0.08
Nodes (13): AppConfig, .apiBaseURL, .isSimulator, APIError, invalidBaseURL, invalidResponse, .isUnauthorized, network (+5 more)

### Community 85 - "test_airport.py"
Cohesion: 0.21
Nodes (12): airport_routes(), build_network(), bus(), ride_from_terminal(), test_airport_real_pbf(), test_airport_real_valhalla(), find(), test_import_sends_stable_manual_stop_ids() (+4 more)

### Community 86 - "Ревью Ш-20. Движок маршрутизации (Valhalla)"
Cohesion: 0.33
Nodes (5): CI, Замечания, Реальные замеры, Ревью Ш-20. Движок маршрутизации (Valhalla), Что сделано

### Community 87 - "test_trip_edits.py"
Cohesion: 0.25
Nodes (22): all_items(), assert_day_is_consistent(), built(), check_totals(), day_of(), pick(), plan(), post() (+14 more)

### Community 88 - "test_planner_budget.py"
Cohesion: 0.20
Nodes (18): Case, over_budget_case(), plan_for(), priced(), stops(), test_cheaper_variant_replaces_meals_too(), test_cheaper_variant_swaps_for_cheaper_places_and_cheapest_lodging(), test_drop_variant_removes_the_least_valuable_costly_optionals_only() (+10 more)

### Community 89 - "trips/api.py"
Cohesion: 0.15
Nodes (19): bearer_token(), delete_me(), logout(), me(), refresh(), RefreshRequest, current_user(), budget_choice() (+11 more)

### Community 90 - "test_planner_layout.py"
Cohesion: 0.13
Nodes (32): DirectionsLegs, _at(), check_invariants(), dates(), fingerprint(), legs_provider(), mk(), names() (+24 more)

### Community 91 - "test_weather.py"
Cohesion: 0.17
Nodes (16): cache_key(), Clock, FakeOpenMeteo, make(), test_a_failure_without_any_cache_raises_and_stores_nothing(), test_a_second_call_and_a_nearby_point_are_served_from_the_cache(), test_an_error_body_with_status_200_is_a_failure_too(), test_cache_key_rounds_the_point_and_the_elevation() (+8 more)

### Community 92 - "entitlements"
Cohesion: 0.50
Nodes (4): path, properties, entitlements, com.apple.developer.applesignin

### Community 93 - "ServerMeta"
Cohesion: 0.20
Nodes (9): ServerMeta, CodingKeys, minIOSVersion, version, State, failed, idle, loaded (+1 more)

### Community 94 - "deps.py"
Cohesion: 0.15
Nodes (14): ChatLimiters, client_ip(), install_id(), make_limiters(), make_llm(), Settings, get_llm_provider(), get_resilient_llm() (+6 more)

### Community 95 - "test_planner_scoring.py"
Cohesion: 0.25
Nodes (16): test_constraints(), test_osm_unique(), make_place(), scored(), test_an_interest_match_beats_a_little_popularity(), test_crowd_penalty_scales_with_intolerance(), test_default_hooks_mean_no_data(), test_event_bonus_counts_double_when_asked() (+8 more)

### Community 96 - "llm/__init__.py"
Cohesion: 0.08
Nodes (20): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-29 — слой LLM (fake-провайдер), Что сделано, Completion, Done, LLMNotConfigured (+12 more)

### Community 97 - "brief.py"
Cohesion: 0.12
Nodes (14): apply_update(), brief_data_block(), BriefError, BriefUpdate, _clean_items(), empty_brief(), _merge_list(), missing_fields() (+6 more)

### Community 98 - "AppLanguage"
Cohesion: 0.09
Nodes (18): AppLanguage, english, .id, .nativeName, russian, system, LanguageSettings, .code (+10 more)

### Community 99 - "CodingKeys"
Cohesion: 0.07
Nodes (30): AppleCredential, CodingKeys, authorizationCode, identityToken, Challenge, CodingKeys, displayName, email (+22 more)

### Community 100 - "Place"
Cohesion: 0.13
Nodes (5): earliest_start(), load_hours(), _minutes(), visit_minutes(), windows()

### Community 101 - "SwiftUI"
Cohesion: 0.07
Nodes (22): AuthenticationServices, PlaceholderScreen, .body, ChatScreen, .body, PlacesScreen, .body, LanguagePicker (+14 more)

### Community 102 - "APIClient"
Cohesion: 0.05
Nodes (23): Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-14 — iOS-каркас, Что сделано, AppContainer, InstallID, L10n (+15 more)

### Community 103 - "test_account_deletion.py"
Cohesion: 0.11
Nodes (25): apple_login(), apple_signin(), auth(), count(), delivery(), ec_key(), FakeGrants, http_grants() (+17 more)

### Community 104 - "apple_grants.py"
Cohesion: 0.08
Nodes (17): Отзыв токена Apple, Ревью координатора (2026-11-21), Что сделано, _exchange_code(), AppleGrantError, AppleGrants, client_secret(), credentials_configured() (+9 more)

### Community 105 - "places/schemas.py"
Cohesion: 0.18
Nodes (16): CategoriesList, Category, CategoryRef, CuratedRouteDetail, CuratedRouteItem, CuratedRoutesList, CuratedRouteSummary, DayHours (+8 more)

### Community 106 - "HaversineMatrix"
Cohesion: 0.11
Nodes (11): Не сделано / не проверено, Правила, Проверки, Ревью координатора (2026-11-21), Ревью Ш-34 — раскладка по дням и времени, Структуры плана (в памяти; Ш-36 сохранит их), leg_tools(), HaversineMatrix (+3 more)

### Community 107 - "select_candidates"
Cohesion: 0.25
Nodes (13): select_candidates(), brief(), fixture_places(), names(), test_crowd_source_is_used_for_quiet_travellers(), test_event_bonus_hook_is_applied(), test_incomplete_brief_is_refused(), test_interests_and_memory_change_the_order() (+5 more)

### Community 108 - "candidates.py"
Cohesion: 0.10
Nodes (12): Что сделано, like_pattern(), _area(), Candidate, MustHave, _resolve_must_have(), Selection, trip_days() (+4 more)

### Community 109 - "HomeScreenUITests"
Cohesion: 0.14
Nodes (8): Проверки, Итог прогона, Находки и замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-18 — места на карте и карточки мест, HomeScreenUITests, PlacesUITests

### Community 110 - "tools.py"
Cohesion: 0.16
Nodes (10): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-30 — гостевой чат, Что сделано, AddGraphNodeArgs, NoArgs, place_pin() (+2 more)

### Community 111 - "read.py"
Cohesion: 0.21
Nodes (13): budget_json(), days_json(), item_json(), leg_json(), local(), lodging_option_json(), _pair_swaps(), place_ref() (+5 more)

### Community 112 - "open_meteo.py"
Cohesion: 0.25
Nodes (5): DayWeather, _hour(), _hour_json(), OpenMeteoProvider, parse_response()

### Community 113 - "ChatPanel"
Cohesion: 0.13
Nodes (11): ChatPanel, .body, CollapsedChatBar, .body, EdgeSwipeStrip, .body, HomeScreen, .attribution (+3 more)

### Community 116 - "scoring.py"
Cohesion: 0.23
Nodes (9): Resolved, _clip01(), interest_match(), intolerance(), pick_pool(), rank(), Score, score_place() (+1 more)

### Community 117 - "View"
Cohesion: 0.18
Nodes (9): AboutScreen, .body, .version, HelpScreen, .body, LanguageScreen, .body, SettingsScreen (+1 more)

### Community 118 - "SmsProvider"
Cohesion: 0.13
Nodes (11): 0003. Значения по умолчанию для открытых вопросов SSOT §16, Допущения вне нумерации §16, Контекст, Последствия, Решение, Соглашение о комментариях в коде, Ссылки, Проверки (+3 more)

### Community 119 - "CuratedRoutesSheet"
Cohesion: 0.18
Nodes (8): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-19 — готовые маршруты для гостя (iOS-часть), Что сделано, CuratedRoutesSheet, .body, .content

### Community 120 - "XCTestCase"
Cohesion: 0.07
Nodes (12): Замечания (не исправлены, записаны), Ревью Ш-24 — схема аккаунтов и сессии, Что сделано, Проверки, AppConfigTests, InstallIDTests, SessionStoreTests, AppleSignInUITests (+4 more)

### Community 121 - "ForecastView"
Cohesion: 0.23
Nodes (5): replan(), ForecastView, HourWeather, test_a_rainy_forecast_moves_the_planner_not_the_unknown_one(), test_rain_rules_thunder_amount_and_unknown()

### Community 122 - "errors.py"
Cohesion: 0.24
Nodes (6): error_response(), install_error_handlers(), _app_error(), _http_error(), _unhandled(), _validation_error()

### Community 123 - ".stream"
Cohesion: 0.19
Nodes (3): SSEEvent, SSEParser, SSEParserTests

### Community 124 - "PlaceCardSheet"
Cohesion: 0.11
Nodes (9): Что сделано, .body, MapScreen, PlaceCardSheet, .body, ProfileMenuSheet, .body, SidebarPanel (+1 more)

### Community 125 - "Ревью Ш-33 — отбор кандидатов"
Cohesion: 0.40
Nodes (4): Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-33 — отбор кандидатов

### Community 128 - "CodingKeys"
Cohesion: 0.20
Nodes (10): CodingKeys, category, id, isPartner, isPublic, kind, lat, lon (+2 more)

### Community 129 - "PlaceCategoryStyle"
Cohesion: 0.18
Nodes (6): JolColor, UIColor, PlaceCategoryStyle, .allImages, .color, .panel

### Community 130 - "SignInEntryView"
Cohesion: 0.29
Nodes (3): SignInEntryView, .body, .accountSection

### Community 131 - "pool_sizes"
Cohesion: 0.22
Nodes (7): places_per_must_have(), pool_sizes(), PoolSizes, test_must_have_count_grows_with_the_trip(), test_a_longer_trip_or_denser_pace_never_shrinks_the_pool(), test_pool_sizes(), test_resolve_slugs()

### Community 132 - "DeleteState"
Cohesion: 0.18
Nodes (8): DeleteState, deleting, failed, idle, Build, Jol iOS, Location, Map style URL

### Community 133 - "Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта"
Cohesion: 0.29
Nodes (6): `GET /v1/trips/{id}`, `GET /v1/trips?limit=50&before=<updated_at>`, `POST /v1/trips/{id}/legs/{leg_id}/mode`  `{"mode": "walk"|"scooter"|"bus"|"metro"|"taxi"|"car"}`, Не сделано / не проверено, Проверки, Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта

### Community 134 - "Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки"
Cohesion: 0.29
Nodes (6): Замечания и отложенное, Исправления (2026-11-21), Проверка исправлений координатором, Проверки, Ревью координатора (2026-11-21), Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки

### Community 135 - "resolve"
Cohesion: 0.38
Nodes (4): _matches(), resolve(), _tokens(), test_resolve_flags_and_empty_input()

### Community 136 - "DetailState"
Cohesion: 0.33
Nodes (5): DetailState, failed, idle, loaded, loading

### Community 137 - "ListState"
Cohesion: 0.40
Nodes (5): ListState, failed, idle, loaded, loading

### Community 138 - "Ревью Ш-17. API мест (+ серверная часть Ш-19)"
Cohesion: 0.33
Nodes (5): Замечания, Ревью Ш-17. API мест (+ серверная часть Ш-19), Статус шагов, Что проверено ревьюером, Что сделано

### Community 143 - "TransactionalDatabase"
Cohesion: 0.25
Nodes (3): TransactionalDatabase, test_the_paid_plan_uses_the_customer_host_and_the_key(), test_without_a_key_the_free_host_is_used()

### Community 148 - "PlacesTests"
Cohesion: 0.21
Nodes (4): Counter, json(), page(), PlacesTests

### Community 149 - "weather/__init__.py"
Cohesion: 0.11
Nodes (11): Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-39 — клиент Open-Meteo и кэш, Условия Open-Meteo (проверены 2026-11-21 на open-meteo.com/en/terms), WeatherProvider, WeatherUnavailable, city_forecast() (+3 more)

## Knowledge Gaps
- **129 isolated node(s):** `.isSimulator`, `.isStubbed`, `.routesJSON`, `.attribution`, `.body` (+124 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1017 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **39 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Что сделано` connect `APIClient` to `AppLanguage`, `CodingKeys`, `SessionTokens`, `apple.py`, `APIError`, `App`, `.stream`?**
  _High betweenness centrality (0.166) - this node is a cross-community bridge._
- **Are the 79 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 79 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.isSimulator`, `.isStubbed`, `.routesJSON` to the rest of the system?**
  _129 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Personal Route Building (whole trip, by day)` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `AppleSignIn` connect `apple.py` to `APIClient`, `execute`?**
  _High betweenness centrality (0.160) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Step` (e.g. with `Что сделано` and `LLMError`) actually correct?**
  _`Step` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Should `worker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.061072261072261075 - nodes in this community are weakly interconnected._