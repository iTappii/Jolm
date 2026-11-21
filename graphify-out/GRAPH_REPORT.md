# Graph Report - Jol v2  (2026-11-21)

## Corpus Check
- 154 files · ~78,447 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 24 file(s) not represented in the graph (top: (none) 6, .csv 4, .xcstrings 2)

## Summary
- 1617 nodes · 3987 edges · 95 communities (80 shown, 15 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 269 edges (avg confidence: 0.87)
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
- admin/service.py
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
- get_settings
- test_transit_search.py
- MapView
- pytest
- test_transit_import.py
- email.py
- Ревью Ш-10. Админка (минимум)
- test_db_url
- typing
- pathlib
- dedupe.py
- get_settings
- Jol — технический план (ТЗ на реализацию)
- FakeRouter
- test_directions.py
- TECH_PLAN.md
- Ревью доработки Ш-08: отношения OSM и связь ручных мест
- import_popular.py
- Ревью Ш-22. Стоимость и сводка вариантов
- fetch_pbf.sh
- README.md
- SessionStore
- apple.py
- AppleSignInView
- test_apple.py
- psycopg
- AppError
- Ревью Ш-20. Движок маршрутизации (Valhalla)
- Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)
- H
- routing/service.py
- execute
- test_popular_import.py
- .signIn
- test_otp.py
- RoutingProvider
- Что сделано
- pathlib
- auth/api.py
- SmsProvider
- committed_auth_db_url
- entitlements
- EmailProvider

## God Nodes (most connected - your core abstractions)
1. `fetch_one()` - 82 edges
2. `conn()` - 58 edges
3. `execute()` - 45 edges
4. `fetch_all()` - 40 edges
5. `get_settings()` - 38 edges
6. `AppError` - 38 edges
7. `db()` - 35 edges
8. `re()` - 32 edges
9. `oe()` - 31 edges
10. `ae()` - 27 edges

## Surprising Connections (you probably didn't know these)
- `Что сделано` --references--> `FakeRouter`  [INFERRED]
  docs/reviews/Ш-21.md → server/app/routing/fake.py
- `Аэропорт` --references--> `FakeRouter`  [INFERRED]
  docs/reviews/Ш-22.md → server/app/routing/fake.py
- `Предыдущая проверка без доступа к сервисам` --references--> `FakeRouter`  [INFERRED]
  docs/reviews/Ш-22.md → server/app/routing/fake.py
- `Что сделано` --references--> `SessionStore`  [INFERRED]
  docs/reviews/Ш-24.md → ios/Jol/Core/SessionStore.swift
- `iOS` --references--> `SessionStore`  [INFERRED]
  docs/reviews/Ш-26.md → ios/Jol/Core/SessionStore.swift

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Crowdsourced Data and Bonus Flow** — jol_ssot_user_content, jol_ssot_content_moderation, jol_ssot_bonus_system, jol_ssot_demand_coefficient [EXTRACTED 1.00]
- **Living Plan Adaptation Loop** — jol_ssot_principle_living_plan, jol_ssot_weather_recheck, jol_ssot_mountain_morning_alert, jol_ssot_place_crowding, jol_ssot_open_meteo [EXTRACTED 1.00]
- **Route Building Inputs** — jol_ssot_route_building, jol_ssot_trip_budget, jol_ssot_mandatory_wishes, jol_ssot_crowd_tolerance, jol_ssot_memory_personalization [EXTRACTED 1.00]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]

## Communities (95 total, 15 thin omitted)

### Community 0 - "Personal Route Building (whole trip, by day)"
Cohesion: 0.06
Nodes (46): Jol Project Instructions (CLAUDE.md), Almaty Launch Geography, Authentication (email OTP, Sign in with Apple, SMS OTP), Bonus System (1 bonus = ~1 tenge), Bookings and Orders via Partner APIs, Dynamic Single-Branch Chat Graph, Content Verification (auto-filter + moderation), Crowd Tolerance Preference (+38 more)

### Community 1 - "worker.py"
Cohesion: 0.07
Nodes (31): Database, backoff_seconds(), _cleanup_done_jobs(), enqueue(), enqueue_due_schedules(), _main(), process_batch(), register() (+23 more)

### Community 2 - "JolApp"
Cohesion: 0.15
Nodes (6): CoreLocation, JolApp, .body, AlmatyCamera, MapLibre, SwiftUI

### Community 3 - "merge_place"
Cohesion: 0.11
Nodes (12): merge_place(), link_manual_to_osm(), Jol — передача работы (2026-11-21), Как работаем, Коммиты, Нужно от владельца, Окружение (этот Mac), Статус плана (+4 more)

### Community 4 - "8. Шаги"
Cohesion: 0.11
Nodes (18): 8. Шаги, Ф0. Основа проекта, Ф10. Готовый маршрут в приложении (SSOT §11.3), Ф11. Погода (SSOT §7.1–7.2), Ф12. Память (SSOT §8), Ф13. Скачивание, история, боковая панель, Ф14. Пользовательский контент и бонусы (SSOT §10), Ф15. Загруженность (SSOT §7.3) `[предложено, §2 п.5]` (+10 more)

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
Cohesion: 0.12
Nodes (10): Замечания, Повторная проверка — 2026-11-21, Ревью Ш-13. iOS: проект и карта, Что проверено ревьюером, Что сделано, Чтобы закрыть шаг, Foundation, AppConfig (+2 more)

### Community 12 - "0001. Технологический стек"
Cohesion: 0.08
Nodes (20): 0001. Технологический стек, Контекст, Последствия, Решение, Ссылки, 0002. «ИИ понимает, движок планирует», Контекст, Последствия (+12 more)

### Community 13 - "postgres"
Cohesion: 0.06
Nodes (34): build_admins, build_elevation, build_tar, build_time_zones, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, serve_tiles (+26 more)

### Community 14 - "import_places.py"
Cohesion: 0.15
Nodes (11): build_record(), extract(), in_bbox(), load(), main(), merge_dropped(), report(), _ring() (+3 more)

### Community 15 - ".swiftlint.yml"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 16 - "tag_mapping.py"
Cohesion: 0.19
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

### Community 34 - "admin/service.py"
Cohesion: 0.13
Nodes (24): check_event_refs(), clean_text(), format_hours_day(), like_pattern(), list_places(), _norm(), page_number(), parse_bool() (+16 more)

### Community 35 - "test_osm_pipeline.py"
Cohesion: 0.23
Nodes (7): collect(), relation_outer_members(), keys(), q(), test_collect_drops_outer_way_and_duplicate_node(), test_load_into_db_and_idempotent(), test_preexisting_duplicate_rows_are_merged_without_losing_data()

### Community 36 - "routing/service.py"
Cohesion: 0.06
Nodes (29): CategoriesList, Category, CategoryRef, CuratedRouteDetail, CuratedRouteItem, CuratedRoutesList, CuratedRouteSummary, DayHours (+21 more)

### Community 37 - "Ревью Ш-07, Ш-08, Ш-09. Данные мест"
Cohesion: 0.33
Nodes (5): Замечания, Отклонения модели данных от `TECH_PLAN.md §5`, Ревью Ш-07, Ш-08, Ш-09. Данные мест, Что проверено ревьюером, Что сделано

### Community 38 - "test_admin_validation.py"
Cohesion: 0.16
Nodes (16): parse_hours_day(), validate_place(), number(), text(), place_form(), test_event_validation(), test_hours_day_errors(), test_hours_day_multiple_intervals_sorted() (+8 more)

### Community 39 - "admin/api.py"
Cohesion: 0.12
Nodes (60): admin_get(), admin_post(), AdminError, AdminLoginRequired, categories_list(), category_edit(), _category_options(), category_save() (+52 more)

### Community 40 - "test_admin.py"
Cohesion: 0.18
Nodes (30): place_form_values(), get_place(), fetch_one(), add_category(), add_place(), csrf_of(), logged_in(), login() (+22 more)

### Community 41 - "auth.py"
Cohesion: 0.12
Nodes (15): hash_password(), hash_token(), login(), LoginResult, logout(), new_token(), normalize_email(), password_error() (+7 more)

### Community 42 - "representative_point"
Cohesion: 0.23
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 43 - "fetch_all"
Cohesion: 0.06
Nodes (50): Замечания, Ревью Ш-17. API мест (+ серверная часть Ш-19), Статус шагов, Что проверено ревьюером, Что сделано, fetch_all(), _geojson(), get_curated_route() (+42 more)

### Community 44 - "transit.py"
Cohesion: 0.12
Nodes (14): _candidates(), find_transit_options(), get_network(), _in_service(), _line_key(), _local_hour(), _materialize(), _ride_leg() (+6 more)

### Community 45 - "import_transit.py"
Cohesion: 0.10
Nodes (20): database_url(), find_pbf(), apply_manual_stops(), build_network(), extract(), haversine_m(), load_seed(), localized_names() (+12 more)

### Community 46 - "get_settings"
Cohesion: 0.16
Nodes (13): get_sms_provider(), normalize_phone(), _StubSmsProvider, get_settings(), Settings, meta(), signing_secret(), test_invalid_phone() (+5 more)

### Community 47 - "test_transit_search.py"
Cohesion: 0.20
Nodes (19): hop_speed_boost(), build(), _load(), _load_dev_network(), run(), search(), stop_row(), test_best_of_each_mode_is_kept() (+11 more)

### Community 48 - "MapView"
Cohesion: 0.18
Nodes (3): MapView, Coordinator, Ф3. Карта

### Community 49 - "pytest"
Cohesion: 0.15
Nodes (19): parse_matrix(), test_parse_bbox_rejects(), load(), _router(), run(), test_client_error_mapping(), test_client_matrix_pairwise_fallback_marks_unreachable(), test_client_retries_connect_errors_only() (+11 more)

### Community 50 - "test_transit_import.py"
Cohesion: 0.12
Nodes (14): sconn(), sconn(), by_rel(), network(), rows(), sconn(), test_empty_extract_does_not_wipe_network(), test_metro_directions_share_stations() (+6 more)

### Community 51 - "email.py"
Cohesion: 0.13
Nodes (6): DevEmailProvider, EmailSettings, get_email_provider(), normalize_email(), SmtpEmailProvider, test_email_dev_stub_is_disabled_in_production()

### Community 53 - "Ревью Ш-10. Админка (минимум)"
Cohesion: 0.33
Nodes (5): Безопасность — проверено ревьюером, Замечания, Изменения модели данных vs `TECH_PLAN.md §5`, Ревью Ш-10. Админка (минимум), Что сделано

### Community 54 - "test_db_url"
Cohesion: 0.24
Nodes (6): recreate_database(), scratch_db_url(), test_db_url(), test_concurrent_identity_creation_and_refresh(), login(), rotate_once()

### Community 55 - "typing"
Cohesion: 0.13
Nodes (14): Maneuver, MatrixResult, NoRoute, RouteResult, RoutingError, RoutingUnavailable, _costing_body(), _loc() (+6 more)

### Community 56 - "pathlib"
Cohesion: 0.18
Nodes (8): 1. Сборка тайлов (Ш-11), 2. Локальный просмотр (демо), 3. Хостинг, 4. Стили (Ш-12), maps/ — карта Jol (Ш-11, Ш-12), build(), interp(), name_expr()

### Community 57 - "dedupe.py"
Cohesion: 0.20
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 58 - "get_settings"
Cohesion: 0.10
Nodes (9): _client_ip(), OtpRequest, OtpVerifyRequest, request_code(), verify_code(), JsonFormatter, setup_logging(), lifespan() (+1 more)

### Community 59 - "Jol — технический план (ТЗ на реализацию)"
Cohesion: 0.22
Nodes (9): 10. Риски, которые держим в голове, 1. Цель первой версии (v1) и границы, 3. Архитектура, 4. Структура репозитория, 5. Модель данных (черновик, уточняется в шагах), 6. API (черновик), 7. Порядок фаз и вехи, 9. Тестирование (+1 more)

### Community 60 - "FakeRouter"
Cohesion: 0.26
Nodes (7): check_mode(), encode_polyline6(), FakeRouter, haversine_m(), test_fake_matrix_shape_and_diagonal(), test_fake_route_speeds_and_order(), test_fake_unreachable_is_none_and_noroute()

### Community 61 - "test_directions.py"
Cohesion: 0.09
Nodes (19): create_app(), decode_polyline6(), client(), TransactionalDatabase, directions_api(), StubDatabase, test_directions_contract_and_almaty_tariff_date(), test_directions_empty_vs_unavailable() (+11 more)

### Community 63 - "TECH_PLAN.md"
Cohesion: 0.25
Nodes (4): Замечания (не исправлены, записаны), Проверки, Ревью Ш-25 — вход по почте (код), Что сделано

### Community 64 - "Ревью доработки Ш-08: отношения OSM и связь ручных мест"
Cohesion: 0.40
Nodes (4): Замечания, Ревью доработки Ш-08: отношения OSM и связь ручных мест, Что проверено ревьюером, Что сделано

### Community 65 - "import_popular.py"
Cohesion: 0.23
Nodes (7): _bool(), CsvError, _int(), _opt(), parse_rows(), test_real_csv_manual_rows_have_no_osm_twin(), test_validation()

### Community 66 - "Ревью Ш-22. Стоимость и сводка вариантов"
Cohesion: 0.33
Nodes (6): API маршрутов, Аэропорт, Повторное ревью на локальных сервисах, Предыдущая проверка без доступа к сервисам, Ревью Ш-22. Стоимость и сводка вариантов, Тарифы

### Community 70 - "SessionStore"
Cohesion: 0.18
Nodes (7): SessionStore, .query, SessionTokens, CodingKeys, accessToken, refreshToken, Security

### Community 71 - "apple.py"
Cohesion: 0.13
Nodes (17): AppleKeyCache, AppleSignIn, challenge(), Challenge, fetch_keys(), sign_in(), verify_identity(), current_user() (+9 more)

### Community 72 - "AppleSignInView"
Cohesion: 0.15
Nodes (11): Что делать дальше, iOS, Замечания, Проверки, Ревью Ш-26 — Sign in with Apple, Сервер, AppleSignInView, .body (+3 more)

### Community 73 - "test_apple.py"
Cohesion: 0.26
Nodes (11): apple_jwks(), get_nonce(), issue(), private_key(), submit(), test_invalid_signature_does_not_consume_challenge(), test_outage_is_rate_limited(), test_rejects_expired_nonce_and_wrong_algorithm_before_fetch() (+3 more)

### Community 74 - "psycopg"
Cohesion: 0.25
Nodes (8): apply_migrations(), checksum_of(), discover(), main(), MigrationError, test_applies_on_empty_db_and_rerun_is_noop(), test_changed_checksum_fails(), test_new_migration_applied_and_failure_rolls_back()

### Community 75 - "AppError"
Cohesion: 0.22
Nodes (9): _digest(), issue(), _latest(), _lock(), verify(), AppError, health(), test_failed_delivery_spends_rate_slot_and_keeps_code_inactive() (+1 more)

### Community 76 - "Ревью Ш-20. Движок маршрутизации (Valhalla)"
Cohesion: 0.40
Nodes (4): CI, Замечания, Реальные замеры, Ревью Ш-20. Движок маршрутизации (Valhalla)

### Community 77 - "Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20)"
Cohesion: 0.40
Nodes (4): Замечания, Ревью Ш-21. Общественный транспорт (+ общий файл OSM из ревью Ш-20), Что сделано, Эталонные пары (лучший вариант)

### Community 79 - "routing/service.py"
Cohesion: 0.24
Nodes (7): DirectionOption, DirectionStep, get_directions(), _road_option(), _traffic_max(), _transit_option(), TransitOption

### Community 80 - "execute"
Cohesion: 0.11
Nodes (10): add_route_place(), move_route_item(), remove_route_item(), _renumber(), execute(), test_dedupe_key_is_unique(), test_failed_statement_raises(), test_insert_and_select_job() (+2 more)

### Community 83 - "test_popular_import.py"
Cohesion: 0.30
Nodes (11): import_csv(), _csv(), _places(), q(), test_far_or_differently_named_manual_row_is_left_alone(), test_import_is_idempotent(), test_import_small_fixture(), test_manual_row_gets_osm_id_attached() (+3 more)

### Community 84 - ".signIn"
Cohesion: 0.22
Nodes (6): AuthenticationServices, AppleIdentityToken, CodingKeys, identityToken, AppleSignInAPI, Challenge

### Community 85 - "test_otp.py"
Cohesion: 0.16
Nodes (6): delivery(), otp_settings(), test_email_code_expiry_and_failed_attempts(), test_email_sign_in_and_replay(), test_ip_limit_shared_across_destinations_and_forwarded_headers(), test_smtp_adapter_requires_tls_before_credentials_and_send()

### Community 86 - "RoutingProvider"
Cohesion: 0.18
Nodes (4): Что сделано, RoutingProvider, make_router(), test_make_router_without_url_is_fake()

### Community 87 - "Что сделано"
Cohesion: 0.22
Nodes (5): Что сделано, SessionStoreTests, MapLaunchUITests, Jol, XCTest

### Community 89 - "auth/api.py"
Cohesion: 0.39
Nodes (4): logout(), me(), refresh(), RefreshRequest

### Community 90 - "SmsProvider"
Cohesion: 0.29
Nodes (4): Проверки, Ревью Ш-27 — вход по SMS, SmsProvider, 2. Рабочие допущения по открытым вопросам

### Community 91 - "committed_auth_db_url"
Cohesion: 0.33
Nodes (4): Замечания (не исправлены, записаны), Проверки, Ревью Ш-24 — схема аккаунтов и сессии, committed_auth_db_url()

### Community 92 - "entitlements"
Cohesion: 0.50
Nodes (4): path, properties, entitlements, com.apple.developer.applesignin

## Knowledge Gaps
- **19 isolated node(s):** `Security`, `accessToken`, `refreshToken`, `.query`, `AuthenticationServices` (+14 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 496 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `merge_place()` connect `merge_place` to `import_places.py`, `Что сделано`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Are the 55 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 55 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Security`, `accessToken`, `refreshToken` to the rest of the system?**
  _19 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Personal Route Building (whole trip, by day)` be split into smaller, more focused modules?**
  _Cohesion score 0.05519480519480519 - nodes in this community are weakly interconnected._
- **Why does `fetch_one()` connect `test_admin.py` to `worker.py`, `admin/service.py`, `routing/service.py`, `apple.py`, `admin/api.py`, `auth.py`, `AppError`, `fetch_all`, `execute`, `test_osm_import.py`, `test_otp.py`, `get_settings`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Should `worker.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06939890710382514 - nodes in this community are weakly interconnected._
- **Why does `SessionStore` connect `SessionStore` to `AppleSignInView`, `Что сделано`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._