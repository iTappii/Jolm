# Graph Report - Jol v2  (2026-11-21)

## Corpus Check
- 249 files · ~121,716 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 25 file(s) not represented in the graph (top: (none) 6, .csv 4, .xcstrings 3)

## Summary
- 2758 nodes · 7286 edges · 162 communities (122 shown, 40 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 619 edges (avg confidence: 0.88)
- Token cost: 211,973 input · 0 output

## Graph Freshness
- Built from commit: `82dd3eb7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Personal Route Building (whole trip, by day)
- worker.py
- MapView.swift
- merge_place
- 8. Шаги
- Jol Logo (PNG + SVG)
- App Icon (PNG)
- App Icon (SVG)
- main.py
- CLAUDE.md
- server
- Ревью Ш-13. iOS: проект и карта
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
- Layout
- htmx-1.9.12.min.js
- Ревью Ш-02. ADR по допущениям
- options
- JolTests
- MapLibre
- build_tiles.sh
- jol-server
- admin/service.py
- test_osm_pipeline.py
- routing/service.py
- Ревью Ш-07, Ш-08, Ш-09. Данные мест
- test_admin_validation.py
- admin/api.py
- test_admin.py
- auth.py
- representative_point
- test_places_api.py
- transit.py
- import_transit.py
- get_settings
- test_transit_search.py
- MapView
- pytest
- test_transit_import.py
- test_otp.py
- Ревью Ш-10. Админка (минимум)
- conftest.py
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
- apple.py
- TECH_PLAN.md
- test_apple.py
- psycopg
- execute
- send_message
- chat/api.py
- H
- layout.py
- execute
- test_popular_import.py
- APIClient
- test_airport.py
- RoutingProvider
- XCTestCase
- pathlib
- auth/api.py
- test_planner_layout.py
- committed_auth_db_url
- entitlements
- Foundation
- Settings
- test_planner_scoring.py
- llm/__init__.py
- brief.py
- AppLanguage
- .signInWithApple
- Place
- SwiftUI
- Что сделано
- test_account_deletion.py
- apple_grants.py
- places/schemas.py
- TravelTimes
- select_candidates
- candidates.py
- HomeScreenUITests
- tools.py
- load_prompt
- Endpoint
- ChatPanel
- places/api.py
- AppConfig
- scoring.py
- View
- LLMProvider
- .body
- XCTest
- HttpAppleGrants
- places/service.py
- .stream
- SidebarPanel
- Ревью Ш-33 — отбор кандидатов
- weather.py
- StubAppleGrants
- ProfileMenuContent
- JolColor
- SignInEntryView
- pool_sizes
- fixture
- http_grants
- Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки
- .current
- .parse
- Coordinator
- Ревью Ш-17. API мест (+ серверная часть Ш-19)
- Ревью Ш-34 — раскладка по дням и времени
- CrowdSource
- _DayOrder
- Metrics.swift
- TransactionalDatabase

## God Nodes (most connected - your core abstractions)
1. `fetch_one()` - 109 edges
2. `fetch_all()` - 71 edges
3. `conn()` - 69 edges
4. `execute()` - 56 edges
5. `get_settings()` - 54 edges
6. `Step` - 52 edges
7. `AppError` - 47 edges
8. `db()` - 37 edges
9. `APIClient` - 36 edges
10. `FakeLLM` - 36 edges

## Surprising Connections (you probably didn't know these)
- `9. Тестирование` --references--> `APIClient`  [INFERRED]
  TECH_PLAN.md → ios/Jol/Core/Networking/APIClient.swift
- `Проверки` --references--> `ProfileTests`  [INFERRED]
  docs/reviews/Ш-16.md → ios/JolTests/ProfileTests.swift
- `Проверки` --references--> `ErrorEvent`  [INFERRED]
  docs/reviews/Ш-29.md → server/app/providers/llm/base.py
- `Проверки` --references--> `process_batch()`  [INFERRED]
  docs/reviews/Ш-28-server.md → server/app/worker.py
- `Проверки` --references--> `committed_auth_db_url()`  [INFERRED]
  docs/reviews/Ш-24.md → server/tests/conftest.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crowdsourced Data and Bonus Flow** — jol_ssot_user_content, jol_ssot_content_moderation, jol_ssot_bonus_system, jol_ssot_demand_coefficient [EXTRACTED 1.00]
- **Living Plan Adaptation Loop** — jol_ssot_principle_living_plan, jol_ssot_weather_recheck, jol_ssot_mountain_morning_alert, jol_ssot_place_crowding, jol_ssot_open_meteo [EXTRACTED 1.00]
- **Route Building Inputs** — jol_ssot_route_building, jol_ssot_trip_budget, jol_ssot_mandatory_wishes, jol_ssot_crowd_tolerance, jol_ssot_memory_personalization [EXTRACTED 1.00]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]

## Communities (162 total, 40 thin omitted)

### Community 0 - "Personal Route Building (whole trip, by day)"
Cohesion: 0.06
Nodes (46): Jol Project Instructions (CLAUDE.md), Almaty Launch Geography, Authentication (email OTP, Sign in with Apple, SMS OTP), Bonus System (1 bonus = ~1 tenge), Bookings and Orders via Partner APIs, Dynamic Single-Branch Chat Graph, Content Verification (auto-filter + moderation), Crowd Tolerance Preference (+38 more)

### Community 1 - "worker.py"
Cohesion: 0.09
Nodes (21): Database, _apple_revoke(), backoff_seconds(), _cleanup_done_jobs(), enqueue(), enqueue_due_schedules(), _main(), process_batch() (+13 more)

### Community 2 - "MapView.swift"
Cohesion: 0.33
Nodes (3): CoreLocation, AlmatyCamera, MapLibre

### Community 3 - "merge_place"
Cohesion: 0.11
Nodes (12): merge_place(), Jol — передача работы (2026-11-21), Как работаем, Коммиты, Нужно от владельца, Окружение (этот Mac), Статус плана, Что делать дальше (+4 more)

### Community 4 - "8. Шаги"
Cohesion: 0.12
Nodes (17): 8. Шаги, Ф0. Основа проекта, Ф10. Готовый маршрут в приложении (SSOT §11.3), Ф11. Погода (SSOT §7.1–7.2), Ф12. Память (SSOT §8), Ф13. Скачивание, история, боковая панель, Ф14. Пользовательский контент и бонусы (SSOT §10), Ф15. Загруженность (SSOT §7.3) `[предложено, §2 п.5]` (+9 more)

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
Cohesion: 0.07
Nodes (18): ChatLimiters, make_limiters(), error_response(), install_error_handlers(), _app_error(), _http_error(), _unhandled(), _validation_error() (+10 more)

### Community 10 - "server"
Cohesion: 0.07
Nodes (26): DATABASE_URL, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, TEST_DATABASE_URL, jobs, server, name (+18 more)

### Community 11 - "Ревью Ш-13. iOS: проект и карта"
Cohesion: 0.29
Nodes (6): Замечания, Повторная проверка — 2026-11-21, Ревью Ш-13. iOS: проект и карта, Что проверено ревьюером, Что сделано, Чтобы закрыть шаг

### Community 12 - "0001. Технологический стек"
Cohesion: 0.08
Nodes (21): 0001. Технологический стек, Контекст, Последствия, Решение, Ссылки, 0002. «ИИ понимает, движок планирует», Контекст, Последствия (+13 more)

### Community 13 - "postgres"
Cohesion: 0.06
Nodes (34): build_admins, build_elevation, build_tar, build_time_zones, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, serve_tiles (+26 more)

### Community 14 - "import_places.py"
Cohesion: 0.14
Nodes (11): build_record(), extract(), in_bbox(), load(), main(), merge_dropped(), report(), _ring() (+3 more)

### Community 15 - ".swiftlint.yml"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 16 - "tag_mapping.py"
Cohesion: 0.16
Nodes (15): category_for_food(), category_slug(), classify(), _clean(), _has_wiki(), parse_elevation(), pick_address(), pick_names() (+7 more)

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
Cohesion: 0.16
Nodes (10): _parse_days(), _parse_intervals(), parse_opening_hours(), _to_time(), record(), test_hours_simple(), test_hours_unparsed(), test_hours_variants() (+2 more)

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

### Community 25 - "Layout"
Cohesion: 0.12
Nodes (10): JolApp, .body, RootView, .body, InstallID, Build, Jol iOS, Layout (+2 more)

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
Cohesion: 0.12
Nodes (25): add_route_place(), check_event_refs(), clean_text(), like_pattern(), list_places(), _norm(), page_number(), parse_bool() (+17 more)

### Community 35 - "test_osm_pipeline.py"
Cohesion: 0.23
Nodes (7): collect(), relation_outer_members(), keys(), q(), test_collect_drops_outer_way_and_duplicate_node(), test_load_into_db_and_idempotent(), test_preexisting_duplicate_rows_are_merged_without_losing_data()

### Community 36 - "routing/service.py"
Cohesion: 0.08
Nodes (21): leg_seconds(), pick_default(), directions(), calculate_cost(), load_tariffs(), recommend(), _recommendation_rank(), Tariff (+13 more)

### Community 37 - "Ревью Ш-07, Ш-08, Ш-09. Данные мест"
Cohesion: 0.33
Nodes (5): Замечания, Отклонения модели данных от `TECH_PLAN.md §5`, Ревью Ш-07, Ш-08, Ш-09. Данные мест, Что проверено ревьюером, Что сделано

### Community 38 - "test_admin_validation.py"
Cohesion: 0.15
Nodes (18): format_hours_day(), parse_hours_day(), _parse_time(), validate_hours(), validate_place(), text(), place_form(), test_event_validation() (+10 more)

### Community 39 - "admin/api.py"
Cohesion: 0.11
Nodes (61): admin_get(), admin_post(), AdminError, AdminLoginRequired, categories_list(), category_edit(), _category_options(), category_save() (+53 more)

### Community 40 - "test_admin.py"
Cohesion: 0.15
Nodes (31): place_form_values(), get_place(), add_category(), add_place(), csrf_of(), logged_in(), login(), make_admin() (+23 more)

### Community 41 - "auth.py"
Cohesion: 0.13
Nodes (14): hash_password(), hash_token(), login(), LoginResult, logout(), new_token(), normalize_email(), password_error() (+6 more)

### Community 42 - "representative_point"
Cohesion: 0.23
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 43 - "test_places_api.py"
Cohesion: 0.11
Nodes (28): is_open_now(), add_place(), at(), make_route(), set_names(), test_categories(), test_curated_routes_published_only(), test_open_now_across_midnight() (+20 more)

### Community 44 - "transit.py"
Cohesion: 0.10
Nodes (14): _candidates(), find_transit_options(), get_network(), _in_service(), _line_key(), _local_hour(), _materialize(), _ride_leg() (+6 more)

### Community 45 - "import_transit.py"
Cohesion: 0.10
Nodes (20): database_url(), find_pbf(), apply_manual_stops(), build_network(), extract(), haversine_m(), load_seed(), localized_names() (+12 more)

### Community 46 - "get_settings"
Cohesion: 0.12
Nodes (14): get_sms_provider(), normalize_phone(), SmsProvider, _StubSmsProvider, get_settings(), meta(), signing_secret(), test_invalid_phone() (+6 more)

### Community 47 - "test_transit_search.py"
Cohesion: 0.20
Nodes (19): hop_speed_boost(), build(), _load(), _load_dev_network(), run(), search(), stop_row(), test_best_of_each_mode_is_kept() (+11 more)

### Community 49 - "pytest"
Cohesion: 0.12
Nodes (23): make_router(), test_parse_bbox_rejects(), load(), _router(), run(), test_client_error_mapping(), test_client_matrix_pairwise_fallback_marks_unreachable(), test_client_retries_connect_errors_only() (+15 more)

### Community 50 - "test_transit_import.py"
Cohesion: 0.19
Nodes (10): by_rel(), rows(), test_empty_extract_does_not_wipe_network(), test_metro_directions_share_stations(), test_migration_constraints(), test_short_relation_skipped(), test_stop_and_platform_are_one_stop(), test_unordered_relation_is_reordered_along_way_geometry() (+2 more)

### Community 51 - "test_otp.py"
Cohesion: 0.07
Nodes (16): Замечания (не исправлены, записаны), Проверки, Ревью Ш-25 — вход по почте (код), Что сделано, DevEmailProvider, EmailProvider, EmailSettings, get_email_provider() (+8 more)

### Community 53 - "Ревью Ш-10. Админка (минимум)"
Cohesion: 0.33
Nodes (5): Безопасность — проверено ревьюером, Замечания, Изменения модели данных vs `TECH_PLAN.md §5`, Ревью Ш-10. Админка (минимум), Что сделано

### Community 54 - "conftest.py"
Cohesion: 0.19
Nodes (6): chat_env(), client(), committed_auth_db_url(), recreate_database(), scratch_db_url(), test_db_url()

### Community 55 - "typing"
Cohesion: 0.15
Nodes (13): MatrixResult, RoutingUnavailable, _costing_body(), _loc(), parse_matrix(), ValhallaRouter, test_directions_partial_engine_failure(), route() (+5 more)

### Community 56 - "pathlib"
Cohesion: 0.18
Nodes (8): 1. Сборка тайлов (Ш-11), 2. Локальный просмотр (демо), 3. Хостинг, 4. Стили (Ш-12), maps/ — карта Jol (Ш-11, Ш-12), build(), interp(), name_expr()

### Community 57 - "dedupe.py"
Cohesion: 0.20
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 58 - "otp_api.py"
Cohesion: 0.24
Nodes (6): normalize_email(), _client_ip(), OtpRequest, OtpVerifyRequest, request_code(), verify_code()

### Community 59 - "Jol — технический план (ТЗ на реализацию)"
Cohesion: 0.22
Nodes (9): 10. Риски, которые держим в голове, 1. Цель первой версии (v1) и границы, 3. Архитектура, 4. Структура репозитория, 5. Модель данных (черновик, уточняется в шагах), 6. API (черновик), 7. Порядок фаз и вехи, 9. Тестирование (+1 more)

### Community 60 - "FakeRouter"
Cohesion: 0.12
Nodes (12): Замечания, Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20), Что сделано, Эталонные пары (лучший вариант), API маршрутов, Аэропорт, Повторное ревью на локальных сервисах, Предыдущая проверка без доступа к сервисам (+4 more)

### Community 61 - "test_directions.py"
Cohesion: 0.10
Nodes (20): check_mode(), Maneuver, NoRoute, RouteResult, RoutingError, encode_polyline6(), decode_polyline6(), TransitLeg (+12 more)

### Community 63 - "test_chat.py"
Cohesion: 0.08
Nodes (64): SendMessage, SlidingWindowLimiter, fetch_all(), FakeToolCall, parse_sse(), call(), day(), post() (+56 more)

### Community 64 - "Ревью доработки Ш-08: отношения OSM и связь ручных мест"
Cohesion: 0.40
Nodes (4): Замечания, Ревью доработки Ш-08: отношения OSM и связь ручных мест, Что проверено ревьюером, Что сделано

### Community 65 - "import_popular.py"
Cohesion: 0.21
Nodes (8): _bool(), CsvError, _int(), link_manual_to_osm(), _opt(), parse_rows(), test_real_csv_manual_rows_have_no_osm_twin(), test_validation()

### Community 66 - ".install"
Cohesion: 0.08
Nodes (6): APIClientTests, ClearedFlag, .value, ProfileTests, StubURLProtocol, .requests

### Community 67 - "test_llm.py"
Cohesion: 0.13
Nodes (33): collect(), ErrorEvent, LLMError, LLMTimeout, Message, ToolSpec, Usage, Call (+25 more)

### Community 70 - "SessionTokens"
Cohesion: 0.11
Nodes (11): AppContainer, EphemeralTokenStore, TokenStore, SessionStore, .query, SessionTokens, CodingKeys, accessToken (+3 more)

### Community 71 - "apple.py"
Cohesion: 0.10
Nodes (23): AppleKeyCache, AppleSignIn, challenge(), Challenge, fetch_keys(), sign_in(), verify_identity(), current_user() (+15 more)

### Community 72 - "TECH_PLAN.md"
Cohesion: 0.07
Nodes (23): Замечания и отложенное, Ревью координатора (2026-11-21), Ревью Ш-15 — главный экран, Что сделано, Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-16 — меню профиля (+15 more)

### Community 73 - "test_apple.py"
Cohesion: 0.26
Nodes (11): apple_jwks(), get_nonce(), issue(), private_key(), submit(), test_invalid_signature_does_not_consume_challenge(), test_outage_is_rate_limited(), test_rejects_expired_nonce_and_wrong_algorithm_before_fetch() (+3 more)

### Community 74 - "psycopg"
Cohesion: 0.18
Nodes (12): apply_migrations(), checksum_of(), discover(), main(), MigrationError, test_applies_on_empty_db_and_rerun_is_noop(), test_changed_checksum_fails(), test_new_migration_applied_and_failure_rolls_back() (+4 more)

### Community 75 - "execute"
Cohesion: 0.17
Nodes (8): delete_account(), _digest(), issue(), _latest(), _lock(), verify(), lock_identity(), execute()

### Community 76 - "send_message"
Cohesion: 0.09
Nodes (31): Что сделано, _add_graph_node(), _chat_json(), create_chat(), get_chat(), lease_sec(), list_chats(), _own_chat() (+23 more)

### Community 77 - "chat/api.py"
Cohesion: 0.08
Nodes (16): CreateChat, _finish(), _save_detached(), client_ip(), install_id(), make_llm(), error_payload(), run_turn() (+8 more)

### Community 79 - "layout.py"
Cohesion: 0.14
Nodes (25): _assign_activities(), assign(), best_day(), item_for(), _assign_meals(), _at(), _centroid(), DayPlan (+17 more)

### Community 80 - "execute"
Cohesion: 0.22
Nodes (8): move_route_item(), fetch_one(), test_email_sign_in_and_replay(), test_dedupe_key_is_unique(), test_failed_statement_raises(), test_insert_and_select_job(), test_parameters_are_not_interpolated(), test_postgis_available()

### Community 83 - "test_popular_import.py"
Cohesion: 0.30
Nodes (11): import_csv(), _csv(), _places(), q(), test_far_or_differently_named_manual_row_is_left_alone(), test_import_is_idempotent(), test_import_small_fixture(), test_manual_row_gets_osm_id_attached() (+3 more)

### Community 84 - "APIClient"
Cohesion: 0.09
Nodes (12): APIClient, RefreshBody, Refresher, APIError, invalidBaseURL, invalidResponse, .isUnauthorized, network (+4 more)

### Community 85 - "test_airport.py"
Cohesion: 0.21
Nodes (12): airport_routes(), build_network(), bus(), ride_from_terminal(), test_airport_real_pbf(), test_airport_real_valhalla(), find(), test_import_sends_stable_manual_stop_ids() (+4 more)

### Community 86 - "RoutingProvider"
Cohesion: 0.14
Nodes (6): CI, Замечания, Реальные замеры, Ревью Ш-20. Движок маршрутизации (Valhalla), Что сделано, RoutingProvider

### Community 87 - "XCTestCase"
Cohesion: 0.24
Nodes (3): SessionStoreTests, FeatureGalleryUITests, MapLaunchUITests

### Community 89 - "auth/api.py"
Cohesion: 0.29
Nodes (6): bearer_token(), delete_me(), logout(), me(), refresh(), RefreshRequest

### Community 90 - "test_planner_layout.py"
Cohesion: 0.15
Nodes (27): DirectionsLegs, _at(), check_invariants(), dates(), legs_provider(), mk(), names(), Rain (+19 more)

### Community 91 - "committed_auth_db_url"
Cohesion: 0.40
Nodes (4): Замечания (не исправлены, записаны), Проверки, Ревью Ш-24 — схема аккаунтов и сессии, Что сделано

### Community 92 - "entitlements"
Cohesion: 0.50
Nodes (4): path, properties, entitlements, com.apple.developer.applesignin

### Community 93 - "Foundation"
Cohesion: 0.08
Nodes (16): Foundation, ServerMeta, CodingKeys, minIOSVersion, version, DeleteState, deleting, failed (+8 more)

### Community 94 - "Settings"
Cohesion: 0.31
Nodes (8): Settings, get_llm_provider(), get_resilient_llm(), settings(), test_fake_is_default_in_dev_and_test(), test_fake_is_rejected_in_prod(), test_real_provider_is_open_and_gives_clear_error(), test_resilient_factory_uses_config()

### Community 95 - "test_planner_scoring.py"
Cohesion: 0.14
Nodes (21): _matches(), resolve(), _tokens(), no_event_bonus(), UnknownCrowd, make_place(), scored(), test_an_interest_match_beats_a_little_popularity() (+13 more)

### Community 96 - "llm/__init__.py"
Cohesion: 0.15
Nodes (10): Что сделано, Completion, Done, LLMNotConfigured, parse_tool_args(), TextDelta, ToolArgsError, ToolCall (+2 more)

### Community 97 - "brief.py"
Cohesion: 0.13
Nodes (15): _build_trip(), _update_trip_brief(), apply_update(), brief_data_block(), BriefError, BriefUpdate, _clean_items(), empty_brief() (+7 more)

### Community 98 - "AppLanguage"
Cohesion: 0.09
Nodes (11): AppLanguage, english, .id, .nativeName, russian, system, LanguageSettings, .code (+3 more)

### Community 99 - ".signInWithApple"
Cohesion: 0.10
Nodes (18): CodingKeys, refreshToken, .body, AppleCredential, CodingKeys, authorizationCode, identityToken, Challenge (+10 more)

### Community 100 - "Place"
Cohesion: 0.11
Nodes (7): earliest_start(), load_hours(), _minutes(), visit_minutes(), windows(), _Ctx, Place

### Community 101 - "SwiftUI"
Cohesion: 0.10
Nodes (15): AuthenticationServices, PlaceholderScreen, .body, JolFont, ChatScreen, .body, PlacesScreen, .body (+7 more)

### Community 102 - "Что сделано"
Cohesion: 0.13
Nodes (10): Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-14 — iOS-каркас, Что сделано, L10n, AuthService, AuthState (+2 more)

### Community 103 - "test_account_deletion.py"
Cohesion: 0.20
Nodes (13): apple_login(), auth(), count(), FakeGrants, otp_sign_in(), test_apple_delete_enqueues_revoke_and_allows_reregistration(), test_apple_without_stored_token_deletes_and_logs_gap(), test_code_exchange_problems_never_block_sign_in() (+5 more)

### Community 104 - "apple_grants.py"
Cohesion: 0.14
Nodes (10): Ревью координатора (2026-11-21), _exchange_code(), AppleGrants, client_secret(), credentials_configured(), decrypt_token(), encrypt_token(), _fernet() (+2 more)

### Community 105 - "places/schemas.py"
Cohesion: 0.18
Nodes (16): CategoriesList, Category, CategoryRef, CuratedRouteDetail, CuratedRouteItem, CuratedRoutesList, CuratedRouteSummary, DayHours (+8 more)

### Community 106 - "TravelTimes"
Cohesion: 0.15
Nodes (6): Правила, HaversineMatrix, _plan_seconds(), RouterMatrix, TravelMatrixProvider, TravelTimes

### Community 107 - "select_candidates"
Cohesion: 0.25
Nodes (13): select_candidates(), brief(), fixture_places(), names(), test_crowd_source_is_used_for_quiet_travellers(), test_event_bonus_hook_is_applied(), test_incomplete_brief_is_refused(), test_interests_and_memory_change_the_order() (+5 more)

### Community 108 - "candidates.py"
Cohesion: 0.15
Nodes (6): _area(), Candidate, MustHave, _resolve_must_have(), trip_days(), place_from_row()

### Community 110 - "tools.py"
Cohesion: 0.16
Nodes (11): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-30 — гостевой чат, Что сделано, handle_tool(), AddGraphNodeArgs, NoArgs (+3 more)

### Community 111 - "load_prompt"
Cohesion: 0.18
Nodes (9): load_prompt(), Prompt, versions(), test_every_prompt_exists_in_both_languages(), test_guest_prompt_has_no_memory_and_only_search_tool(), test_render_fills_today(), test_trip_brief_asks_dates_then_budget_then_lodging(), test_unknown_locale_falls_back_to_english_and_unknown_prompt_fails() (+1 more)

### Community 112 - "Endpoint"
Cohesion: 0.22
Nodes (7): Endpoint, Method, delete, get, patch, post, put

### Community 113 - "ChatPanel"
Cohesion: 0.16
Nodes (10): ChatPanel, .body, CollapsedChatBar, .body, EdgeSwipeStrip, .body, HomeScreen, .attribution (+2 more)

### Community 114 - "places/api.py"
Cohesion: 0.30
Nodes (9): _geojson(), get_curated_route(), get_place(), list_categories(), list_curated_routes(), list_places(), _locale(), _summary() (+1 more)

### Community 115 - "AppConfig"
Cohesion: 0.22
Nodes (5): AppConfig, .apiBaseURL, .isSimulator, .mapStyleURL, APIBaseURLTests

### Community 116 - "scoring.py"
Cohesion: 0.23
Nodes (9): Resolved, _clip01(), interest_match(), intolerance(), pick_pool(), rank(), Score, score_place() (+1 more)

### Community 117 - "View"
Cohesion: 0.21
Nodes (10): .body, AboutScreen, .body, .version, HelpScreen, .body, LanguageScreen, .body (+2 more)

### Community 118 - "LLMProvider"
Cohesion: 0.17
Nodes (7): Замечания, Проверки, Ревью координатора (2026-11-21), Ревью Ш-29 — слой LLM (fake-провайдер), LLMProvider, TokenCounter, Ф8. Чат с ИИ (SSOT §4, §11.1–11.2)

### Community 119 - ".body"
Cohesion: 0.19
Nodes (8): .content, LanguagePicker, .body, ProfileScreen, .body, FeatureGalleryScreen, .body, .statusRow

### Community 120 - "XCTest"
Cohesion: 0.19
Nodes (3): AppConfigTests, Jol, XCTest

### Community 121 - "HttpAppleGrants"
Cohesion: 0.27
Nodes (3): AppleGrantError, _error(), HttpAppleGrants

### Community 122 - "places/service.py"
Cohesion: 0.17
Nodes (6): _covers(), group_hours(), like_pattern(), parse_bbox(), test_like_pattern_escapes(), test_parse_bbox_ok()

### Community 124 - "SidebarPanel"
Cohesion: 0.18
Nodes (6): .body, MapScreen, .body, SidebarPanel, .body, .panel

### Community 125 - "Ревью Ш-33 — отбор кандидатов"
Cohesion: 0.20
Nodes (6): Замечания и отложенное, Проверки, Ревью координатора (2026-11-21), Ревью Ш-33 — отбор кандидатов, Что сделано, Selection

### Community 126 - "weather.py"
Cohesion: 0.29
Nodes (3): Forecast, is_rainy(), UnknownForecast

### Community 127 - "StubAppleGrants"
Cohesion: 0.25
Nodes (4): Отзыв токена Apple, Что сделано, MissingCredentialsGrants, StubAppleGrants

### Community 128 - "ProfileMenuContent"
Cohesion: 0.29
Nodes (4): ProfileMenuContent, .deleteFailed, ProfileMenuSheet, .body

### Community 129 - "JolColor"
Cohesion: 0.39
Nodes (3): JolColor, UIColor, UIKit

### Community 130 - "SignInEntryView"
Cohesion: 0.29
Nodes (3): SignInEntryView, .body, .accountSection

### Community 131 - "pool_sizes"
Cohesion: 0.29
Nodes (6): places_per_must_have(), pool_sizes(), PoolSizes, test_must_have_count_grows_with_the_trip(), test_a_longer_trip_or_denser_pace_never_shrinks_the_pool(), test_pool_sizes()

### Community 132 - "fixture"
Cohesion: 0.25
Nodes (5): apple_signin(), delivery(), ec_key(), rsa_key(), settings()

### Community 133 - "http_grants"
Cohesion: 0.32
Nodes (6): http_grants(), pem(), test_http_exchange_code(), test_http_revoke_outcomes(), test_http_revoke_request_and_client_secret(), handler()

### Community 134 - "Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки"
Cohesion: 0.29
Nodes (6): Замечания и отложенное, Исправления (2026-11-21), Проверка исправлений координатором, Проверки, Ревью координатора (2026-11-21), Ревью Ш-31 — чат зарегистрированного и сбор параметров поездки

### Community 138 - "Ревью Ш-17. API мест (+ серверная часть Ш-19)"
Cohesion: 0.33
Nodes (5): Замечания, Ревью Ш-17. API мест (+ серверная часть Ш-19), Статус шагов, Что проверено ревьюером, Что сделано

### Community 139 - "Ревью Ш-34 — раскладка по дням и времени"
Cohesion: 0.33
Nodes (5): Не сделано / не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-34 — раскладка по дням и времени, Структуры плана (в памяти; Ш-36 сохранит их)

## Knowledge Gaps
- **72 isolated node(s):** `.body`, `.isSimulator`, `UIKit`, `.body`, `system` (+67 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 806 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **40 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Что сделано` connect `Что сделано` to `AppLanguage`, `.signInWithApple`, `SessionTokens`, `apple.py`, `AppConfig`, `APIClient`, `Layout`, `.stream`, `Foundation`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Are the 66 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 66 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.body`, `.isSimulator`, `UIKit` to the rest of the system?**
  _72 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Personal Route Building (whole trip, by day)` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `AppleSignIn` connect `apple.py` to `Что сделано`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Should `worker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0858843537414966 - nodes in this community are weakly interconnected._
- **Why does `APIClient` connect `APIClient` to `.install`, `merge_place`, `8. Шаги`, `SessionTokens`, `Что сделано`, `TECH_PLAN.md`, `Jol — технический план (ТЗ на реализацию)`, `test_otp.py`, `Layout`, `.stream`, `Foundation`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._