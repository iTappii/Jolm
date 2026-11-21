# Graph Report - sh-52-a11y  (2026-11-21)

## Corpus Check
- 480 files · ~289,351 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 37 file(s) not represented in the graph (top: (none) 8, .sse 6, .csv 4)

## Summary
- 6575 nodes · 18250 edges · 270 communities (202 shown, 68 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1511 edges (avg confidence: 0.88)
- Token cost: 211,973 input · 0 output

## Graph Freshness
- Built from commit: `af135e7d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Personal Route Building (whole trip, by day)
- worker.py
- Foundation
- ChatRingUITests
- 8. Шаги
- Jol Logo (PNG + SVG)
- App Icon (PNG)
- App Icon (SVG)
- main.py
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
- Ревью Ш-25 — вход по почте (код)
- test_clientip.py
- fetch_all
- routing/__init__.py
- build_styles.py
- dedupe.py
- ChatEvent
- Jol — технический план (ТЗ на реализацию)
- Ревью Ш-22. Стоимость и сводка вариантов
- test_directions.py
- test_chat.py
- Ревью доработки Ш-08: отношения OSM и связь ручных мест
- import_popular.py
- .install
- ChatUITests
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
- AppConfig
- test_airport.py
- RoutingProvider
- test_trip_edits.py
- Sendable
- AppError
- test_planner_layout.py
- test_weather.py
- entitlements
- CodingKey
- Settings
- pytest
- test_memory.py
- ChatModelTests
- AppLanguage
- CodingKeys
- Place
- SwiftUI
- APIClient
- test_account_deletion.py
- apple_grants.py
- places/schemas.py
- Ревью Ш-34 — раскладка по дням и времени
- select_candidates
- candidates.py
- PlacesUITests
- typing
- read.py
- open_meteo.py
- AppContainer
- scoring.py
- ChatModel
- SmsProvider
- View
- XCTestCase
- live/engine.py
- DirectionsPanel
- .stream
- ChatState
- TECH_PLAN.md
- TripMapModel
- PlaceTabContent
- .send
- JolColor
- SignInModel
- GeoPoint
- DeleteState
- Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта
- Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки
- BookingSheet
- submissions/service.py
- sign_in
- Ревью Ш-17. API мест (+ серверная часть Ш-19)
- DirectionOption
- push/__init__.py
- test_live_plan.py
- BookingKind
- PlacesTests
- PlaceActionsUITests
- enqueue
- _retention_cleanup
- test_analytics.py
- TripMapOverlay
- LocationResult
- DirectionsModel
- test_bonuses.py
- bookings/service.py
- proposals.py
- ChatGraphView
- SignInTests
- EventItem
- fetch_one
- trips/store.py
- RateRule
- crowd/service.py
- CrowdModel
- live/jobs.py
- CrowdBlock
- PlaceActionsTests
- local.py
- ChatPanel
- affinity.py
- autofilter.py
- AccessibilityUITests
- submissions/schemas.py
- CrowdSection
- storage/__init__.py
- rules.py
- test_bookings.py
- Foundation
- String
- CodingKeys
- TripMapTests
- analytics/api.py
- haversine_m
- Деплой Jol: рабочая инструкция (Ш-51)
- pg-common.sh
- LocalStorage
- SignInGateUITests
- options
- environment
- CodingKeys
- DirectionsUITests
- Ревью Ш-50 (сервер) — события и метрики
- Answer
- CodingKeys
- test_favorites.py
- CodingKeys
- CodingKeys
- test_geocode.py
- test_removed_museums_show_up_less_often_but_are_not_excluded
- deploy.sh
- postgres
- CodingKeys
- Ревью Ш-44 (сервер) — отправка контента
- Ревью Ш-46 — бонусы (временная формула)
- Ревью Ш-51 — продакшен-инфраструктура (кодовая часть)
- postgres
- Ревью Ш-42 (серверная часть) — скачанный маршрут
- Ревью Ш-45 — автофильтр и модерация
- Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке
- Phase
- api
- worker
- CodingKeys
- Ревью Ш-35 — бюджет и жильё (SSOT §5.2)
- services
- healthcheck
- Failure
- Look
- Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)
- Ревью Ш-23b (сервер) — избранные места
- migrate
- H
- Ревью Ш-24 — схема аккаунтов и сессии
- Step
- two_pools
- handle

## God Nodes (most connected - your core abstractions)
1. `fetch_one()` - 266 edges
2. `fetch_all()` - 186 edges
3. `conn()` - 124 edges
4. `execute()` - 124 edges
5. `sign_in()` - 113 edges
6. `AppError` - 109 edges
7. `get_settings()` - 99 edges
8. `Step` - 78 edges
9. `FakeRouter` - 66 edges
10. `Text` - 65 edges

## Surprising Connections (you probably didn't know these)
- `1. Как работаем (обязательно)` --references--> `merge_place()`  [INFERRED]
  docs/HANDOFF.md → data/osm/merge.py
- `Замечания` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-08-fix-dedupe.md → data/osm/merge.py
- `Ревью координатора (2026-11-21)` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-23b-server.md → data/osm/merge.py
- `Данные: таблица `osm_addresses`` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-23c-server.md → data/osm/merge.py
- `Ревью координатора (2026-11-21)` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-36.md → data/osm/merge.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crowdsourced Data and Bonus Flow** — jol_ssot_user_content, jol_ssot_content_moderation, jol_ssot_bonus_system, jol_ssot_demand_coefficient [EXTRACTED 1.00]
- **Living Plan Adaptation Loop** — jol_ssot_principle_living_plan, jol_ssot_weather_recheck, jol_ssot_mountain_morning_alert, jol_ssot_place_crowding, jol_ssot_open_meteo [EXTRACTED 1.00]
- **Route Building Inputs** — jol_ssot_route_building, jol_ssot_trip_budget, jol_ssot_mandatory_wishes, jol_ssot_crowd_tolerance, jol_ssot_memory_personalization [EXTRACTED 1.00]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]

## Communities (270 total, 68 thin omitted)

### Community 0 - "Personal Route Building (whole trip, by day)"
Cohesion: 0.06
Nodes (46): Jol Project Instructions (CLAUDE.md), Almaty Launch Geography, Authentication (email OTP, Sign in with Apple, SMS OTP), Bonus System (1 bonus = ~1 tenge), Bookings and Orders via Partner APIs, Dynamic Single-Branch Chat Graph, Content Verification (auto-filter + moderation), Crowd Tolerance Preference (+38 more)

### Community 1 - "worker.py"
Cohesion: 0.14
Nodes (12): Database, _apple_revoke(), backoff_seconds(), _finish(), _main(), _run_job(), run_worker(), _storage_delete() (+4 more)

### Community 2 - "Foundation"
Cohesion: 0.10
Nodes (9): FixtureURLProtocol, UITestSupport, .directionsJSON, .eventsItemsJSON, .favoritesJSON, .isStubbed, .placesJSON, .routeJSON (+1 more)

### Community 3 - "ChatRingUITests"
Cohesion: 0.07
Nodes (17): 0. Первые 5 минут новой сессии, 1. Как работаем (обязательно), 2. Окружение (этот Mac), 3. Работа в процессе на момент передачи — ПРОВЕРИТЬ ПЕРВЫМ ДЕЛОМ, 4. Статус плана (кратко; подробности — в `TECH_PLAN.md` и `docs/reviews/`), 5. Что делать дальше (по порядку), 6. Ревью сессии (координатор, 2026-11-21), 7. Нужно от владельца (+9 more)

### Community 4 - "8. Шаги"
Cohesion: 0.12
Nodes (15): EmailProvider, 8. Шаги, Ф0. Основа проекта, Ф10. Готовый маршрут в приложении (SSOT §11.3), Ф12. Память (SSOT §8), Ф13. Скачивание, история, боковая панель, Ф14. Пользовательский контент и бонусы (SSOT §10), Ф15. Загруженность (SSOT §7.3) `[предложено, §2 п.5]` (+7 more)

### Community 5 - "Jol Logo (PNG + SVG)"
Cohesion: 0.38
Nodes (7): Orange and Black Palette, Jol Logo, Jol Logo, Orange and Black Palette, Road Underline Bar, Road Underline Motif, Jol Wordmark

### Community 6 - "App Icon (PNG)"
Cohesion: 0.67
Nodes (4): Jol App Icon (1024px), Jol Wordmark, Orange Brand Color, Underline Bar Motif

### Community 7 - "App Icon (SVG)"
Cohesion: 0.67
Nodes (4): Jol App Icon, Orange and Black Palette, Road Underline Bar Motif, Jol Wordmark (J-o-l)

### Community 8 - "main.py"
Cohesion: 0.04
Nodes (37): ChatLimiters, make_limiters(), error_response(), install_error_handlers(), _app_error(), _http_error(), _unhandled(), _validation_error() (+29 more)

### Community 10 - "server"
Cohesion: 0.07
Nodes (26): DATABASE_URL, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, TEST_DATABASE_URL, jobs, server, name (+18 more)

### Community 11 - "build.py"
Cohesion: 0.05
Nodes (42): SSE `route_ready` (точная форма), Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-36 — сборка в поездку (`build_trip`), `POST /v1/trips/{id}/items/{item_id}/remove`  тело необязательно: `{"force": false}`, `POST /v1/trips/{id}/items/{item_id}/replace`  `{"place_id"? | "category"? | "query"?, "force"?}`, REST (+34 more)

### Community 12 - "0001. Технологический стек"
Cohesion: 0.12
Nodes (14): 0001. Технологический стек, Контекст, Последствия, Решение, Ссылки, 0002. «ИИ понимает, движок планирует», Контекст, Последствия (+6 more)

### Community 13 - "postgres"
Cohesion: 0.06
Nodes (34): build_admins, build_elevation, build_tar, build_time_zones, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, serve_tiles (+26 more)

### Community 14 - "import_places.py"
Cohesion: 0.11
Nodes (12): build_record(), collect(), extract(), load(), main(), merge_dropped(), relation_outer_members(), report() (+4 more)

### Community 15 - ".swiftlint.yml"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 16 - "tag_mapping.py"
Cohesion: 0.09
Nodes (25): _parse_days(), _parse_intervals(), parse_opening_hours(), _to_time(), category_for_food(), category_slug(), classify(), _clean() (+17 more)

### Community 17 - "Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас"
Cohesion: 0.20
Nodes (7): Замечания, Исправления (2026-11-21), Не проверено, Отклонения от плана (приняты как временные), Ревью Ш-01, Ш-03, Ш-04, Ш-05, Ш-06. Основа и сервер-каркас, Что проверено, LeaseLost

### Community 18 - "Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol"
Cohesion: 0.33
Nodes (5): Замечания, Интеграция (сделано ревьюером), Ревью Ш-11, Ш-12. Векторные тайлы и стиль карты Jol, Что проверено ревьюером, Что сделано

### Community 19 - "base"
Cohesion: 0.22
Nodes (9): ASSETCATALOG_COMPILER_APPICON_NAME, CURRENT_PROJECT_VERSION, GENERATE_INFOPLIST_FILE, INFOPLIST_FILE, MARKETING_VERSION, PRODUCT_BUNDLE_IDENTIFIER, SWIFT_VERSION, TARGETED_DEVICE_FAMILY (+1 more)

### Community 20 - "edit.py"
Cohesion: 0.09
Nodes (36): Ревью координатора (2026-11-21), Что сделано, KeptStop, RetimedDay, Place, _apply_retime(), budget_summary(), _candidates() (+28 more)

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
Cohesion: 0.14
Nodes (8): JolApp, .body, Navigator, App, appleMaps, .id, twoGIS, .body

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
Cohesion: 0.10
Nodes (25): merge_place(), Что сделано, test_osm_merge_keeps_event_and_removes_promotion_at_public_place(), keys(), q(), sconn(), test_load_into_db_and_idempotent(), test_merge_moves_analytics_events_to_the_survivor() (+17 more)

### Community 36 - "routing/service.py"
Cohesion: 0.06
Nodes (29): directions(), calculate_cost(), load_tariffs(), recommend(), _recommendation_rank(), Tariff, AlmatyPoint, DirectionOption (+21 more)

### Community 37 - "Ревью Ш-07, Ш-08, Ш-09. Данные мест"
Cohesion: 0.33
Nodes (5): Замечания, Отклонения модели данных от `TECH_PLAN.md §5`, Ревью Ш-07, Ш-08, Ш-09. Данные мест, Что проверено ревьюером, Что сделано

### Community 38 - "budget.py"
Cohesion: 0.07
Nodes (46): _cheaper_replacement(), cheaper_variant(), choose_lodging(), Costs, drop_variant(), _in_pool_order(), layout_centre(), leg_cost() (+38 more)

### Community 39 - "admin/api.py"
Cohesion: 0.07
Nodes (81): admin_get(), admin_post(), AdminError, AdminLoginRequired, analytics_page(), _bonus_page(), bonuses_form(), bonuses_save() (+73 more)

### Community 40 - "test_admin.py"
Cohesion: 0.16
Nodes (29): place_form_values(), get_place(), add_category(), add_place(), csrf_of(), logged_in(), login(), make_admin() (+21 more)

### Community 41 - "Sendable"
Cohesion: 0.07
Nodes (39): CuratedRouteDetail, .stops, CuratedRoutesList, CuratedRouteStop, CodingKeys, ord, .id, CuratedRouteSummary (+31 more)

### Community 42 - "representative_point"
Cohesion: 0.23
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 43 - "test_places_api.py"
Cohesion: 0.09
Nodes (34): _covers(), is_open_now(), parse_bbox(), test_admin_event_shown_on_localized_map_and_venue_card(), museum_world(), add_place(), at(), make_route() (+26 more)

### Community 44 - "transit.py"
Cohesion: 0.12
Nodes (14): _candidates(), find_transit_options(), get_network(), _in_service(), _line_key(), _local_hour(), _materialize(), _ride_leg() (+6 more)

### Community 45 - "import_transit.py"
Cohesion: 0.09
Nodes (25): build_record(), clean(), extract(), load(), main(), database_url(), find_pbf(), in_bbox() (+17 more)

### Community 46 - "get_settings"
Cohesion: 0.07
Nodes (22): Что сделано, DevEmailProvider, EmailSettings, get_email_provider(), normalize_email(), SmtpEmailProvider, OtpRequest, OtpVerifyRequest (+14 more)

### Community 47 - "test_transit_search.py"
Cohesion: 0.20
Nodes (19): hop_speed_boost(), build(), _load(), _load_dev_network(), run(), search(), stop_row(), test_best_of_each_mode_is_kept() (+11 more)

### Community 48 - "MapCoordinator"
Cohesion: 0.06
Nodes (8): CoreLocation, AlmatyCamera, MapCoordinator, Layer, MapView, MapLibre, Ф3. Карта, UIKit

### Community 49 - "pytest"
Cohesion: 0.12
Nodes (18): make_router(), _router(), run(), test_client_error_mapping(), test_client_matrix_pairwise_fallback_marks_unreachable(), test_client_retries_connect_errors_only(), flaky(), test_client_route_request_and_parse() (+10 more)

### Community 50 - "test_transit_import.py"
Cohesion: 0.14
Nodes (13): sconn(), by_rel(), network(), rows(), sconn(), test_empty_extract_does_not_wipe_network(), test_metro_directions_share_stations(), test_migration_constraints() (+5 more)

### Community 51 - "Ревью Ш-25 — вход по почте (код)"
Cohesion: 0.29
Nodes (6): Замечания (не исправлены, записаны), Исправления (2026-11-21), Исправления (2026-11-21, Ш-51), Проверки, Ревью координатора к исправлениям, Ревью Ш-25 — вход по почте (код)

### Community 53 - "test_clientip.py"
Cohesion: 0.08
Nodes (25): Безопасность — проверено ревьюером, Замечания, Изменения модели данных vs `TECH_PLAN.md §5`, Исправления (2026-11-21), Ревью Ш-10. Админка (минимум), Что сделано, client_ip(), _parse() (+17 more)

### Community 54 - "fetch_all"
Cohesion: 0.13
Nodes (35): call(), add_event(), test_guest_can_search_evening_events_without_a_trip(), test_map_rejects_invalid_windows_and_boxes(), test_map_window_overlap_coordinates_and_hidden_places(), test_planner_and_chat_offer_an_attendable_event_with_its_ad_label(), test_public_places_are_ad_free_in_admin_database_and_map(), _router() (+27 more)

### Community 55 - "routing/__init__.py"
Cohesion: 0.10
Nodes (21): check_mode(), Maneuver, MatrixResult, NoRoute, RouteResult, RoutingError, RoutingUnavailable, _costing_body() (+13 more)

### Community 56 - "build_styles.py"
Cohesion: 0.18
Nodes (8): 1. Сборка тайлов (Ш-11), 2. Локальный просмотр (демо), 3. Хостинг, 4. Стили (Ш-12), maps/ — карта Jol (Ш-11, Ш-12), build(), interp(), name_expr()

### Community 57 - "dedupe.py"
Cohesion: 0.21
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 58 - "ChatEvent"
Cohesion: 0.04
Nodes (67): ChatBrief, .isEmpty, ChatDetail, ChatEvent, briefUpdated, BriefUpdated, done, error (+59 more)

### Community 59 - "Jol — технический план (ТЗ на реализацию)"
Cohesion: 0.20
Nodes (10): 0. Правила исполнения, 10. Риски, которые держим в голове, 1. Цель первой версии (v1) и границы, 3. Архитектура, 4. Структура репозитория, 5. Модель данных (черновик, уточняется в шагах), 6. API (черновик), 7. Порядок фаз и вехи (+2 more)

### Community 60 - "Ревью Ш-22. Стоимость и сводка вариантов"
Cohesion: 0.29
Nodes (6): API маршрутов, Аэропорт, Повторное ревью на локальных сервисах, Предыдущая проверка без доступа к сервисам, Ревью Ш-22. Стоимость и сводка вариантов, Тарифы

### Community 61 - "test_directions.py"
Cohesion: 0.06
Nodes (28): Исправления (2026-11-21), Как устроено, Контракт, Не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-22a — несколько вариантов пути на вид транспорта и время прибытия, decode_polyline6() (+20 more)

### Community 63 - "test_chat.py"
Cohesion: 0.14
Nodes (38): Step, day(), new_chat(), open_stream(), say(), signing_secret(), StallingLLM, stream_request() (+30 more)

### Community 64 - "Ревью доработки Ш-08: отношения OSM и связь ручных мест"
Cohesion: 0.40
Nodes (4): Замечания, Ревью доработки Ш-08: отношения OSM и связь ручных мест, Что проверено ревьюером, Что сделано

### Community 65 - "import_popular.py"
Cohesion: 0.14
Nodes (19): _bool(), CsvError, import_csv(), _int(), link_manual_to_osm(), _opt(), parse_rows(), _csv() (+11 more)

### Community 66 - ".install"
Cohesion: 0.08
Nodes (5): APIClientTests, FavoritesTests, ProfileTests, StubURLProtocol, .requests

### Community 67 - "ChatUITests"
Cohesion: 0.06
Nodes (18): Не сделано / замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-23b (iOS часть) — избранные места, Что сделано, FavoritesList, FavoritesModel, ListState (+10 more)

### Community 70 - "SessionTokens"
Cohesion: 0.06
Nodes (20): Что сделано, Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-28 (iOS) — экраны входа и гейт регистрации, Что сделано, EphemeralTokenStore, TokenStore (+12 more)

### Community 71 - "execute"
Cohesion: 0.04
Nodes (49): Исправления (2026-11-21), Что сделано, clean_props(), _flag(), _one_of(), _short_str(), _small_int(), anonymize_user() (+41 more)

### Community 72 - "TECH_PLAN.md"
Cohesion: 0.07
Nodes (19): AuthenticationServices, Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-16 — меню профиля, Что сделано, iOS, Замечания (+11 more)

### Community 73 - "test_apple.py"
Cohesion: 0.26
Nodes (11): apple_jwks(), get_nonce(), issue(), private_key(), submit(), test_invalid_signature_does_not_consume_challenge(), test_outage_is_rate_limited(), test_rejects_expired_nonce_and_wrong_algorithm_before_fetch() (+3 more)

### Community 74 - "psycopg"
Cohesion: 0.07
Nodes (23): database_url(), main(), apply_migrations(), checksum_of(), discover(), main(), MigrationError, counts() (+15 more)

### Community 75 - "test_chat_guest.py"
Cohesion: 0.23
Nodes (23): FakeToolCall, parse_sse(), post(), test_bad_tool_arguments_come_back_as_a_tool_error(), test_failure_after_text_keeps_the_text_and_sends_no_done(), test_guest_chat_writes_nothing_to_the_database(), snapshot(), test_history_at_the_limits_is_accepted() (+15 more)

### Community 76 - "send_message"
Cohesion: 0.05
Nodes (47): Что сделано, _chat_json(), create_chat(), CreateChat, _finish(), get_chat(), lease_sec(), list_chats() (+39 more)

### Community 77 - "chat/api.py"
Cohesion: 0.07
Nodes (20): install_id(), make_llm(), error_payload(), run_turn(), TurnRecord, ChatTurn, guest_chat(), frames() (+12 more)

### Community 78 - "edit_tools.py"
Cohesion: 0.08
Nodes (29): Замечания, Исправления (2026-11-21, Ш-51), Проверки, Ревью координатора (2026-11-21), Ревью Ш-30 — гостевой чат, Что сделано, _add_graph_node(), _build_trip() (+21 more)

### Community 79 - "layout.py"
Cohesion: 0.09
Nodes (31): _assign_activities(), assign(), best_day(), item_for(), _assign_meals(), _at(), _centroid(), _Ctx (+23 more)

### Community 80 - "PlacesModel"
Cohesion: 0.03
Nodes (29): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-19 — готовые маршруты для гостя (iOS-часть), Что сделано, EventsModel, MapScreen, .body (+21 more)

### Community 84 - "AppConfig"
Cohesion: 0.11
Nodes (11): Замечания, Повторная проверка — 2026-11-21, Ревью Ш-13. iOS: проект и карта, Что проверено ревьюером, Что сделано, Чтобы закрыть шаг, AppConfig, .apiBaseURL (+3 more)

### Community 85 - "test_airport.py"
Cohesion: 0.23
Nodes (12): airport_routes(), build_network(), bus(), ride_from_terminal(), test_airport_real_pbf(), test_airport_real_valhalla(), find(), test_import_sends_stable_manual_stop_ids() (+4 more)

### Community 86 - "RoutingProvider"
Cohesion: 0.13
Nodes (6): CI, Замечания, Реальные замеры, Ревью Ш-20. Движок маршрутизации (Valhalla), Что сделано, RoutingProvider

### Community 87 - "test_trip_edits.py"
Cohesion: 0.09
Nodes (47): all_items(), assert_day_is_consistent(), built(), check_totals(), day_of(), pick(), plan(), post() (+39 more)

### Community 88 - "Sendable"
Cohesion: 0.07
Nodes (49): MeInfo, .identity, Warning, RouteUnmet, TripLink, TripLinks, DirectionStep, CategoryRef (+41 more)

### Community 89 - "AppError"
Cohesion: 0.07
Nodes (36): bearer_token(), delete_me(), logout(), me(), refresh(), RefreshRequest, current_user(), AppError (+28 more)

### Community 90 - "test_planner_layout.py"
Cohesion: 0.08
Nodes (38): Правила, DirectionsLegs, HaversineMatrix, pick_default(), _plan_seconds(), RouterMatrix, test_planner_legs_ask_for_one_variant_per_mode(), _at() (+30 more)

### Community 91 - "test_weather.py"
Cohesion: 0.10
Nodes (20): is_rainy(), cache_key(), body_for(), Clock, FakeOpenMeteo, make(), test_a_failure_without_any_cache_raises_and_stores_nothing(), test_a_rainy_forecast_moves_the_planner_not_the_unknown_one() (+12 more)

### Community 92 - "entitlements"
Cohesion: 0.50
Nodes (4): path, properties, entitlements, com.apple.developer.applesignin

### Community 93 - "CodingKey"
Cohesion: 0.03
Nodes (76): CodingKeys, displayName, email, id, phone, CodingKeys, placeName, wish (+68 more)

### Community 94 - "Settings"
Cohesion: 0.11
Nodes (38): decrypt_token(), encrypt_token(), challenge_key(), _checked(), decrypt(), encrypt(), _explicit(), _fernet_keys() (+30 more)

### Community 95 - "pytest"
Cohesion: 0.12
Nodes (26): places_per_must_have(), _matches(), resolve(), _tokens(), pool_sizes(), PoolSizes, no_event_bonus(), test_must_have_count_grows_with_the_trip() (+18 more)

### Community 96 - "test_memory.py"
Cohesion: 0.05
Nodes (66): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-29 — слой LLM (fake-провайдер), Что сделано, chat_data_block(), configure(), memory_note() (+58 more)

### Community 97 - "ChatModelTests"
Cohesion: 0.08
Nodes (10): .body, ChatStub, Answer, TripStub, .isOver, .total, ChatModelTests, Script (+2 more)

### Community 98 - "AppLanguage"
Cohesion: 0.13
Nodes (11): AppLanguage, english, .id, .nativeName, russian, system, LanguageSettings, .code (+3 more)

### Community 99 - "CodingKeys"
Cohesion: 0.10
Nodes (20): CodingKeys, address, booking, category, crowd, description, events, hours (+12 more)

### Community 100 - "Place"
Cohesion: 0.16
Nodes (5): earliest_start(), load_hours(), _minutes(), visit_minutes(), windows()

### Community 101 - "SwiftUI"
Cohesion: 0.05
Nodes (41): Экраны ВНЕ зоны, которым нужен тот же проход, RootView, .body, .content, JolRadius, JolSpacing, PlaceholderScreen, .body (+33 more)

### Community 102 - "APIClient"
Cohesion: 0.05
Nodes (27): Ревью координатора (2026-11-21), L10n, APIClient, RefreshBody, CodingKeys, refreshToken, Refresher, APIError (+19 more)

### Community 103 - "test_account_deletion.py"
Cohesion: 0.11
Nodes (27): apple_login(), apple_signin(), auth(), count(), delivery(), ec_key(), FakeGrants, http_grants() (+19 more)

### Community 104 - "apple_grants.py"
Cohesion: 0.06
Nodes (20): Отзыв токена Apple, Ревью координатора (2026-11-21), Что сделано, AppleKeyCache, AppleSignIn, challenge(), Challenge, _exchange_code() (+12 more)

### Community 105 - "places/schemas.py"
Cohesion: 0.12
Nodes (22): EventItem, EventList, EventVenue, CategoriesList, Category, CategoryRef, CrowdHour, CrowdLevel (+14 more)

### Community 106 - "Ревью Ш-34 — раскладка по дням и времени"
Cohesion: 0.33
Nodes (5): Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-34 — раскладка по дням и времени, Структуры плана (в памяти; Ш-36 сохранит их)

### Community 107 - "select_candidates"
Cohesion: 0.12
Nodes (19): ProfileCrowd, fill_profile(), fixtures(), test_build_plan_reads_the_profile(), test_card_shows_crowd_only_with_enough_data(), test_location_is_not_stored(), test_planner_uses_the_profile_for_quiet_travellers(), brief() (+11 more)

### Community 108 - "candidates.py"
Cohesion: 0.09
Nodes (13): Что сделано, like_pattern(), _area(), Candidate, MustHave, _resolve_must_have(), select_candidates(), Selection (+5 more)

### Community 109 - "PlacesUITests"
Cohesion: 0.05
Nodes (24): Проверки, Итог прогона, Находки и замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-18 — места на карте и карточки мест, Итог прогона, Исправления (2026-11-21) (+16 more)

### Community 110 - "typing"
Cohesion: 0.05
Nodes (27): AddGraphNodeArgs, NoArgs, search_events(), SearchEventsArgs, SearchPlacesArgs, list_events(), event_json(), _iso() (+19 more)

### Community 111 - "read.py"
Cohesion: 0.13
Nodes (19): budget_json(), chosen_option(), days_json(), item_json(), leg_json(), leg_late_by_s(), local(), lodging_option_json() (+11 more)

### Community 112 - "open_meteo.py"
Cohesion: 0.12
Nodes (11): DayWeather, HourWeather, WeatherUnavailable, _hour(), _hour_json(), OpenMeteoProvider, parse_response(), test_parse_rejects_a_broken_answer() (+3 more)

### Community 113 - "AppContainer"
Cohesion: 0.05
Nodes (35): Что сделано, Итог прогона (Ш-37, Ш-47, Ш-48, Ш-49), Не сделано / ограничения, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-37 (iOS) — полная карта маршрута (веха M3), Что сделано (+27 more)

### Community 116 - "scoring.py"
Cohesion: 0.22
Nodes (10): Не сделано, Resolved, _clip01(), interest_match(), intolerance(), pick_pool(), rank(), Score (+2 more)

### Community 117 - "ChatModel"
Cohesion: 0.06
Nodes (12): ChatModel, .isGuestTranscript, .isStreaming, Load, failed, idle, loaded, loading (+4 more)

### Community 118 - "SmsProvider"
Cohesion: 0.14
Nodes (11): 0003. Значения по умолчанию для открытых вопросов SSOT §16, Допущения вне нумерации §16, Допущения серверных доработок (2026-11-21) [предложено], Допущения Ш-51 (продакшен-инфраструктура) [предложено, ждёт владельца], Контекст, Последствия, Решение, Соглашение о комментариях в коде (+3 more)

### Community 119 - "View"
Cohesion: 0.05
Nodes (44): Что сделано, Не сделано / ограничения, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-48 (iOS) — мероприятия на карте, Что сделано, Text (+36 more)

### Community 120 - "XCTestCase"
Cohesion: 0.04
Nodes (28): CoreGraphics, Замечания и отложенное, Проверки, Ревью Ш-14 — iOS-каркас, Замечания и отложенное, Ревью координатора (2026-11-21), Ревью Ш-15 — главный экран, Что сделано (+20 more)

### Community 121 - "live/engine.py"
Cohesion: 0.16
Nodes (14): Исправления (2026-11-21), Ревью координатора к исправлениям (2026-11-21), _count(), _count_plan(), _count_rows(), find_proposal(), problem_of(), _minutes() (+6 more)

### Community 122 - "DirectionsPanel"
Cohesion: 0.08
Nodes (12): DirectionsFormatting, .carousel, .chips, DirectionsPanel, .content, .header, .language, TripLegSheet (+4 more)

### Community 123 - ".stream"
Cohesion: 0.19
Nodes (3): SSEEvent, SSEParser, SSEParserTests

### Community 124 - "ChatState"
Cohesion: 0.07
Nodes (30): CodingKeys, brief, graphNodes, id, messages, title, ChatFailure, busy (+22 more)

### Community 125 - "TECH_PLAN.md"
Cohesion: 0.07
Nodes (21): Данные: таблица `osm_addresses`, Замечания, Ответ, Проверки, Ревью координатора (2026-11-21), Ревью Ш-23c (сервер) — тап по любой точке карты, Проверки, Ревью Ш-27 — вход по SMS (+13 more)

### Community 126 - "TripMapModel"
Cohesion: 0.06
Nodes (22): .current, TripMapLine, TripMapModel, .day, .days, PendingRemoval, Phase, failed (+14 more)

### Community 127 - "PlaceTabContent"
Cohesion: 0.11
Nodes (9): .body, NavigatorButton, PlaceGallery, .body, PlaceTabContent, .body, .overview, .reviews (+1 more)

### Community 128 - ".send"
Cohesion: 0.06
Nodes (21): AppleCredential, CodingKeys, authorizationCode, identityToken, Challenge, OTPChannel, email, phone (+13 more)

### Community 129 - "JolColor"
Cohesion: 0.08
Nodes (11): JolColor, UIColor, FavoritesSheet, .body, .content, .photos, PlaceCategoryStyle, .allImages (+3 more)

### Community 130 - "SignInModel"
Cohesion: 0.07
Nodes (22): CodeStep, .body, DestinationStep, .body, ProblemText, .body, .rateLimitedText, SignInEntryView (+14 more)

### Community 131 - "GeoPoint"
Cohesion: 0.08
Nodes (13): .currentPage, .line, DirectionsRequest, CodingKeys, from, toPlaceID, GeoPoint, .coordinate (+5 more)

### Community 132 - "DeleteState"
Cohesion: 0.40
Nodes (4): DeleteState, deleting, failed, idle

### Community 133 - "Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта"
Cohesion: 0.25
Nodes (7): `GET /v1/trips/{id}`, `GET /v1/trips?limit=50&before=<updated_at>`, `POST /v1/trips/{id}/legs/{leg_id}/mode`  `{"mode": "walk"|"scooter"|"bus"|"metro"|"taxi"|"car"}`, Исправления (2026-11-21), Не сделано / не проверено, Проверки, Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта

### Community 134 - "Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки"
Cohesion: 0.29
Nodes (6): Замечания и отложенное, Исправления (2026-11-21), Проверка исправлений координатором, Проверки, Ревью координатора (2026-11-21), Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки

### Community 135 - "BookingSheet"
Cohesion: 0.05
Nodes (21): BookingModel, .booking, Failure, invalid, network, notSupported, other, rateLimited (+13 more)

### Community 136 - "submissions/service.py"
Cohesion: 0.09
Nodes (19): StorageProvider, create_submission(), summary(), AlreadyDecided, _apply(), decide(), create_submission(), create_upload() (+11 more)

### Community 137 - "sign_in"
Cohesion: 0.15
Nodes (38): test_approve_and_reject_flow(), test_approving_menu_and_price_applies_them_to_the_place(), test_deleted_admin_keeps_the_decision(), test_duplicate_photo_by_hash(), test_duplicate_review_text(), test_menu_and_transit_text_are_filtered_too(), test_moderation_requires_admin_and_csrf(), test_moderator_rejected_photo_cannot_come_back() (+30 more)

### Community 138 - "Ревью Ш-17. API мест (+ серверная часть Ш-19)"
Cohesion: 0.33
Nodes (5): Замечания, Ревью Ш-17. API мест (+ серверная часть Ш-19), Статус шагов, Что проверено ревьюером, Что сделано

### Community 139 - "DirectionOption"
Cohesion: 0.06
Nodes (27): Congestion, high, low, medium, DirectionLine, DirectionOption, .transitRef, DirectionsPayload (+19 more)

### Community 142 - "push/__init__.py"
Cohesion: 0.09
Nodes (20): Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-40 — перепроверка маршрута по погоде, горы, пуши, Чат и SSE, Что сделано, Эндпоинты, push() (+12 more)

### Community 143 - "test_live_plan.py"
Cohesion: 0.19
Nodes (39): d(), set_clock(), configure(), FakeRouter, TransactionalDatabase, test_directions_place_and_tariff_version_in_postgis(), at(), built() (+31 more)

### Community 145 - "BookingKind"
Cohesion: 0.06
Nodes (33): Booking, CodingKeys, endsAt, id, kind, note, partySize, place (+25 more)

### Community 148 - "PlacesTests"
Cohesion: 0.21
Nodes (4): Counter, json(), page(), PlacesTests

### Community 149 - "PlaceActionsUITests"
Cohesion: 0.12
Nodes (9): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-49 (iOS) — кнопка и запрос бронирования, Что сделано, AccountGate, action (+1 more)

### Community 150 - "enqueue"
Cohesion: 0.14
Nodes (16): enqueue(), process_batch(), register(), one(), test_a_db_handler_loses_its_writes_when_the_lease_was_taken_over(), handle(), test_a_job_that_kills_its_worker_ends_dead_instead_of_looping(), test_an_external_handler_failure_is_retried_with_its_payload() (+8 more)

### Community 161 - "_retention_cleanup"
Cohesion: 0.25
Nodes (5): _cleanup_done_jobs(), enqueue_due_schedules(), _retention_cleanup(), Schedule, test_schedule_enqueues_once_per_slot_even_when_called_twice()

### Community 165 - "test_analytics.py"
Cohesion: 0.12
Nodes (33): period(), add_item(), checkin(), ev(), fixtures(), hdr(), make_trip(), make_user() (+25 more)

### Community 167 - "TripMapOverlay"
Cohesion: 0.08
Nodes (15): Замечания (по важности), Проверки, Что сделано, Ш-52 (доступность) — полная карта маршрута, «Как добраться», мероприятия, бронирование, готовые маршруты, AdaptiveStack, JolTarget, .notice, .originRow (+7 more)

### Community 168 - "LocationResult"
Cohesion: 0.08
Nodes (10): StubLocationProvider, .stubLocation, CoreLocationProvider, LocationProviding, LocationResult, denied, located, unavailable (+2 more)

### Community 169 - "DirectionsModel"
Cohesion: 0.09
Nodes (14): Контракт `POST /v1/directions` (Ш-22a), как его понимает клиент, Проверки, Ревью координатора (2026-11-21), Ревью Ш-23 — «Как добраться» (веха M2), Решения и замечания, Что сделано, DirectionsModel, Fallback (+6 more)

### Community 170 - "test_bonuses.py"
Cohesion: 0.10
Nodes (20): Breakdown, compute(), Param, resolve(), validate(), accrue(), load_coefficients(), add_trips() (+12 more)

### Community 171 - "bookings/service.py"
Cohesion: 0.12
Nodes (12): get_adapter(), supported_names(), create_booking(), get_booking(), list_bookings(), booking_json(), BookingCreate, card_block() (+4 more)

### Community 172 - "proposals.py"
Cohesion: 0.14
Nodes (18): mountain_notify(), accept(), create(), decline(), list_json(), _place_refs(), add_chat_message(), add_notice() (+10 more)

### Community 173 - "ChatGraphView"
Cohesion: 0.11
Nodes (19): Проверка, Реализация, Ревью координатора (2026-11-21), Ш-32. iOS: чат, граф, живая карта, ArrowArcShape, .animatableData, ArrowHeadShape, .animatableData (+11 more)

### Community 174 - "SignInTests"
Cohesion: 0.16
Nodes (3): apiError(), SignInTests, Fixture

### Community 175 - "EventItem"
Cohesion: 0.08
Nodes (19): EventItem, CodingKeys, adLabel, category, description, endsAt, id, isAd (+11 more)

### Community 176 - "fetch_one"
Cohesion: 0.13
Nodes (23): move_route_item(), fetch_all(), fetch_one(), queue(), test_curated_route_create_add_reorder_publish(), order(), pending_ids(), a_user() (+15 more)

### Community 177 - "trips/store.py"
Cohesion: 0.11
Nodes (12): apply_budget_choice(), brief_json(), get_trip_for_update(), insert_leg(), list_trips(), lodging_options(), lodging_rows(), offline_extras() (+4 more)

### Community 178 - "RateRule"
Cohesion: 0.18
Nodes (18): acquire(), acquire_own(), cleanup_expired(), key_hash(), RateRule, test_a_committed_count_survives_a_failing_request(), test_a_refused_request_counts_nothing_anywhere(), test_cleanup_removes_only_expired_rows() (+10 more)

### Community 179 - "crowd/service.py"
Cohesion: 0.14
Nodes (11): checkin(), CrowdReport, report(), Where, crowd_aggregate(), aggregate(), card_block(), _distance() (+3 more)

### Community 180 - "CrowdModel"
Cohesion: 0.11
Nodes (13): CrowdModel, Action, checkIn, report, .isWorking, Outcome, alreadyRecorded, failed (+5 more)

### Community 181 - "live/jobs.py"
Cohesion: 0.13
Nodes (14): local_today(), now(), optional_weather(), reset(), router(), weather(), _days_ahead(), mountain_scan() (+6 more)

### Community 182 - "CrowdBlock"
Cohesion: 0.12
Nodes (17): CrowdBlock, CodingKeys, now, samples, today, updatedAt, CrowdHour, CrowdLevel (+9 more)

### Community 184 - "local.py"
Cohesion: 0.14
Nodes (6): ObjectTooLarge, PresignedPut, StorageError, _hmac(), sign_query(), test_sigv4_matches_the_aws_documented_presign_example()

### Community 185 - "ChatPanel"
Cohesion: 0.13
Nodes (10): BriefChips, .body, BriefFormatting, ChatPanel, .canSend, .header, .inputBar, .isActive (+2 more)

### Community 186 - "affinity.py"
Cohesion: 0.12
Nodes (13): load_memory(), Memory, penalties_from_signals(), clean_note(), latest_notes(), memory_data_block(), save_note(), reject_museums() (+5 more)

### Community 187 - "autofilter.py"
Cohesion: 0.15
Nodes (11): collapse(), evaluate(), FilterResult, free_texts(), has_profanity(), price_reasons(), profanity_lists(), text_reasons() (+3 more)

### Community 189 - "submissions/schemas.py"
Cohesion: 0.13
Nodes (12): _clean(), _line(), MenuItem, MenuPayload, _Payload, PhotoPayload, PricePayload, _required() (+4 more)

### Community 190 - "CrowdSection"
Cohesion: 0.15
Nodes (4): CrowdSection, .actions, .body, .model

### Community 191 - "storage/__init__.py"
Cohesion: 0.16
Nodes (9): Что сделано, make_storage(), media_url(), S3Storage, s3(), test_make_storage_by_settings(), test_media_url(), test_s3_presigned_put_signs_length_and_type() (+1 more)

### Community 192 - "rules.py"
Cohesion: 0.13
Nodes (9): _stats(), day_text(), _hour(), mountain_texts(), proposal_texts(), Problem, stop_problem(), visit_hours() (+1 more)

### Community 193 - "test_bookings.py"
Cohesion: 0.18
Nodes (13): booking_settings(), link_partner(), place(), test_book_from_card_and_read_confirmation(), test_event_ticket_requires_a_current_event_at_the_partner_place(), test_limits_below_the_minimum_and_localized_messages(), test_only_connected_partners_offer_bookings(), test_pagination_at_equal_timestamps() (+5 more)

### Community 194 - "Foundation"
Cohesion: 0.18
Nodes (4): Foundation, Polyline, EventsService, Observation

### Community 195 - "String"
Cohesion: 0.20
Nodes (7): Endpoint, Method, delete, get, patch, post, put

### Community 196 - "CodingKeys"
Cohesion: 0.12
Nodes (16): CodingKeys, approximate, arriveAt, congestion, costKztMax, costKztMin, distanceM, durationS (+8 more)

### Community 198 - "analytics/api.py"
Cohesion: 0.20
Nodes (7): AnalyticsLimiters, _bearer(), _install_id(), make_limiters(), post_events(), ClientEvent, EventBatch

### Community 199 - "haversine_m"
Cohesion: 0.21
Nodes (8): encode_polyline6(), haversine_m(), path_distance_m(), directed(), _resample(), route(), test_path_distance_is_small_for_the_same_streets_and_large_for_a_detour(), VariantRouter

### Community 200 - "Деплой Jol: рабочая инструкция (Ш-51)"
Cohesion: 0.14
Nodes (13): Бэкапы и восстановление, Деплой Jol: рабочая инструкция (Ш-51), Клиентский IP за прокси, Ключи шифрования токенов Apple: ротация и миграция, Миграции, Наблюдаемость, Откат, Первый деплой (+5 more)

### Community 201 - "pg-common.sh"
Cohesion: 0.24
Nodes (10): backup.sh script, db_name_of(), die(), pg_admin(), pg_dump_to(), pg_restore_from(), pg-common.sh script, sha256() (+2 more)

### Community 202 - "LocalStorage"
Cohesion: 0.29
Nodes (4): LocalStorage, _sig(), test_local_storage_roundtrip_and_traversal(), test_storage_delete_job_removes_objects()

### Community 204 - "options"
Cohesion: 0.21
Nodes (12): logging, driver, options, logging, max-file, max-size, logging, x-app (+4 more)

### Community 205 - "environment"
Cohesion: 0.17
Nodes (12): build_admins, build_elevation, build_tar, build_time_zones, serve_tiles, server_threads, use_default_speeds_config, valhalla (+4 more)

### Community 206 - "CodingKeys"
Cohesion: 0.17
Nodes (12): CodingKeys, endsAt, estCostKzt, id, kind, meal, mustHave, ord (+4 more)

### Community 208 - "Ревью Ш-50 (сервер) — события и метрики"
Cohesion: 0.16
Nodes (9): Замечания, Ревью доработки Ш-08: дедупликация мест OSM, Что сделано, Не проверено и не сделано, Проверки, Ревью координатора (2026-11-21), Ревью Ш-50 (сервер) — события и метрики, Что было в черновике и что с ним стало (+1 more)

### Community 210 - "CodingKeys"
Cohesion: 0.18
Nodes (11): CodingKeys, budgetKzt, complete, crowdTolerance, endDate, hasAccommodation, interests, missing (+3 more)

### Community 211 - "test_favorites.py"
Cohesion: 0.38
Nodes (8): mk(), put(), test_cap_applies_to_new_places_only(), test_favorites_are_per_user_and_hidden_places_are_not_listed(), test_guest_gets_401_everywhere(), test_names_follow_accept_language_and_address(), test_put_list_delete_and_idempotency(), test_put_unknown_or_inactive_place_is_404_and_delete_is_still_204()

### Community 212 - "CodingKeys"
Cohesion: 0.20
Nodes (10): CodingKeys, breakdown, budgetKzt, choice, lodging, remainingKzt, shortfallKzt, status (+2 more)

### Community 213 - "CodingKeys"
Cohesion: 0.20
Nodes (10): CodingKeys, chosenModeRaw, costKzt, departAt, estimated, fromItemID, id, options (+2 more)

### Community 214 - "test_geocode.py"
Cohesion: 0.27
Nodes (5): load_fixture(), test_address_when_no_place_close(), test_bare_point_and_validation(), test_extract_fixture(), test_place_wins_inside_radius()

### Community 215 - "test_removed_museums_show_up_less_often_but_are_not_excluded"
Cohesion: 0.22
Nodes (8): Не проверено / ограничения, Проверки, Ревью координатора (2026-11-21), Ревью Ш-41 — сигналы памяти и персонализация, Что сделано, new_user(), test_favorite_place_and_category_get_a_small_bonus(), test_removed_museums_show_up_less_often_but_are_not_excluded()

### Community 216 - "deploy.sh"
Cohesion: 0.44
Nodes (7): compose(), die(), need_env(), previous_tag(), record_tag(), deploy.sh script, wait_ready()

### Community 217 - "postgres"
Cohesion: 0.22
Nodes (9): POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, environment, image, platform, restart, volumes (+1 more)

### Community 218 - "CodingKeys"
Cohesion: 0.22
Nodes (9): CodingKeys, distanceM, durationS, fromName, geometry, kind, routeRef, toName (+1 more)

### Community 219 - "Ревью Ш-44 (сервер) — отправка контента"
Cohesion: 0.25
Nodes (7): API, Для iOS, Исправления (2026-11-21), Не проверено и ограничения, Проверки, Ревью координатора (2026-11-21), Ревью Ш-44 (сервер) — отправка контента

### Community 220 - "Ревью Ш-46 — бонусы (временная формула)"
Cohesion: 0.25
Nodes (7): Не сделано и риски, Проверки, Ревью координатора (2026-11-21), Ревью Ш-46 — бонусы (временная формула), Решения, Формула (временная), Что сделано

### Community 221 - "Ревью Ш-51 — продакшен-инфраструктура (кодовая часть)"
Cohesion: 0.25
Nodes (7): Замечания и компромиссы, Не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-51 — продакшен-инфраструктура (кодовая часть), Решения владельца, Что сделано

### Community 222 - "postgres"
Cohesion: 0.29
Nodes (8): depends_on, migrate, postgres, condition, depends_on, condition, depends_on, depends_on

### Community 223 - "Ревью Ш-42 (серверная часть) — скачанный маршрут"
Cohesion: 0.29
Nodes (6): ETag, Не проверено / ограничения, Ответ, Проверки, Ревью координатора (2026-11-21), Ревью Ш-42 (серверная часть) — скачанный маршрут

### Community 224 - "Ревью Ш-45 — автофильтр и модерация"
Cohesion: 0.29
Nodes (6): Автофильтр (`server/app/submissions/autofilter.py`), Модерация (админка `/admin/moderation`), Не сделано и ограничения, Проверки, Ревью координатора (2026-11-21), Ревью Ш-45 — автофильтр и модерация

### Community 225 - "Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке"
Cohesion: 0.29
Nodes (6): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке, Что сделано

### Community 226 - "Phase"
Cohesion: 0.29
Nodes (6): Phase, failed, idle, loaded, loading, locating

### Community 227 - "api"
Cohesion: 0.29
Nodes (7): env_file, environment, image, ports, restart, WEB_CONCURRENCY, api

### Community 228 - "worker"
Cohesion: 0.29
Nodes (7): disable, worker, command, env_file, healthcheck, image, restart

### Community 229 - "CodingKeys"
Cohesion: 0.29
Nodes (7): CodingKeys, category, categoryName, id, lat, lon, name

### Community 230 - "Ревью Ш-35 — бюджет и жильё (SSOT §5.2)"
Cohesion: 0.33
Nodes (5): Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-35 — бюджет и жильё (SSOT §5.2), Что сделано

### Community 231 - "services"
Cohesion: 0.33
Nodes (5): name, services, volumes, pgdata, valhalla_data

### Community 232 - "healthcheck"
Cohesion: 0.53
Nodes (6): interval, retries, test, timeout, healthcheck, healthcheck

### Community 233 - "Failure"
Cohesion: 0.33
Nodes (5): Failure, generic, network, outsideArea, serviceUnavailable

### Community 234 - "Look"
Cohesion: 0.33
Nodes (5): Look, .appearance, dark, darkLarge, lightLarge

### Community 235 - "Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)"
Cohesion: 0.40
Nodes (4): Замечания, Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20), Что сделано, Эталонные пары (лучший вариант)

### Community 236 - "Ревью Ш-23b (сервер) — избранные места"
Cohesion: 0.40
Nodes (4): Проверки, Ревью координатора (2026-11-21), Ревью Ш-23b (сервер) — избранные места, Что сделано

### Community 237 - "migrate"
Cohesion: 0.40
Nodes (5): command, env_file, image, restart, migrate

### Community 239 - "Ревью Ш-24 — схема аккаунтов и сессии"
Cohesion: 0.50
Nodes (3): Замечания (не исправлены, записаны), Проверки, Ревью Ш-24 — схема аккаунтов и сессии

### Community 240 - "Step"
Cohesion: 0.67
Nodes (3): Step, code, destination

## Knowledge Gaps
- **513 isolated node(s):** `.isSimulator`, `refreshToken`, `server`, `rateLimited`, `network` (+508 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 2033 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **68 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Исправления (2026-11-21)` connect `execute` to `AppError`, `merge_place`, `APIClient`, `Ревью Ш-24 — схема аккаунтов и сессии`?**
  _High betweenness centrality (0.160) - this node is a cross-community bridge._
- **Are the 121 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 121 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.isSimulator`, `refreshToken`, `server` to the rest of the system?**
  _513 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Personal Route Building (whole trip, by day)` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `Refresher` connect `APIClient` to `Sendable`, `SessionTokens`, `execute`?**
  _High betweenness centrality (0.158) - this node is a cross-community bridge._
- **Should `worker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14492753623188406 - nodes in this community are weakly interconnected._
- **Why does `AppError` connect `AppError` to `test_memory.py`, `routing/service.py`, `analytics/api.py`, `execute`, `apple_grants.py`, `main.py`, `submissions/service.py`, `bookings/service.py`, `send_message`, `chat/api.py`, `get_settings`, `edit_tools.py`, `typing`, `proposals.py`, `psycopg`, `crowd/service.py`, `edit.py`, `Settings`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._