# Graph Report - agent-a953de925ad27333d  (2026-11-21)

## Corpus Check
- 484 files · ~290,697 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 38 file(s) not represented in the graph (top: (none) 8, .sse 6, .csv 4)

## Summary
- 6588 nodes · 18098 edges · 286 communities (211 shown, 75 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 1447 edges (avg confidence: 0.88)
- Token cost: 211,973 input · 0 output

## Graph Freshness
- Built from commit: `6a07bcdb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Personal Route Building (whole trip, by day)
- Database
- UITestSupport
- ChatRingUITests
- 8. Шаги
- Jol Logo (PNG + SVG)
- App Icon (PNG)
- App Icon (SVG)
- RequestIdMiddleware
- CLAUDE.md
- server
- build.py
- 0001. Технологический стек
- postgres
- ChatEvent
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
- String
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
- test_memory.py
- transit.py
- import_places.py
- get_settings
- test_transit_search.py
- MapCoordinator
- pytest
- test_transit_import.py
- AppError
- Ревью Ш-10. Админка (минимум)
- fetch_all
- routing/__init__.py
- pathlib
- metrics.py
- conftest.py
- Jol — технический план (ТЗ на реализацию)
- Ревью Ш-22. Стоимость и сводка вариантов
- test_directions.py
- test_chat.py
- Ревью доработки Ш-08: отношения OSM и связь ручных мест
- import_popular.py
- .install
- Step
- fetch_pbf.sh
- README.md
- SessionTokens
- apple.py
- AppleSignInView
- test_apple.py
- psycopg
- test_chat_guest.py
- send_message
- guest_chat
- edit_tools.py
- layout.py
- PlacesModel
- AppConfig
- test_airport.py
- RoutingProvider
- test_trip_edits.py
- test_analytics.py
- trips/api.py
- test_planner_layout.py
- test_weather.py
- entitlements
- ProfileMenuContent
- RateRule
- test_planner_scoring.py
- TokenCounter
- brief.py
- AppLanguage
- CodingKeys
- Place
- SwiftUI
- APIClient
- test_account_deletion.py
- get_settings
- places/schemas.py
- HaversineMatrix
- select_candidates
- candidates.py
- PlacesUITests
- tools.py
- read.py
- open_meteo.py
- ChatPanel
- scoring.py
- View
- TripMapModel
- ChatModelTests
- XCTestCase
- Place
- main.py
- .stream
- AppContainer
- TECH_PLAN.md
- GeoBounds
- PlaceTabContent
- CodingKey
- PlaceCategoryStyle
- SignInModel
- pool_sizes
- Layout
- Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта
- execute
- test_submissions.py
- ChatModel
- ChatGraphView
- Ревью Ш-17. API мест (+ серверная часть Ш-19)
- FavoritesModel
- Metrics.swift
- test_live_plan.py
- storage/__init__.py
- PlacesTests
- typing
- register
- enqueue
- ChatState
- DirectionsModel
- live/store.py
- CrowdModel
- GeoPoint
- .response
- LocationResult
- BookingKind
- DirectionOption
- TripLegSheet
- test_clientip.py
- push/__init__.py
- test_trips_followups.py
- EventItem
- create
- build_trip
- ChatUITests
- StubURLProtocol
- DirectionsUITests
- CrowdSection
- CrowdBlock
- PlaceActionsUITests
- TripMapOverlay
- autofilter.py
- English
- APIError
- MemoryTokenStore
- process_batch
- BookingSheet
- AccountGate
- get_place
- submissions/schemas.py
- EventsModel
- crowd/service.py
- String
- CodingKeys
- StubAppleGrants
- Foundation
- .report
- load_prompt
- Деплой Jol: рабочая инструкция (Ш-51)
- pg-common.sh
- TripBudgetSheet
- notes.py
- HttpAppleGrants
- BookingModel
- CodingKeys
- options
- environment
- CodingKeys
- SignInGateUITests
- test_geocode.py
- Failure
- aggregate
- CodingKeys
- CodingKeys
- deploy.sh
- postgres
- http_grants
- Ревью Ш-51 — продакшен-инфраструктура (кодовая часть)
- postgres
- fixture
- Ревью Ш-23c (сервер) — тап по любой точке карты
- Ревью Ш-25 — вход по почте (код)
- Ревью Ш-42 (серверная часть) — скачанный маршрут
- Ревью Ш-45 — автофильтр и модерация
- Ревью Ш-50 (сервер) — события и метрики
- api
- worker
- State
- CodingKeys
- CodingKeys
- list_events
- ToolArgsError
- committed_auth_db_url
- Ревью Ш-41 — сигналы памяти и персонализация
- services
- healthcheck
- .booking
- CodingKeys
- CodingKeys
- Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)
- migrate
- .create
- DeleteState
- Phase
- H
- Ревью доработки Ш-08: дедупликация мест OSM
- test_one_failure_does_not_affect_others_in_batch
- backoff_seconds
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
10. `TripMapModel` - 65 edges

## Surprising Connections (you probably didn't know these)
- `1. Как работаем (обязательно)` --references--> `merge_place()`  [INFERRED]
  docs/HANDOFF.md → data/osm/merge.py
- `Замечания` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-08-fix-dedupe.md → data/osm/merge.py
- `Данные: таблица `osm_addresses`` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-23c-server.md → data/osm/merge.py
- `Ревью координатора (2026-11-21)` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-36.md → data/osm/merge.py
- `Ревью координатора (2026-11-21)` --references--> `merge_place()`  [INFERRED]
  docs/reviews/Ш-38.md → data/osm/merge.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crowdsourced Data and Bonus Flow** — jol_ssot_user_content, jol_ssot_content_moderation, jol_ssot_bonus_system, jol_ssot_demand_coefficient [EXTRACTED 1.00]
- **Living Plan Adaptation Loop** — jol_ssot_principle_living_plan, jol_ssot_weather_recheck, jol_ssot_mountain_morning_alert, jol_ssot_place_crowding, jol_ssot_open_meteo [EXTRACTED 1.00]
- **Route Building Inputs** — jol_ssot_route_building, jol_ssot_trip_budget, jol_ssot_mandatory_wishes, jol_ssot_crowd_tolerance, jol_ssot_memory_personalization [EXTRACTED 1.00]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]

## Communities (286 total, 75 thin omitted)

### Community 0 - "Personal Route Building (whole trip, by day)"
Cohesion: 0.06
Nodes (46): Jol Project Instructions (CLAUDE.md), Almaty Launch Geography, Authentication (email OTP, Sign in with Apple, SMS OTP), Bonus System (1 bonus = ~1 tenge), Bookings and Orders via Partner APIs, Dynamic Single-Branch Chat Graph, Content Verification (auto-filter + moderation), Crowd Tolerance Preference (+38 more)

### Community 1 - "Database"
Cohesion: 0.20
Nodes (8): Database, _main(), run_worker(), test_concurrent_email_send_limit_and_consume_once(), test_pending_delivery_does_not_hold_database_transaction(), two_pools(), clean_handlers(), db()

### Community 2 - "UITestSupport"
Cohesion: 0.09
Nodes (12): UITestPlaceActions, Answer, FixtureURLProtocol, UITestSupport, .directionsJSON, .eventsItemsJSON, .favoritesJSON, .isStubbed (+4 more)

### Community 3 - "ChatRingUITests"
Cohesion: 0.13
Nodes (15): 0. Первые 5 минут новой сессии, 1. Как работаем (обязательно), 2. Окружение (этот Mac), 3. Работа в процессе на момент передачи — ПРОВЕРИТЬ ПЕРВЫМ ДЕЛОМ, 4. Статус плана (кратко; подробности — в `TECH_PLAN.md` и `docs/reviews/`), 5. Что делать дальше (по порядку), 6. Ревью сессии (координатор, 2026-11-21), 7. Нужно от владельца (+7 more)

### Community 4 - "8. Шаги"
Cohesion: 0.07
Nodes (25): Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-40 — перепроверка маршрута по погоде, горы, пуши, Чат и SSE, Эндпоинты, install_id(), WeatherProvider (+17 more)

### Community 5 - "Jol Logo (PNG + SVG)"
Cohesion: 0.38
Nodes (7): Orange and Black Palette, Jol Logo, Jol Logo, Orange and Black Palette, Road Underline Bar, Road Underline Motif, Jol Wordmark

### Community 6 - "App Icon (PNG)"
Cohesion: 0.67
Nodes (4): Jol App Icon (1024px), Jol Wordmark, Orange Brand Color, Underline Bar Motif

### Community 7 - "App Icon (SVG)"
Cohesion: 0.67
Nodes (4): Jol App Icon, Orange and Black Palette, Road Underline Bar Motif, Jol Wordmark (J-o-l)

### Community 10 - "server"
Cohesion: 0.07
Nodes (26): DATABASE_URL, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, TEST_DATABASE_URL, jobs, server, name (+18 more)

### Community 11 - "build.py"
Cohesion: 0.10
Nodes (16): Costs, _breakdown(), budget_json(), BuiltPlan, leg_tools(), _lodging_json(), must_have_unmet_json(), place_name() (+8 more)

### Community 12 - "0001. Технологический стек"
Cohesion: 0.07
Nodes (23): 0001. Технологический стек, Контекст, Последствия, Решение, Ссылки, 0002. «ИИ понимает, движок планирует», Контекст, Последствия (+15 more)

### Community 13 - "postgres"
Cohesion: 0.06
Nodes (34): build_admins, build_elevation, build_tar, build_time_zones, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, serve_tiles (+26 more)

### Community 14 - "ChatEvent"
Cohesion: 0.04
Nodes (71): ChatBrief, CodingKeys, budgetKzt, complete, crowdTolerance, endDate, hasAccommodation, interests (+63 more)

### Community 15 - ".swiftlint.yml"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 16 - "tag_mapping.py"
Cohesion: 0.06
Nodes (35): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), _parse_days(), _parse_intervals() (+27 more)

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
Cohesion: 0.12
Nodes (30): KeptStop, RetimedDay, _apply_retime(), budget_summary(), _candidates(), _day_stops(), _fetch_variant(), _find_item() (+22 more)

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

### Community 25 - "String"
Cohesion: 0.05
Nodes (29): Endpoint, Method, delete, get, patch, post, put, CodingKeys (+21 more)

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
Nodes (46): add_route_place(), check_event_refs(), clean_text(), format_hours_day(), like_pattern(), list_places(), _norm(), page_number() (+38 more)

### Community 35 - "merge_place"
Cohesion: 0.08
Nodes (26): merge_place(), Проверки, Ревью координатора (2026-11-21), Ревью Ш-23b (сервер) — избранные места, Что сделано, Что сделано, test_osm_merge_keeps_event_and_removes_promotion_at_public_place(), keys() (+18 more)

### Community 36 - "routing/service.py"
Cohesion: 0.07
Nodes (26): pick_default(), directions(), calculate_cost(), load_tariffs(), recommend(), _recommendation_rank(), Tariff, AlmatyPoint (+18 more)

### Community 37 - "Ревью Ш-07, Ш-08, Ш-09. Данные мест"
Cohesion: 0.33
Nodes (5): Замечания, Отклонения модели данных от `TECH_PLAN.md §5`, Ревью Ш-07, Ш-08, Ш-09. Данные мест, Что проверено ревьюером, Что сделано

### Community 38 - "budget.py"
Cohesion: 0.07
Nodes (46): Что сделано, _cheaper_replacement(), cheaper_variant(), choose_lodging(), drop_variant(), _in_pool_order(), layout_centre(), leg_cost() (+38 more)

### Community 39 - "admin/api.py"
Cohesion: 0.08
Nodes (78): admin_get(), admin_post(), AdminError, AdminLoginRequired, analytics_page(), _bonus_page(), bonuses_form(), bonuses_save() (+70 more)

### Community 40 - "test_admin.py"
Cohesion: 0.10
Nodes (44): place_form_values(), get_place(), move_route_item(), fetch_all(), fetch_one(), queue(), add_category(), add_place() (+36 more)

### Community 41 - "Sendable"
Cohesion: 0.06
Nodes (60): ServerMeta, MeInfo, .identity, ProposalInfo, ProposalsList, Warning, RouteUnmet, TripLink (+52 more)

### Community 42 - "representative_point"
Cohesion: 0.23
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 43 - "test_memory.py"
Cohesion: 0.05
Nodes (66): load_memory(), penalties_from_signals(), is_open_now(), a_user(), add_report(), body(), fill_profile(), fixtures() (+58 more)

### Community 44 - "transit.py"
Cohesion: 0.12
Nodes (13): _candidates(), find_transit_options(), get_network(), _in_service(), _line_key(), _local_hour(), _materialize(), _ride_leg() (+5 more)

### Community 45 - "import_places.py"
Cohesion: 0.07
Nodes (33): build_record(), clean(), extract(), load(), main(), build_record(), collect(), database_url() (+25 more)

### Community 46 - "get_settings"
Cohesion: 0.16
Nodes (12): get_sms_provider(), normalize_phone(), SmsProvider, _StubSmsProvider, test_invalid_phone(), test_normalize_phone(), test_phone_otp_normalizes_identity_and_issues_session(), test_phone_otp_unavailable_in_production() (+4 more)

### Community 47 - "test_transit_search.py"
Cohesion: 0.20
Nodes (19): hop_speed_boost(), build(), _load(), _load_dev_network(), run(), search(), stop_row(), test_best_of_each_mode_is_kept() (+11 more)

### Community 48 - "MapCoordinator"
Cohesion: 0.05
Nodes (9): CoreLocation, Polyline, AlmatyCamera, MapCoordinator, Layer, MapView, MapLibre, Ф3. Карта (+1 more)

### Community 49 - "pytest"
Cohesion: 0.12
Nodes (24): make_router(), test_parse_bbox_rejects(), load(), _router(), run(), test_client_error_mapping(), test_client_matrix_pairwise_fallback_marks_unreachable(), test_client_retries_connect_errors_only() (+16 more)

### Community 50 - "test_transit_import.py"
Cohesion: 0.14
Nodes (13): sconn(), by_rel(), network(), rows(), sconn(), test_empty_extract_does_not_wipe_network(), test_metro_directions_share_stations(), test_migration_constraints() (+5 more)

### Community 51 - "AppError"
Cohesion: 0.05
Nodes (32): Исправления (2026-11-21), Что сделано, refresh(), DevEmailProvider, EmailProvider, EmailSettings, get_email_provider(), normalize_email() (+24 more)

### Community 53 - "Ревью Ш-10. Админка (минимум)"
Cohesion: 0.29
Nodes (6): Безопасность — проверено ревьюером, Замечания, Изменения модели данных vs `TECH_PLAN.md §5`, Исправления (2026-11-21), Ревью Ш-10. Админка (минимум), Что сделано

### Community 54 - "fetch_all"
Cohesion: 0.11
Nodes (38): today_almaty(), call(), test_today_is_the_almaty_date(), test_build_plan_reads_the_profile(), add_event(), test_admin_event_shown_on_localized_map_and_venue_card(), test_guest_can_search_evening_events_without_a_trip(), test_map_rejects_invalid_windows_and_boxes() (+30 more)

### Community 55 - "routing/__init__.py"
Cohesion: 0.11
Nodes (19): check_mode(), Maneuver, MatrixResult, NoRoute, RouteResult, RoutingError, RoutingUnavailable, _costing_body() (+11 more)

### Community 56 - "pathlib"
Cohesion: 0.16
Nodes (8): 1. Сборка тайлов (Ш-11), 2. Локальный просмотр (демо), 3. Хостинг, 4. Стили (Ш-12), maps/ — карта Jol (Ш-11, Ш-12), build(), interp(), name_expr()

### Community 57 - "metrics.py"
Cohesion: 0.29
Nodes (4): _esc(), render(), reset(), test_metrics_counts_requests_by_route_template()

### Community 58 - "conftest.py"
Cohesion: 0.09
Nodes (11): chat_env(), client(), env(), recreate_database(), scratch_db_url(), test_db_url(), test_health_db_down_returns_503_uniform_error(), test_pick_locale() (+3 more)

### Community 59 - "Jol — технический план (ТЗ на реализацию)"
Cohesion: 0.20
Nodes (10): 0. Правила исполнения, 10. Риски, которые держим в голове, 1. Цель первой версии (v1) и границы, 3. Архитектура, 4. Структура репозитория, 5. Модель данных (черновик, уточняется в шагах), 6. API (черновик), 7. Порядок фаз и вехи (+2 more)

### Community 60 - "Ревью Ш-22. Стоимость и сводка вариантов"
Cohesion: 0.29
Nodes (6): API маршрутов, Аэропорт, Повторное ревью на локальных сервисах, Предыдущая проверка без доступа к сервисам, Ревью Ш-22. Стоимость и сводка вариантов, Тарифы

### Community 61 - "test_directions.py"
Cohesion: 0.08
Nodes (21): decode_polyline6(), TransitLeg, TransitOption, _alt(), directions_api(), StubDatabase, test_directions_contract_and_almaty_tariff_date(), test_directions_empty_vs_unavailable() (+13 more)

### Community 63 - "test_chat.py"
Cohesion: 0.09
Nodes (52): SendMessage, parse_sse(), booking_settings(), link_partner(), place(), test_book_from_card_and_read_confirmation(), test_event_ticket_requires_a_current_event_at_the_partner_place(), test_limits_below_the_minimum_and_localized_messages() (+44 more)

### Community 64 - "Ревью доработки Ш-08: отношения OSM и связь ручных мест"
Cohesion: 0.40
Nodes (4): Замечания, Ревью доработки Ш-08: отношения OSM и связь ручных мест, Что проверено ревьюером, Что сделано

### Community 65 - "import_popular.py"
Cohesion: 0.14
Nodes (19): _bool(), CsvError, import_csv(), _int(), link_manual_to_osm(), _opt(), parse_rows(), _csv() (+11 more)

### Community 66 - ".install"
Cohesion: 0.14
Nodes (3): APIClientTests, ClearedFlag, .value

### Community 67 - "Step"
Cohesion: 0.09
Nodes (51): Что сделано, configure(), collect(), Completion, Done, ErrorEvent, LLMError, LLMNotConfigured (+43 more)

### Community 70 - "SessionTokens"
Cohesion: 0.13
Nodes (8): EphemeralTokenStore, SessionStore, .query, SessionTokens, CodingKeys, accessToken, refreshToken, Security

### Community 71 - "apple.py"
Cohesion: 0.10
Nodes (20): AppleKeyCache, AppleSignIn, challenge(), Challenge, _exchange_code(), fetch_keys(), sign_in(), verify_identity() (+12 more)

### Community 72 - "AppleSignInView"
Cohesion: 0.09
Nodes (14): AuthenticationServices, Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-16 — меню профиля, Что сделано, iOS, Замечания (+6 more)

### Community 73 - "test_apple.py"
Cohesion: 0.26
Nodes (11): apple_jwks(), get_nonce(), issue(), private_key(), submit(), test_invalid_signature_does_not_consume_challenge(), test_outage_is_rate_limited(), test_rejects_expired_nonce_and_wrong_algorithm_before_fetch() (+3 more)

### Community 74 - "psycopg"
Cohesion: 0.10
Nodes (17): load_seed(), database_url(), main(), apply_migrations(), checksum_of(), discover(), main(), MigrationError (+9 more)

### Community 75 - "test_chat_guest.py"
Cohesion: 0.24
Nodes (22): FakeToolCall, post(), test_bad_tool_arguments_come_back_as_a_tool_error(), test_failure_after_text_keeps_the_text_and_sends_no_done(), test_guest_chat_writes_nothing_to_the_database(), snapshot(), test_history_at_the_limits_is_accepted(), test_history_limits_are_422() (+14 more)

### Community 76 - "send_message"
Cohesion: 0.08
Nodes (30): Что сделано, _chat_json(), create_chat(), CreateChat, _finish(), get_chat(), lease_sec(), list_chats() (+22 more)

### Community 77 - "guest_chat"
Cohesion: 0.10
Nodes (9): error_payload(), run_turn(), TurnRecord, ChatTurn, guest_chat(), frames(), GuestChatRequest, format_event() (+1 more)

### Community 78 - "edit_tools.py"
Cohesion: 0.13
Nodes (22): _add_graph_node(), _build_trip(), _search_events(), _search_places(), handle_tool(), _update_trip_brief(), _after_edit(), _chat_trip() (+14 more)

### Community 79 - "layout.py"
Cohesion: 0.08
Nodes (34): Что сделано, _assign_activities(), assign(), best_day(), item_for(), _assign_meals(), _at(), _centroid() (+26 more)

### Community 80 - "PlacesModel"
Cohesion: 0.08
Nodes (15): .failedRow, PlacesModel, DetailState, failed, idle, loaded, loading, ListState (+7 more)

### Community 84 - "AppConfig"
Cohesion: 0.11
Nodes (12): Замечания, Повторная проверка — 2026-11-21, Ревью Ш-13. iOS: проект и карта, Что проверено ревьюером, Что сделано, Чтобы закрыть шаг, AppConfig, .apiBaseURL (+4 more)

### Community 85 - "test_airport.py"
Cohesion: 0.21
Nodes (12): airport_routes(), build_network(), bus(), ride_from_terminal(), test_airport_real_pbf(), test_airport_real_valhalla(), find(), test_import_sends_stable_manual_stop_ids() (+4 more)

### Community 86 - "RoutingProvider"
Cohesion: 0.08
Nodes (15): CI, Замечания, Реальные замеры, Ревью Ш-20. Движок маршрутизации (Valhalla), Что сделано, Исправления (2026-11-21), Как устроено, Контракт (+7 more)

### Community 87 - "test_trip_edits.py"
Cohesion: 0.10
Nodes (44): all_items(), assert_day_is_consistent(), built(), check_totals(), day_of(), pick(), plan(), post() (+36 more)

### Community 88 - "test_analytics.py"
Cohesion: 0.05
Nodes (53): 1. Общие ответы, 2. Типы данных (что отметить в App Store Connect), 3. API с «обоснованием причины» (Privacy Manifest), 4. Разрешения (Info.plist) — RU + EN, 5. Что решить владельцу до отправки, App Store Connect — «App Privacy»: ответы и доказательства, Что сделано, table (+45 more)

### Community 89 - "trips/api.py"
Cohesion: 0.07
Nodes (35): Ревью координатора (2026-11-21), Что сделано, accept_proposal(), budget_choice(), BudgetChoice, decline_proposal(), _edit(), etag_matches() (+27 more)

### Community 90 - "test_planner_layout.py"
Cohesion: 0.13
Nodes (32): RouterMatrix, _at(), check_invariants(), dates(), fingerprint(), legs_provider(), mk(), names() (+24 more)

### Community 91 - "test_weather.py"
Cohesion: 0.12
Nodes (19): city_forecast(), cache_key(), body_for(), Clock, FakeOpenMeteo, make(), test_a_failure_without_any_cache_raises_and_stores_nothing(), test_a_second_call_and_a_nearby_point_are_served_from_the_cache() (+11 more)

### Community 92 - "entitlements"
Cohesion: 0.50
Nodes (4): path, properties, entitlements, com.apple.developer.applesignin

### Community 93 - "ProfileMenuContent"
Cohesion: 0.12
Nodes (11): ProfileMenuContent, .accountSection, .body, .deleteFailed, ProfileMenuSheet, .body, State, failed (+3 more)

### Community 94 - "RateRule"
Cohesion: 0.14
Nodes (21): ChatLimiters, make_limiters(), make_llm(), acquire(), acquire_own(), cleanup_expired(), key_hash(), RateRule (+13 more)

### Community 95 - "test_planner_scoring.py"
Cohesion: 0.18
Nodes (19): _matches(), resolve(), _tokens(), no_event_bonus(), make_place(), scored(), test_an_interest_match_beats_a_little_popularity(), test_crowd_penalty_scales_with_intolerance() (+11 more)

### Community 96 - "TokenCounter"
Cohesion: 0.22
Nodes (5): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-29 — слой LLM (fake-провайдер), TokenCounter

### Community 97 - "brief.py"
Cohesion: 0.09
Nodes (18): Замечания и отложенное, Исправления (2026-11-21), Проверка исправлений координатором, Проверки, Ревью координатора (2026-11-21), Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки, apply_update(), brief_data_block() (+10 more)

### Community 98 - "AppLanguage"
Cohesion: 0.08
Nodes (12): AppLanguage, english, .id, .nativeName, russian, system, LanguageSettings, .code (+4 more)

### Community 99 - "CodingKeys"
Cohesion: 0.10
Nodes (20): CodingKeys, address, booking, category, crowd, description, events, hours (+12 more)

### Community 100 - "Place"
Cohesion: 0.13
Nodes (6): Правила, earliest_start(), load_hours(), _minutes(), visit_minutes(), windows()

### Community 101 - "SwiftUI"
Cohesion: 0.04
Nodes (40): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-19 — готовые маршруты для гостя (iOS-часть), Что сделано, PlaceholderScreen, .body, ChatScreen (+32 more)

### Community 102 - "APIClient"
Cohesion: 0.07
Nodes (18): Замечания и отложенное, Ревью координатора (2026-11-21), Ревью Ш-14 — iOS-каркас, Что сделано, Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-28 (iOS) — экраны входа и гейт регистрации (+10 more)

### Community 103 - "test_account_deletion.py"
Cohesion: 0.23
Nodes (15): apple_login(), auth(), count(), FakeGrants, otp_sign_in(), test_apple_delete_enqueues_revoke_and_allows_reregistration(), test_apple_without_stored_token_deletes_and_logs_gap(), test_code_exchange_problems_never_block_sign_in() (+7 more)

### Community 104 - "get_settings"
Cohesion: 0.05
Nodes (61): AppleGrants, client_secret(), credentials_configured(), decrypt_token(), encrypt_token(), get_apple_grants(), challenge_key(), _checked() (+53 more)

### Community 105 - "places/schemas.py"
Cohesion: 0.15
Nodes (20): EventItem, CategoriesList, Category, CategoryRef, CrowdHour, CrowdLevel, CrowdProfile, CuratedRouteDetail (+12 more)

### Community 106 - "HaversineMatrix"
Cohesion: 0.15
Nodes (4): HaversineMatrix, _plan_seconds(), PreferredLegs, TravelTimes

### Community 107 - "select_candidates"
Cohesion: 0.25
Nodes (14): select_candidates(), test_planner_uses_the_profile_for_quiet_travellers(), brief(), fixture_places(), names(), test_crowd_source_is_used_for_quiet_travellers(), test_event_bonus_hook_is_applied(), test_incomplete_brief_is_refused() (+6 more)

### Community 108 - "candidates.py"
Cohesion: 0.09
Nodes (12): Что сделано, Memory, like_pattern(), _area(), Candidate, MustHave, _resolve_must_have(), Selection (+4 more)

### Community 109 - "PlacesUITests"
Cohesion: 0.06
Nodes (26): Проверки, Итог прогона, Находки и замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-18 — места на карте и карточки мест, Итог прогона, Исправления (2026-11-21) (+18 more)

### Community 110 - "tools.py"
Cohesion: 0.12
Nodes (13): Замечания, Исправления (2026-11-21, Ш-51), Проверки, Ревью координатора (2026-11-21), Ревью Ш-30 — гостевой чат, Что сделано, AddGraphNodeArgs, NoArgs (+5 more)

### Community 111 - "read.py"
Cohesion: 0.13
Nodes (19): budget_json(), chosen_option(), days_json(), item_json(), leg_json(), leg_late_by_s(), local(), lodging_option_json() (+11 more)

### Community 112 - "open_meteo.py"
Cohesion: 0.19
Nodes (6): DayWeather, OpenMeteoProvider, parse_response(), test_a_rainy_forecast_moves_the_planner_not_the_unknown_one(), test_parse_rejects_a_broken_answer(), test_parse_the_recorded_response()

### Community 113 - "ChatPanel"
Cohesion: 0.11
Nodes (12): BriefChips, .body, BriefFormatting, ChatPanel, .body, .canSend, .header, .inputBar (+4 more)

### Community 116 - "scoring.py"
Cohesion: 0.22
Nodes (10): Не сделано, Resolved, _clip01(), interest_match(), intolerance(), pick_pool(), rank(), Score (+2 more)

### Community 117 - "View"
Cohesion: 0.05
Nodes (38): Что сделано, Не сделано / ограничения, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-48 (iOS) — мероприятия на карте, Что сделано, JolFont (+30 more)

### Community 118 - "TripMapModel"
Cohesion: 0.05
Nodes (23): EventsService, .body, .header, TripMapLine, TripMapModel, .day, .days, .lines (+15 more)

### Community 119 - "ChatModelTests"
Cohesion: 0.07
Nodes (13): Проверка, Реализация, Ревью координатора (2026-11-21), Ш-32. iOS: чат, граф, живая карта, ChatStub, Answer, TripStub, .isOver (+5 more)

### Community 120 - "XCTestCase"
Cohesion: 0.07
Nodes (9): Проверки, Что сделано, AppConfigTests, SessionStoreTests, SidebarAndLegalTests, FeatureGalleryUITests, MapLaunchUITests, Jol (+1 more)

### Community 121 - "Place"
Cohesion: 0.11
Nodes (18): Исправления (2026-11-21), Ревью координатора к исправлениям (2026-11-21), _count(), _count_plan(), _count_rows(), find_proposal(), problem_of(), _minutes() (+10 more)

### Community 122 - "main.py"
Cohesion: 0.04
Nodes (42): AnalyticsLimiters, _bearer(), _install_id(), make_limiters(), post_events(), ClientEvent, EventBatch, bearer_token() (+34 more)

### Community 123 - ".stream"
Cohesion: 0.18
Nodes (3): SSEEvent, SSEParser, SSEParserTests

### Community 124 - "AppContainer"
Cohesion: 0.05
Nodes (36): Что сделано, Итог прогона (Ш-37, Ш-47, Ш-48, Ш-49), Не сделано / ограничения, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-37 (iOS) — полная карта маршрута (веха M3), Что сделано (+28 more)

### Community 125 - "TECH_PLAN.md"
Cohesion: 0.06
Nodes (27): Проверки, Ревью Ш-27 — вход по SMS, Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-33 — отбор кандидатов, Не сделано / не проверено, Проверки (+19 more)

### Community 126 - "GeoBounds"
Cohesion: 0.21
Nodes (5): today, GeoBounds, .height, .queryValue, .width

### Community 127 - "PlaceTabContent"
Cohesion: 0.09
Nodes (14): PlaceGallery, .body, PlaceTabContent, .body, .bookButton, .overview, .reviews, PlaceTab (+6 more)

### Community 128 - "CodingKey"
Cohesion: 0.02
Nodes (79): CodingKeys, refreshToken, CodingKeys, minIOSVersion, version, CodingKeys, displayName, email (+71 more)

### Community 129 - "PlaceCategoryStyle"
Cohesion: 0.12
Nodes (8): JolColor, UIColor, .photos, PlaceCategoryStyle, .allImages, .color, PlacePhotoView, .body

### Community 130 - "SignInModel"
Cohesion: 0.06
Nodes (26): CodeStep, .body, DestinationStep, .appleSection, .body, ProblemText, .body, .rateLimitedText (+18 more)

### Community 131 - "pool_sizes"
Cohesion: 0.22
Nodes (7): places_per_must_have(), pool_sizes(), PoolSizes, test_must_have_count_grows_with_the_trip(), test_a_longer_trip_or_denser_pace_never_shrinks_the_pool(), test_pool_sizes(), test_resolve_slugs()

### Community 132 - "Layout"
Cohesion: 0.07
Nodes (19): Замечания и отложенное, Ревью координатора (2026-11-21), Ревью Ш-15 — главный экран, Что сделано, Проверки, JolApp, .body, RootView (+11 more)

### Community 133 - "Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта"
Cohesion: 0.25
Nodes (7): `GET /v1/trips/{id}`, `GET /v1/trips?limit=50&before=<updated_at>`, `POST /v1/trips/{id}/legs/{leg_id}/mode`  `{"mode": "walk"|"scooter"|"bus"|"metro"|"taxi"|"car"}`, Исправления (2026-11-21), Не сделано / не проверено, Проверки, Ревью Ш-37 (серверная часть) — чтение поездок и выбор транспорта

### Community 134 - "execute"
Cohesion: 0.05
Nodes (30): delete_account(), _remove_submissions(), lock_identity(), execute(), StorageProvider, save_coefficients(), summary(), AlreadyDecided (+22 more)

### Community 135 - "test_submissions.py"
Cohesion: 0.07
Nodes (54): Breakdown, compute(), resolve(), accrue(), load_coefficients(), test_approve_and_reject_flow(), test_approving_menu_and_price_applies_them_to_the_place(), test_deleted_admin_keeps_the_decision() (+46 more)

### Community 136 - "ChatModel"
Cohesion: 0.06
Nodes (13): Что проверено (код против DoD и сервера), ChatModel, .isGuestTranscript, .isStreaming, Load, failed, idle, loaded (+5 more)

### Community 137 - "ChatGraphView"
Cohesion: 0.07
Nodes (18): CoreGraphics, ArrowArcShape, .animatableData, ArrowHeadShape, .animatableData, ChatGraphView, .body, .caption (+10 more)

### Community 138 - "Ревью Ш-17. API мест (+ серверная часть Ш-19)"
Cohesion: 0.33
Nodes (5): Замечания, Ревью Ш-17. API мест (+ серверная часть Ш-19), Статус шагов, Что проверено ревьюером, Что сделано

### Community 139 - "FavoritesModel"
Cohesion: 0.06
Nodes (20): Не сделано / замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-23b (iOS часть) — избранные места, Что сделано, FavoritesList, FavoritesModel, ListState (+12 more)

### Community 143 - "test_live_plan.py"
Cohesion: 0.15
Nodes (45): d(), set_clock(), configure(), reset(), push_send(), FakeRouter, TransactionalDatabase, test_directions_place_and_tariff_version_in_postgis() (+37 more)

### Community 145 - "storage/__init__.py"
Cohesion: 0.07
Nodes (25): API, Для iOS, Исправления (2026-11-21), Не проверено и ограничения, Проверки, Ревью координатора (2026-11-21), Ревью Ш-44 (сервер) — отправка контента, Что сделано (+17 more)

### Community 148 - "PlacesTests"
Cohesion: 0.19
Nodes (4): Counter, json(), page(), PlacesTests

### Community 149 - "typing"
Cohesion: 0.04
Nodes (17): event_for_model(), EventList, EventVenue, _iso(), _stats(), day_text(), _hour(), proposal_texts() (+9 more)

### Community 150 - "register"
Cohesion: 0.18
Nodes (5): _apple_revoke(), register(), _storage_delete(), test_each_job_runs_exactly_once_with_two_parallel_workers(), one_worker()

### Community 161 - "enqueue"
Cohesion: 0.17
Nodes (9): memory_scan(), _cleanup_done_jobs(), enqueue(), enqueue_due_schedules(), _retention_cleanup(), Schedule, test_a_db_handler_loses_its_writes_when_the_lease_was_taken_over(), handle() (+1 more)

### Community 165 - "ChatState"
Cohesion: 0.07
Nodes (28): messages, GraphNode, .id, RouteReady, ChatFailure, busy, .canRetry, full (+20 more)

### Community 167 - "DirectionsModel"
Cohesion: 0.05
Nodes (31): Контракт `POST /v1/directions` (Ш-22a), как его понимает клиент, Проверки, Ревью координатора (2026-11-21), Ревью Ш-23 — «Как добраться» (веха M2), Решения и замечания, Что сделано, DirectionsModel, .currentPage (+23 more)

### Community 168 - "live/store.py"
Cohesion: 0.08
Nodes (30): local_today(), now(), optional_weather(), push(), router(), weather(), _days_ahead(), mountain_notify() (+22 more)

### Community 169 - "CrowdModel"
Cohesion: 0.08
Nodes (14): CrowdModel, Action, checkIn, report, .isWorking, Outcome, alreadyRecorded, failed (+6 more)

### Community 170 - "GeoPoint"
Cohesion: 0.10
Nodes (9): .line, from, GeoPoint, .coordinate, .isInServiceArea, Counter, DirectionsTests, FakeLocator (+1 more)

### Community 171 - ".response"
Cohesion: 0.11
Nodes (4): FavoritesTests, apiError(), SignInTests, Fixture

### Community 172 - "LocationResult"
Cohesion: 0.07
Nodes (14): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке, Что сделано, StubLocationProvider, CoreLocationProvider (+6 more)

### Community 173 - "BookingKind"
Cohesion: 0.07
Nodes (32): Booking, CodingKeys, endsAt, id, kind, note, partySize, place (+24 more)

### Community 174 - "DirectionOption"
Cohesion: 0.07
Nodes (23): Congestion, high, low, medium, DirectionLine, DirectionOption, .transitRef, DirectionsPayload (+15 more)

### Community 175 - "TripLegSheet"
Cohesion: 0.11
Nodes (7): DirectionsFormatting, .chips, TripLegSheet, .body, .choices, .current, .language

### Community 176 - "test_clientip.py"
Cohesion: 0.09
Nodes (21): client_ip(), _parse(), parse_networks(), resolve_client_ip(), _trusted(), address_text(), reverse(), pick_text() (+13 more)

### Community 177 - "push/__init__.py"
Cohesion: 0.12
Nodes (12): Что сделано, ApnsProvider, _reason(), LogPushProvider, PushError, PushMessage, PushOutcome, PushProvider (+4 more)

### Community 178 - "test_trips_followups.py"
Cohesion: 0.10
Nodes (15): encode_polyline6(), haversine_m(), _distinct_routes(), _near(), path_distance_m(), directed(), _resample(), same_path() (+7 more)

### Community 179 - "EventItem"
Cohesion: 0.08
Nodes (19): EventItem, CodingKeys, adLabel, category, description, endsAt, id, isAd (+11 more)

### Community 180 - "create"
Cohesion: 0.11
Nodes (11): BookingLimits, get_adapter(), limits_of(), supported_names(), booking_json(), BookingCreate, card_block(), check_limits() (+3 more)

### Community 181 - "build_trip"
Cohesion: 0.10
Nodes (21): SSE `route_ready` (точная форма), Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-36 — сборка в поездку (`build_trip`), `POST /v1/trips/{id}/items/{item_id}/remove`  тело необязательно: `{"force": false}`, `POST /v1/trips/{id}/items/{item_id}/replace`  `{"place_id"? | "category"? | "query"?, "force"?}`, REST (+13 more)

### Community 183 - "StubURLProtocol"
Cohesion: 0.13
Nodes (3): StubURLProtocol, .requests, TripMapTests

### Community 185 - "CrowdSection"
Cohesion: 0.13
Nodes (4): CrowdSection, .actions, .body, .model

### Community 186 - "CrowdBlock"
Cohesion: 0.13
Nodes (16): CrowdBlock, CodingKeys, now, samples, updatedAt, CrowdHour, CrowdLevel, CrowdRecorded (+8 more)

### Community 188 - "TripMapOverlay"
Cohesion: 0.13
Nodes (6): TripFormatting, TripMapOverlay, .attribution, .budgetChip, .loadedPanel, .warnings

### Community 189 - "autofilter.py"
Cohesion: 0.16
Nodes (11): collapse(), evaluate(), FilterResult, free_texts(), has_profanity(), price_reasons(), profanity_lists(), text_reasons() (+3 more)

### Community 190 - "English"
Cohesion: 0.10
Nodes (19): 1. Who we are, 1. Кто мы, 2. Data we receive, 2. Какие данные мы получаем, 3. Who receives it, 3. Кому передаём, 4. Retention, 4. Срок хранения (+11 more)

### Community 191 - "APIError"
Cohesion: 0.12
Nodes (10): APIError, invalidBaseURL, invalidResponse, .isUnauthorized, network, rateLimited, server, .serverMessage (+2 more)

### Community 193 - "process_batch"
Cohesion: 0.21
Nodes (11): _finish(), process_batch(), _run_job(), one(), test_a_job_that_kills_its_worker_ends_dead_instead_of_looping(), test_an_external_handler_failure_is_retried_with_its_payload(), test_an_external_handler_runs_without_a_transaction_held_on_its_job(), test_claim_counts_the_attempt_and_holds_a_lease() (+3 more)

### Community 194 - "BookingSheet"
Cohesion: 0.16
Nodes (3): BookingSheet, .calendar, .model

### Community 195 - "AccountGate"
Cohesion: 0.15
Nodes (8): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-49 (iOS) — кнопка и запрос бронирования, Что сделано, AccountGate, action

### Community 196 - "get_place"
Cohesion: 0.18
Nodes (11): event_json(), load_events(), window_end(), _geojson(), get_curated_route(), get_place(), list_categories(), list_curated_routes() (+3 more)

### Community 197 - "submissions/schemas.py"
Cohesion: 0.15
Nodes (10): _clean(), _line(), MenuItem, MenuPayload, _Payload, PhotoPayload, PricePayload, _required() (+2 more)

### Community 198 - "EventsModel"
Cohesion: 0.14
Nodes (3): EventsModel, MapScreen, .tripOpen

### Community 199 - "crowd/service.py"
Cohesion: 0.21
Nodes (6): card_block(), _distance(), label(), place_block(), ProfileCrowd, record()

### Community 200 - "String"
Cohesion: 0.20
Nodes (13): AppleCredential, CodingKeys, authorizationCode, identityToken, Challenge, OTPChannel, email, phone (+5 more)

### Community 201 - "CodingKeys"
Cohesion: 0.12
Nodes (16): CodingKeys, approximate, arriveAt, congestion, costKztMax, costKztMin, distanceM, durationS (+8 more)

### Community 202 - "StubAppleGrants"
Cohesion: 0.14
Nodes (9): Замечания, Исправления (2026-11-21, Ш-51), Отзыв токена Apple, Проверки, Ревью координатора (2026-11-21), Ревью Ш-28 (серверная часть) — удаление аккаунта, Что сделано, MissingCredentialsGrants (+1 more)

### Community 203 - "Foundation"
Cohesion: 0.21
Nodes (3): Foundation, L10n, Observation

### Community 204 - ".report"
Cohesion: 0.19
Nodes (6): CrowdBody, CodingKeys, lat, level, lon, CrowdService

### Community 205 - "load_prompt"
Cohesion: 0.19
Nodes (9): load_prompt(), Prompt, versions(), test_every_prompt_exists_in_both_languages(), test_guest_prompt_exposes_place_and_event_search(), test_render_fills_today(), test_trip_brief_asks_dates_then_budget_then_lodging(), test_unknown_locale_falls_back_to_english_and_unknown_prompt_fails() (+1 more)

### Community 206 - "Деплой Jol: рабочая инструкция (Ш-51)"
Cohesion: 0.14
Nodes (13): Бэкапы и восстановление, Деплой Jol: рабочая инструкция (Ш-51), Клиентский IP за прокси, Ключи шифрования токенов Apple: ротация и миграция, Миграции, Наблюдаемость, Откат, Первый деплой (+5 more)

### Community 207 - "pg-common.sh"
Cohesion: 0.24
Nodes (10): backup.sh script, db_name_of(), die(), pg_admin(), pg_dump_to(), pg_restore_from(), pg-common.sh script, sha256() (+2 more)

### Community 208 - "TripBudgetSheet"
Cohesion: 0.27
Nodes (3): TripBudgetSheet, .body, .language

### Community 209 - "notes.py"
Cohesion: 0.18
Nodes (8): chat_data_block(), memory_note(), _provider(), clean_note(), latest_notes(), memory_data_block(), save_note(), test_data_block_is_escaped_capped_and_empty_when_there_is_nothing()

### Community 210 - "HttpAppleGrants"
Cohesion: 0.24
Nodes (3): AppleGrantError, _error(), HttpAppleGrants

### Community 211 - "BookingModel"
Cohesion: 0.18
Nodes (4): BookingModel, .booking, .isSending, .form

### Community 212 - "CodingKeys"
Cohesion: 0.15
Nodes (13): CodingKeys, budget, budgetChoice, budgetKzt, days, endDate, events, id (+5 more)

### Community 213 - "options"
Cohesion: 0.21
Nodes (12): logging, driver, options, logging, max-file, max-size, logging, x-app (+4 more)

### Community 214 - "environment"
Cohesion: 0.17
Nodes (12): build_admins, build_elevation, build_tar, build_time_zones, serve_tiles, server_threads, use_default_speeds_config, valhalla (+4 more)

### Community 215 - "CodingKeys"
Cohesion: 0.17
Nodes (12): CodingKeys, endsAt, estCostKzt, id, kind, meal, mustHave, ord (+4 more)

### Community 217 - "test_geocode.py"
Cohesion: 0.21
Nodes (6): load_fixture(), sconn(), test_address_when_no_place_close(), test_bare_point_and_validation(), test_extract_fixture(), test_place_wins_inside_radius()

### Community 218 - "Failure"
Cohesion: 0.18
Nodes (8): Failure, invalid, network, notSupported, other, rateLimited, signedOut, unavailable

### Community 219 - "aggregate"
Cohesion: 0.20
Nodes (7): Запись, Проверка, Ревью координатора (2026-11-21), Чтение, Ш-47. Загруженность мест на сервере, crowd_aggregate(), aggregate()

### Community 220 - "CodingKeys"
Cohesion: 0.20
Nodes (10): CodingKeys, feasible, lodgingChanged, removed, removedCount, savesKzt, shortfallKzt, swaps (+2 more)

### Community 221 - "CodingKeys"
Cohesion: 0.20
Nodes (10): CodingKeys, chosenModeRaw, costKzt, departAt, estimated, fromItemID, id, options (+2 more)

### Community 222 - "deploy.sh"
Cohesion: 0.44
Nodes (7): compose(), die(), need_env(), previous_tag(), record_tag(), deploy.sh script, wait_ready()

### Community 223 - "postgres"
Cohesion: 0.22
Nodes (9): POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, environment, image, platform, restart, volumes (+1 more)

### Community 224 - "http_grants"
Cohesion: 0.28
Nodes (7): http_grants(), pem(), test_http_exchange_code(), test_http_revoke_outcomes(), test_http_revoke_request_and_client_secret(), handler(), test_missing_credentials_adapter_selection()

### Community 225 - "Ревью Ш-51 — продакшен-инфраструктура (кодовая часть)"
Cohesion: 0.25
Nodes (7): Замечания и компромиссы, Не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-51 — продакшен-инфраструктура (кодовая часть), Решения владельца, Что сделано

### Community 226 - "postgres"
Cohesion: 0.29
Nodes (8): depends_on, migrate, postgres, condition, depends_on, condition, depends_on, depends_on

### Community 227 - "fixture"
Cohesion: 0.25
Nodes (5): apple_signin(), delivery(), ec_key(), rsa_key(), settings()

### Community 228 - "Ревью Ш-23c (сервер) — тап по любой точке карты"
Cohesion: 0.29
Nodes (6): Данные: таблица `osm_addresses`, Замечания, Ответ, Проверки, Ревью координатора (2026-11-21), Ревью Ш-23c (сервер) — тап по любой точке карты

### Community 229 - "Ревью Ш-25 — вход по почте (код)"
Cohesion: 0.29
Nodes (6): Замечания (не исправлены, записаны), Исправления (2026-11-21), Исправления (2026-11-21, Ш-51), Проверки, Ревью координатора к исправлениям, Ревью Ш-25 — вход по почте (код)

### Community 230 - "Ревью Ш-42 (серверная часть) — скачанный маршрут"
Cohesion: 0.29
Nodes (6): ETag, Не проверено / ограничения, Ответ, Проверки, Ревью координатора (2026-11-21), Ревью Ш-42 (серверная часть) — скачанный маршрут

### Community 231 - "Ревью Ш-45 — автофильтр и модерация"
Cohesion: 0.29
Nodes (6): Автофильтр (`server/app/submissions/autofilter.py`), Модерация (админка `/admin/moderation`), Не сделано и ограничения, Проверки, Ревью координатора (2026-11-21), Ревью Ш-45 — автофильтр и модерация

### Community 232 - "Ревью Ш-50 (сервер) — события и метрики"
Cohesion: 0.29
Nodes (6): Не проверено и не сделано, Проверки, Ревью координатора (2026-11-21), Ревью Ш-50 (сервер) — события и метрики, Что было в черновике и что с ним стало, Что должен слать iOS

### Community 233 - "api"
Cohesion: 0.29
Nodes (7): env_file, environment, image, ports, restart, WEB_CONCURRENCY, api

### Community 234 - "worker"
Cohesion: 0.29
Nodes (7): disable, worker, command, env_file, healthcheck, image, restart

### Community 235 - "State"
Cohesion: 0.29
Nodes (5): State, done, editing, failed, sending

### Community 236 - "CodingKeys"
Cohesion: 0.29
Nodes (7): CodingKeys, budget, days, mustHaveUnmet, tripID, version, warnings

### Community 237 - "CodingKeys"
Cohesion: 0.29
Nodes (7): CodingKeys, category, categoryName, id, lat, lon, name

### Community 238 - "list_events"
Cohesion: 0.29
Nodes (3): list_events(), parse_bbox(), test_parse_bbox_ok()

### Community 240 - "committed_auth_db_url"
Cohesion: 0.33
Nodes (4): Замечания (не исправлены, записаны), Проверки, Ревью Ш-24 — схема аккаунтов и сессии, committed_auth_db_url()

### Community 241 - "Ревью Ш-41 — сигналы памяти и персонализация"
Cohesion: 0.33
Nodes (5): Не проверено / ограничения, Проверки, Ревью координатора (2026-11-21), Ревью Ш-41 — сигналы памяти и персонализация, Что сделано

### Community 242 - "services"
Cohesion: 0.33
Nodes (5): name, services, volumes, pgdata, valhalla_data

### Community 243 - "healthcheck"
Cohesion: 0.53
Nodes (6): interval, retries, test, timeout, healthcheck, healthcheck

### Community 245 - "CodingKeys"
Cohesion: 0.33
Nodes (6): CodingKeys, entriesKzt, eventsKzt, lodgingKzt, mealsKzt, transportKzt

### Community 246 - "CodingKeys"
Cohesion: 0.33
Nodes (6): CodingKeys, budget, changedDays, lateByS, leg, version

### Community 247 - "Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)"
Cohesion: 0.40
Nodes (4): Замечания, Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20), Что сделано, Эталонные пары (лучший вариант)

### Community 248 - "migrate"
Cohesion: 0.40
Nodes (5): command, env_file, image, restart, migrate

### Community 250 - "DeleteState"
Cohesion: 0.40
Nodes (4): DeleteState, deleting, failed, idle

### Community 251 - "Phase"
Cohesion: 0.40
Nodes (5): Phase, failed, idle, loaded, loading

### Community 253 - "Ревью доработки Ш-08: дедупликация мест OSM"
Cohesion: 0.50
Nodes (3): Замечания, Ревью доработки Ш-08: дедупликация мест OSM, Что сделано

## Knowledge Gaps
- **516 isolated node(s):** `.isSimulator`, `refreshToken`, `server`, `rateLimited`, `network` (+511 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 2063 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **75 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Исправления (2026-11-21)` connect `AppError` to `committed_auth_db_url`, `merge_place`, `APIClient`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Are the 121 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 121 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.isSimulator`, `refreshToken`, `server` to the rest of the system?**
  _516 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Personal Route Building (whole trip, by day)` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `Refresher` connect `APIClient` to `Sendable`, `AppError`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Should `UITestSupport` be split into smaller, more focused modules?**
  _Cohesion score 0.0931174089068826 - nodes in this community are weakly interconnected._
- **Why does `APIClient` connect `APIClient` to `Layout`, `8. Шаги`, `ChatModel`, `FavoritesModel`, `PlacesTests`, `DirectionsModel`, `Sendable`, `GeoPoint`, `.response`, `LocationResult`, `CrowdModel`, `get_settings`, `StubURLProtocol`, `Jol — технический план (ТЗ на реализацию)`, `APIError`, `MemoryTokenStore`, `.install`, `EventsModel`, `AppleSignInView`, `StubAppleGrants`, `.report`, `PlacesModel`, `BookingModel`, `TripMapModel`, `ChatModelTests`, `.create`, `.stream`, `AppContainer`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._