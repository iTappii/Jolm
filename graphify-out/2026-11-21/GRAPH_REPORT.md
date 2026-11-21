# Graph Report - Jol v2  (2026-11-21)

## Corpus Check
- 483 files · ~291,671 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 41 file(s) not represented in the graph (top: .sse 11, (none) 7, .csv 4)

## Summary
- 6537 nodes · 18046 edges · 274 communities (213 shown, 61 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 1250 edges (avg confidence: 0.87)
- Token cost: 211,973 input · 0 output

## Graph Freshness
- Built from commit: `6a07bcdb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Sendable
- api (106)
- conftest.py
- htmx-1.9.12.min (105)
- TripMapModel (104)
- CodingKey
- execute
- DirectionOption
- budget (78)
- routing/service.py
- ChatModelTests
- test_account_deletion.py
- db.py
- build (68)
- test_weather.py
- config.py
- APIClientTests (64)
- layout (61)
- edit (61)
- test_live_plan (59)
- service (59)
- api (59)
- test_trip_edits.py
- PlaceActionsUITests
- test_submissions (55)
- FavoritesModel (54)
- BookingSheet
- ProfileScreen (52)
- deps (52)
- import_places (51)
- Identifiable
- test_chat (51)
- APIError
- BookingModels (50)
- PlacesModel (50)
- Ш-32 (47)
- DirectionsTests (47)
- test_directions (47)
- CrowdModel (45)
- Ш-31 (45)
- Ш-44-server (45)
- test_admin (45)
- test_planner_layout (45)
- DirectionsModel (43)
- store (43)
- SignInModel (42)
- JolFont
- test_places_api (42)
- test_popular_import (41)
- PlaceCardTabs (40)
- SignInTests (40)
- test_routing (40)
- test_osm_import (39)
- CrowdBlock
- base (39)
- test_analytics.py
- LocationProvider (38)
- edit_tools (38)
- ChatState (37)
- memory/jobs.py
- SessionStore (36)
- analytics/service.py
- adapters (36)
- store (36)
- test_llm.py
- .nodeCenter
- docker-compose (35)
- test_osm_pipeline (34)
- test_transit_import (34)
- test_chat_guest (34)
- EventsModel
- typing
- ProfileModel (33)
- enqueue
- UITestSupport
- DirectionsFormatting (32)
- PlaceCardView
- ChatModel
- open_meteo.py
- test_planner_scoring (32)
- transit (32)
- _macros (30)
- test_transit_search (29)
- auth
- valhalla (29)
- PlaceActionsTests
- EventModels (28)
- brief (28)
- email.py
- ServerMeta
- ci (27)
- PlacesTests (27)
- read (27)
- test_planner_candidates (26)
- AppConfig (26)
- .summary
- Foundation
- test_memory.py
- schemas (24)
- AppError
- AppContainer
- ChatChainUITests
- messages (21)
- scoring (21)
- AppLanguage (20)
- SSEParserTests (20)
- PlaceModels (20)
- service (20)
- test_clientip.py
- CLAUDE (19)
- ChatService
- JOL_SSOT (19)
- schemas (19)
- AuthService
- SwiftUI
- MapCoordinator
- test_apple (17)
- TECH_PLAN (17)
- PlaceCategoryStyle (17)
- test_planner_budget.py
- XCTestCase
- candidates.py
- test_airport (17)
- geometry (16)
- import_transit.py
- HANDOFF (16)
- DirectionsModels (16)
- HomeScreenUITests (16)
- test_bookings (16)
- Ш-20 (15)
- test_ratelimit.py
- dedupe (14)
- JOL_SSOT (14)
- bonus_policy.py
- .swiftlint (14)
- psycopg
- live/engine.py
- StubURLProtocol
- GeoBounds
- fetch_all
- load_prompt
- README (13)
- get_settings
- Database
- ChainNode
- JOL_SSOT (12)
- Ш-07-09 (12)
- TripDayListView
- planner/hours.py
- SignInGateUITests (12)
- trip_brief.en.v4 (12)
- HaversineMatrix
- ChatPanel
- DirectionsUITests
- ChainNodesTests
- TripMapUITests
- Ш-11-12 (10)
- Ш-14 (10)
- Kind
- .report
- test_trips_followups.py
- PlacesUITests
- serve (9)
- load_memory
- project (9)
- Ш-18 (8)
- Ш-23b-server (8)
- resolve
- project (8)
- project (8)
- search_events
- Failure
- TECH_PLAN (7)
- ChatEvent
- BookingModel
- ChatFailure
- project (7)
- jol-logo (7)
- CodingKeys
- Деплой Jol: рабочая инструкция (Ш-51)
- pg-common.sh
- Ш-01-03-06 (6)
- Ш-17 (6)
- Ш-15 (6)
- CodingKeys
- .create
- project (6)
- options
- Ш-02 (5)
- Ш-22a (5)
- project (5)
- project (5)
- Ш-10 (4)
- Ш-23 (4)
- project (4)
- project (4)
- jol-icon-1024 (4)
- jol-icon (4)
- environment
- Ш-23 (3)
- icon-1024 (3)
- CodingKeys
- README (3)
- build_tiles (3)
- fetch_pbf (2)
- Ш-26 (2)
- pyproject (1)
- TECH_PLAN (1)
- CodingKeys
- Answer
- .makeModel
- analytics/events.py
- deploy.sh
- postgres
- FavoritesUITests
- postgres
- metrics.py
- .current
- ChatReductionTests
- resolve
- middleware.py
- api
- worker
- cli.py
- places/api.py
- services
- healthcheck
- _retention_cleanup
- migrate
- upsert.py
- State
- CodingKeys
- ProposalState
- _run_job
- iOS (цепочка, `Features/Chat/`)
- FeatureGalleryUITests
- WeatherUnavailable
- isolated
- chat_env
- fixtures
- handle

## God Nodes (most connected - your core abstractions)
1. `fetch_one()` - 266 edges
2. `fetch_all()` - 186 edges
3. `execute()` - 125 edges
4. `conn()` - 123 edges
5. `sign_in()` - 114 edges
6. `AppError` - 109 edges
7. `get_settings()` - 100 edges
8. `Step` - 77 edges
9. `FakeRouter` - 71 edges
10. `TripMapModel` - 65 edges

## Surprising Connections (you probably didn't know these)
- `Замечания` --references--> `PlaceActionsUITests`  [INFERRED]
  docs/reviews/Ш-32b.md → ios/JolUITests/PlaceActionsUITests.swift
- `Секреты` --references--> `SecretsError`  [INFERRED]
  docs/deploy.md → server/app/auth/keys.py
- `Не проверено` --references--> `S3Storage`  [INFERRED]
  docs/reviews/Ш-51.md → server/app/providers/storage/s3.py
- `Проверки` --references--> `TripMapUITests`  [INFERRED]
  docs/reviews/Ш-37-ios.md → ios/JolUITests/TripMapUITests.swift
- `Что сделано` --references--> `LocationProviding`  [INFERRED]
  docs/reviews/Ш-47-ios.md → ios/Jol/Features/Directions/LocationProvider.swift

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Общие макросы форм админки** — server_app_admin_templates__macros_field, server_app_admin_templates__macros_select, server_app_admin_templates__macros_checkbox, server_app_admin_templates__macros_csrf_field [EXTRACTED 1.00]
- **Working defaults for open SSOT questions** — jol_ssot_open_questions, tech_plan_open_defaults, docs_adr_0003_open_defaults_table, docs_handoff_owner_needs, tech_plan_open_marker [EXTRACTED 1.00]
- **Account deletion flow across data stores** — docs_reviews_ш_44_server_account_deletion, docs_reviews_ш_46_bonus_ledger, docs_reviews_ш_50_server_anonymize, docs_reviews_ш_50_server_analytics_events [INFERRED 0.75]
- **Методы входа и выдача сессии** — docs_reviews_ш_25_otp_api, docs_reviews_ш_26_apple_identity_verify, docs_reviews_ш_27_sms_e164, docs_reviews_ш_24_session_tokens [INFERRED 0.75]
- **Конвейер маршрутов: API, тарифы, пиковые часы, маршрутизатор** — docs_reviews_ш_22_directions_api, docs_reviews_ш_22_transport_tariffs, docs_reviews_ш_22_peak_multiplier, docs_reviews_ш_20_routing_provider [INFERRED 0.75]
- **Стек LLM-чата** — docs_reviews_ш_29_llm_provider_contract, docs_reviews_ш_29_resilient_llm, docs_reviews_ш_29_fake_llm, docs_reviews_ш_30_tool_loop_engine, docs_reviews_ш_31_trip_brief_tools [INFERRED 0.75]
- **Стек карты: стиль, iOS MapView, слой мест** — docs_reviews_ш_11_12_style_generator, docs_reviews_ш_13_ios_map_view, docs_reviews_ш_18_map_places_layer [INFERRED 0.75]
- **Надёжность воркера: аренда, внешние вызовы, обработчик** — docs_reviews_ш_01_03_06_worker_lease, docs_reviews_ш_01_03_06_external_tx, docs_reviews_ш_01_03_06_job_worker [INFERRED 0.75]
- **Budget and lodging pipeline** — jol_ssot_budget_lodging_rule, tech_plan_planner, tech_plan_ш_35, docs_adr_0003_budget_two_variants, docs_adr_0002_planner_vs_llm_principle [INFERRED 0.85]
- **Getting-there route flow** — jol_ssot_getting_there_screen, jol_ssot_transport_modes, tech_plan_ш_22, tech_plan_ш_23, tech_plan_api_draft [INFERRED 0.85]
- **Live weather recheck loop** — docs_reviews_ш_39_forecast_view, docs_reviews_ш_40_live_rules, docs_reviews_ш_40_live_engine, docs_reviews_ш_40_proposals_endpoints, docs_reviews_ш_40_push_provider [INFERRED 0.85]
- **Jol icon brand composition** — logo_jol_icon_wordmark, logo_jol_icon_road_bar_motif, logo_jol_icon_color_palette [INFERRED 0.85]
- **Jol Brand Mark Composition** — logo_jol_logo_wordmark, logo_jol_logo_road_bar, logo_jol_logo_color_palette [INFERRED 0.85]
- **Moderation approval to bonus accrual** — docs_reviews_ш_45_autofilter, docs_reviews_ш_45_moderation_queue, docs_reviews_ш_46_idempotency_key, docs_reviews_ш_46_bonus_formula [INFERRED 0.85]
- **Trip build pipeline: candidates, layout, budget** — docs_reviews_ш_36_build_trip, docs_reviews_ш_33_select_candidates, docs_reviews_ш_34_layout_plan_days, docs_reviews_ш_35_budget_plan_costs [INFERRED 0.85]
- **Trip edit flow (remove, replace, signals, SSE)** — docs_reviews_ш_38_remove_item, docs_reviews_ш_38_replace_item, docs_reviews_ш_38_trip_edit_engine, docs_reviews_ш_38_user_place_signals, docs_reviews_ш_38_trip_updated_event [INFERRED 0.85]

## Communities (274 total, 61 thin omitted)

### Community 0 - "Sendable"
Cohesion: 0.09
Nodes (43): MeInfo, .identity, Warning, CategoryRef, DayHours, Interval, .lines, BudgetBreakdown (+35 more)

### Community 1 - "api (106)"
Cohesion: 0.08
Nodes (77): admin_get(), admin_post(), AdminError, AdminLoginRequired, analytics_page(), _bonus_page(), bonuses_form(), bonuses_save() (+69 more)

### Community 2 - "conftest.py"
Cohesion: 0.15
Nodes (9): client(), committed_auth_db_url(), env(), recreate_database(), scratch_db_url(), test_db_url(), test_concurrent_identity_creation_and_refresh(), login() (+1 more)

### Community 3 - "htmx-1.9.12.min (105)"
Cohesion: 0.08
Nodes (104): A(), ae(), ar(), at(), B(), be(), br(), bt() (+96 more)

### Community 4 - "TripMapModel (104)"
Cohesion: 0.05
Nodes (22): TripMapLine, TripMapModel, .day, .days, PendingRemoval, Phase, failed, idle (+14 more)

### Community 5 - "CodingKey"
Cohesion: 0.03
Nodes (75): CodingKeys, refreshToken, CodingKeys, displayName, email, id, phone, CodingKeys (+67 more)

### Community 6 - "execute"
Cohesion: 0.06
Nodes (40): delete_account(), _remove_submissions(), logout(), refresh(), RefreshRequest, _digest(), issue(), _latest() (+32 more)

### Community 7 - "DirectionOption"
Cohesion: 0.03
Nodes (60): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-49 (iOS) — кнопка и запрос бронирования, Что сделано, Endpoint, Method (+52 more)

### Community 8 - "budget (78)"
Cohesion: 0.09
Nodes (30): _cheaper_replacement(), cheaper_variant(), choose_lodging(), Costs, drop_variant(), _in_pool_order(), layout_centre(), leg_cost() (+22 more)

### Community 9 - "routing/service.py"
Cohesion: 0.07
Nodes (27): DirectionsLegs, directions(), calculate_cost(), load_tariffs(), recommend(), _recommendation_rank(), Tariff, AlmatyPoint (+19 more)

### Community 10 - "ChatModelTests"
Cohesion: 0.08
Nodes (9): ChatStub, Answer, TripStub, .isOver, .total, ChatModelTests, Script, StatusBox (+1 more)

### Community 11 - "test_account_deletion.py"
Cohesion: 0.04
Nodes (34): AppleKeyCache, AppleSignIn, challenge(), Challenge, _exchange_code(), fetch_keys(), AppleGrantError, AppleGrants (+26 more)

### Community 12 - "db.py"
Cohesion: 0.05
Nodes (19): ChatLimiters, client_ip(), make_limiters(), error_response(), install_error_handlers(), _app_error(), _http_error(), _unhandled() (+11 more)

### Community 13 - "build (68)"
Cohesion: 0.07
Nodes (26): build_trip(), _model_budget(), _model_events(), _breakdown(), budget_json(), BuiltPlan, _lodging_json(), must_have_unmet_json() (+18 more)

### Community 14 - "test_weather.py"
Cohesion: 0.12
Nodes (19): city_forecast(), cache_key(), body_for(), Clock, FakeOpenMeteo, make(), test_a_failure_without_any_cache_raises_and_stores_nothing(), test_a_second_call_and_a_nearby_point_are_served_from_the_cache() (+11 more)

### Community 15 - "config.py"
Cohesion: 0.06
Nodes (24): Settings, capture_exception(), init_error_reporting(), _release(), make_storage(), media_url(), ObjectTooLarge, PresignedPut (+16 more)

### Community 16 - "APIClientTests (64)"
Cohesion: 0.11
Nodes (3): APIClientTests, ClearedFlag, .value

### Community 17 - "layout (61)"
Cohesion: 0.08
Nodes (34): _assign_activities(), assign(), best_day(), item_for(), _assign_meals(), _at(), _centroid(), _Ctx (+26 more)

### Community 18 - "edit (61)"
Cohesion: 0.09
Nodes (36): _option(), leg_tools(), KeptStop, RetimedDay, place_from_row(), _apply_retime(), budget_summary(), _candidates() (+28 more)

### Community 19 - "test_live_plan (59)"
Cohesion: 0.16
Nodes (41): d(), set_clock(), configure(), FakeRouter, TransactionalDatabase, test_build_plan_reads_the_profile(), test_directions_place_and_tariff_version_in_postgis(), test_directions_variant_fields_and_one_recommended() (+33 more)

### Community 20 - "service (59)"
Cohesion: 0.05
Nodes (56): add_route_place(), check_event_refs(), clean_text(), format_hours_day(), like_pattern(), list_places(), move_route_item(), _norm() (+48 more)

### Community 21 - "api (59)"
Cohesion: 0.08
Nodes (29): bearer_token(), delete_me(), me(), current_user(), create_booking(), get_booking(), list_bookings(), DeviceIn (+21 more)

### Community 22 - "test_trip_edits.py"
Cohesion: 0.11
Nodes (44): all_items(), assert_day_is_consistent(), built(), check_totals(), day_of(), pick(), plan(), post() (+36 more)

### Community 23 - "PlaceActionsUITests"
Cohesion: 0.17
Nodes (7): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке, Что сделано, PlaceActionsUITests

### Community 24 - "test_submissions (55)"
Cohesion: 0.13
Nodes (45): test_approve_and_reject_flow(), test_approving_menu_and_price_applies_them_to_the_place(), test_deleted_admin_keeps_the_decision(), test_duplicate_photo_by_hash(), test_duplicate_review_text(), test_menu_and_transit_text_are_filtered_too(), test_moderation_requires_admin_and_csrf(), test_moderator_rejected_photo_cannot_come_back() (+37 more)

### Community 25 - "FavoritesModel (54)"
Cohesion: 0.10
Nodes (12): FavoritesList, FavoritesModel, ListState, failed, idle, loaded, loading, Problem (+4 more)

### Community 26 - "BookingSheet"
Cohesion: 0.15
Nodes (4): BookingSheet, .calendar, .model, .bookButton

### Community 27 - "ProfileScreen (52)"
Cohesion: 0.05
Nodes (33): PlaceholderScreen, .body, ChatScreen, .body, View, PlacesScreen, .body, LanguagePicker (+25 more)

### Community 28 - "deps (52)"
Cohesion: 0.08
Nodes (11): Решения владельца, install_id(), make_llm(), run_turn(), TurnRecord, ChatTurn, guest_chat(), frames() (+3 more)

### Community 29 - "import_places (51)"
Cohesion: 0.11
Nodes (18): build_record(), clean(), extract(), load(), main(), build_record(), collect(), database_url() (+10 more)

### Community 30 - "Identifiable"
Cohesion: 0.07
Nodes (39): CuratedRouteDetail, .stops, CuratedRoutesList, CuratedRouteStop, CodingKeys, ord, .id, CuratedRouteSummary (+31 more)

### Community 31 - "test_chat (51)"
Cohesion: 0.13
Nodes (41): save_note(), parse_sse(), day(), new_chat(), open_stream(), say(), signing_secret(), StallingLLM (+33 more)

### Community 32 - "APIError"
Cohesion: 0.09
Nodes (14): APIError, invalidBaseURL, invalidResponse, .isUnauthorized, network, rateLimited, server, .serverMessage (+6 more)

### Community 33 - "BookingModels (50)"
Cohesion: 0.06
Nodes (33): Booking, CodingKeys, endsAt, id, kind, note, partySize, place (+25 more)

### Community 34 - "PlacesModel (50)"
Cohesion: 0.05
Nodes (21): MapScreen, .body, .tripOpen, PlacesModel, DetailState, failed, idle, loaded (+13 more)

### Community 35 - "Ш-32 (47)"
Cohesion: 0.06
Nodes (45): ChatGraphView (one-branch thesis graph), ChatPanel (collapsible chat), ChatService (iOS SSE chat client), MapCoordinator+Chat (live map pins), POST /v1/chats/{id}/messages (SSE), TripDaysSheet (route by days sheet), interests.py keyword table (RU+EN), _resolve_must_have (mandatory wishes) (+37 more)

### Community 36 - "DirectionsTests (47)"
Cohesion: 0.10
Nodes (9): .line, from, GeoPoint, .coordinate, .isInServiceArea, Counter, DirectionsTests, FakeLocator (+1 more)

### Community 37 - "test_directions (47)"
Cohesion: 0.09
Nodes (17): decode_polyline6(), TransitOption, _alt(), directions_api(), StubDatabase, test_directions_contract_and_almaty_tariff_date(), test_directions_empty_vs_unavailable(), test_directions_motor_range_for_local_departure() (+9 more)

### Community 38 - "CrowdModel (45)"
Cohesion: 0.07
Nodes (17): CrowdModel, Action, checkIn, report, .isWorking, Outcome, alreadyRecorded, failed (+9 more)

### Community 39 - "Ш-31 (45)"
Cohesion: 0.05
Nodes (30): osm_addresses (таблица), GET /v1/geocode/reverse, Схема аккаунтов (users, auth_identities, sessions, otp_codes), Обнаружение повторного использования refresh-токена, Ротация refresh-токена, Access JWT 15 минут и refresh-токен 60 дней, POST /v1/auth/otp/request и /v1/auth/otp/verify, EmailProvider и SmtpEmailProvider (+22 more)

### Community 40 - "Ш-44-server (45)"
Cohesion: 0.06
Nodes (38): Review Ш-44 server: content submissions, LocalStorage (dev only), retention.cleanup worker task, S3Storage with SigV4 presigned PUT, StorageProvider interface, Submissions API (five types), Review Ш-45: autofilter and moderation, Autofilter rules (rejected_auto) (+30 more)

### Community 41 - "test_admin (45)"
Cohesion: 0.12
Nodes (37): place_form_values(), get_place(), fetch_one(), add_category(), add_place(), csrf_of(), logged_in(), login() (+29 more)

### Community 42 - "test_planner_layout (45)"
Cohesion: 0.12
Nodes (33): pick_default(), RouterMatrix, _at(), check_invariants(), dates(), fingerprint(), legs_provider(), mk() (+25 more)

### Community 43 - "DirectionsModel (43)"
Cohesion: 0.07
Nodes (22): DirectionsModel, Failure, generic, network, outsideArea, serviceUnavailable, Fallback, chosen (+14 more)

### Community 44 - "store (43)"
Cohesion: 0.10
Nodes (28): Сервер (порядок заполнения, восстановление), _chat_json(), create_chat(), get_chat(), list_chats(), _own_chat(), send_message(), frames() (+20 more)

### Community 45 - "SignInModel (42)"
Cohesion: 0.06
Nodes (25): CodeStep, .body, DestinationStep, .body, ProblemText, .body, .rateLimitedText, SignInEntryView (+17 more)

### Community 46 - "JolFont"
Cohesion: 0.09
Nodes (21): Проверки, Ревью координатора (2026-11-21), Ревью Ш-32a — граф-кольцо в чате, Решения и ограничения, Что сделано, .body, .body, ChatTranscriptView (+13 more)

### Community 47 - "test_places_api (42)"
Cohesion: 0.06
Nodes (49): _covers(), group_hours(), is_open_now(), parse_bbox(), mk(), put(), test_cap_applies_to_new_places_only(), test_favorites_are_per_user_and_hidden_places_are_not_listed() (+41 more)

### Community 48 - "test_popular_import (41)"
Cohesion: 0.12
Nodes (20): _bool(), CsvError, import_csv(), _int(), link_manual_to_osm(), _opt(), parse_rows(), _csv() (+12 more)

### Community 49 - "PlaceCardTabs (40)"
Cohesion: 0.09
Nodes (10): PlaceGallery, .body, PlaceTabContent, .body, .overview, .photos, .reviews, PlaceFormatting (+2 more)

### Community 50 - "SignInTests (40)"
Cohesion: 0.13
Nodes (4): ContactValidator, apiError(), SignInTests, Fixture

### Community 51 - "test_routing (40)"
Cohesion: 0.14
Nodes (19): make_router(), load(), _router(), run(), test_client_error_mapping(), test_client_matrix_pairwise_fallback_marks_unreachable(), test_client_retries_connect_errors_only(), flaky() (+11 more)

### Community 52 - "test_osm_import (39)"
Cohesion: 0.09
Nodes (25): _parse_days(), _parse_intervals(), parse_opening_hours(), _to_time(), category_for_food(), category_slug(), classify(), _clean() (+17 more)

### Community 53 - "CrowdBlock"
Cohesion: 0.12
Nodes (17): CrowdBlock, CodingKeys, now, samples, today, updatedAt, CrowdHour, CrowdLevel (+9 more)

### Community 54 - "base (39)"
Cohesion: 0.11
Nodes (14): push(), push_send(), ApnsProvider, _reason(), LogPushProvider, PushError, PushMessage, PushOutcome (+6 more)

### Community 55 - "test_analytics.py"
Cohesion: 0.12
Nodes (33): period(), add_item(), checkin(), ev(), fixtures(), hdr(), make_trip(), make_user() (+25 more)

### Community 56 - "LocationProvider (38)"
Cohesion: 0.07
Nodes (8): .stubLocation, CoreLocationProvider, LocationProviding, LocationResult, denied, located, unavailable, TestLocator

### Community 57 - "edit_tools (38)"
Cohesion: 0.10
Nodes (24): _add_graph_node(), _build_trip(), _search_events(), _search_places(), handle_tool(), _after_edit(), _chat_trip(), get_trip_plan() (+16 more)

### Community 58 - "ChatState (37)"
Cohesion: 0.11
Nodes (10): messages, ChatMessage, Role, assistant, user, ChatState, .isConverged, .isEmpty (+2 more)

### Community 59 - "memory/jobs.py"
Cohesion: 0.11
Nodes (16): chat_data_block(), configure(), memory_note(), memory_scan(), _provider(), clean_note(), LLMProvider, get_llm_provider() (+8 more)

### Community 60 - "SessionStore (36)"
Cohesion: 0.08
Nodes (13): APIClient, RefreshBody, Refresher, EphemeralTokenStore, TokenStore, SessionStore, .query, SessionTokens (+5 more)

### Community 61 - "analytics/service.py"
Cohesion: 0.10
Nodes (15): AnalyticsLimiters, _bearer(), _install_id(), make_limiters(), post_events(), clean_props(), ClientEvent, EventBatch (+7 more)

### Community 62 - "adapters (36)"
Cohesion: 0.08
Nodes (17): Availability, BookingLimits, BookingRequest, get_adapter(), limits_of(), PartnerAdapter, PartnerResult, StubAdapter (+9 more)

### Community 63 - "store (36)"
Cohesion: 0.11
Nodes (19): optional_weather(), router(), weather(), _days_ahead(), mountain_notify(), _user_locale(), weather_recheck(), create() (+11 more)

### Community 64 - "test_llm.py"
Cohesion: 0.09
Nodes (39): _trim_history(), collect(), Completion, Done, ErrorEvent, LLMError, LLMNotConfigured, LLMTimeout (+31 more)

### Community 65 - ".nodeCenter"
Cohesion: 0.14
Nodes (5): CoreGraphics, ChainGeometry, Connector, .height, ChainGeometryTests

### Community 66 - "docker-compose (35)"
Cohesion: 0.06
Nodes (34): build_admins, build_elevation, build_tar, build_time_zones, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, serve_tiles (+26 more)

### Community 67 - "test_osm_pipeline (34)"
Cohesion: 0.10
Nodes (22): merge_place(), test_osm_merge_keeps_event_and_removes_promotion_at_public_place(), keys(), q(), sconn(), test_collect_drops_outer_way_and_duplicate_node(), test_load_into_db_and_idempotent(), test_merge_moves_analytics_events_to_the_survivor() (+14 more)

### Community 68 - "test_transit_import (34)"
Cohesion: 0.16
Nodes (12): by_rel(), network(), rows(), sconn(), test_empty_extract_does_not_wipe_network(), test_metro_directions_share_stations(), test_migration_constraints(), test_short_relation_skipped() (+4 more)

### Community 69 - "test_chat_guest (34)"
Cohesion: 0.20
Nodes (24): FakeToolCall, Step, post(), test_bad_tool_arguments_come_back_as_a_tool_error(), test_failure_after_text_keeps_the_text_and_sends_no_done(), test_guest_chat_writes_nothing_to_the_database(), snapshot(), test_history_at_the_limits_is_accepted() (+16 more)

### Community 70 - "EventsModel"
Cohesion: 0.06
Nodes (18): Не сделано / ограничения, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-48 (iOS) — мероприятия на карте, Что сделано, JolFont, AdBadge (+10 more)

### Community 71 - "typing"
Cohesion: 0.05
Nodes (15): EventList, EventVenue, event_json(), _iso(), load_events(), window_end(), accept(), decline() (+7 more)

### Community 72 - "ProfileModel (33)"
Cohesion: 0.08
Nodes (13): AccountGate, AuthState, action, ProfileMenuContent, .body, .dangerSection, .deleteFailed, .body (+5 more)

### Community 73 - "enqueue"
Cohesion: 0.13
Nodes (16): enqueue(), process_batch(), register(), one(), test_a_db_handler_loses_its_writes_when_the_lease_was_taken_over(), handle(), test_a_job_that_kills_its_worker_ends_dead_instead_of_looping(), test_an_external_handler_failure_is_retried_with_its_payload() (+8 more)

### Community 74 - "UITestSupport"
Cohesion: 0.09
Nodes (10): FixtureURLProtocol, StubLocationProvider, UITestSupport, .directionsJSON, .eventsItemsJSON, .favoritesJSON, .isStubbed, .placesJSON (+2 more)

### Community 75 - "DirectionsFormatting (32)"
Cohesion: 0.10
Nodes (7): DirectionsFormatting, TripLegSheet, .body, .choices, .current, .header, .language

### Community 76 - "PlaceCardView"
Cohesion: 0.14
Nodes (10): PlaceCardView, .detail, .failedRow, .tabBar, PlaceTab, .id, overview, photos (+2 more)

### Community 77 - "ChatModel"
Cohesion: 0.11
Nodes (4): ChatModel, .isGuestTranscript, .isStreaming, Loaded

### Community 78 - "open_meteo.py"
Cohesion: 0.13
Nodes (10): DayWeather, HourWeather, _hour(), _hour_json(), OpenMeteoProvider, parse_response(), test_a_rainy_forecast_moves_the_planner_not_the_unknown_one(), test_parse_rejects_a_broken_answer() (+2 more)

### Community 79 - "test_planner_scoring (32)"
Cohesion: 0.19
Nodes (16): no_event_bonus(), UnknownCrowd, make_place(), scored(), test_an_interest_match_beats_a_little_popularity(), test_crowd_penalty_scales_with_intolerance(), test_default_hooks_mean_no_data(), test_event_bonus_counts_double_when_asked() (+8 more)

### Community 80 - "transit (32)"
Cohesion: 0.07
Nodes (17): NoRoute, RoutingError, RoutingProvider, _candidates(), find_transit_options(), get_network(), _in_service(), _line_key() (+9 more)

### Community 81 - "_macros (30)"
Cohesion: 0.10
Nodes (5): checkbox macro, csrf_field macro, field macro, select macro, textarea macro

### Community 82 - "test_transit_search (29)"
Cohesion: 0.15
Nodes (20): hop_speed_boost(), build(), _load(), _load_dev_network(), run(), search(), stop_row(), test_best_of_each_mode_is_kept() (+12 more)

### Community 83 - "auth"
Cohesion: 0.19
Nodes (15): apple_login(), auth(), count(), FakeGrants, otp_sign_in(), test_apple_delete_enqueues_revoke_and_allows_reregistration(), test_apple_without_stored_token_deletes_and_logs_gap(), test_code_exchange_problems_never_block_sign_in() (+7 more)

### Community 84 - "valhalla (29)"
Cohesion: 0.13
Nodes (17): check_mode(), Maneuver, MatrixResult, RoutingUnavailable, _costing_body(), _loc(), parse_matrix(), parse_route() (+9 more)

### Community 86 - "EventModels (28)"
Cohesion: 0.08
Nodes (19): EventItem, CodingKeys, adLabel, category, description, endsAt, id, isAd (+11 more)

### Community 87 - "brief (28)"
Cohesion: 0.08
Nodes (23): CreateChat, _finish(), lease_sec(), _save_detached(), SendMessage, _update_trip_brief(), apply_update(), brief_data_block() (+15 more)

### Community 88 - "email.py"
Cohesion: 0.06
Nodes (22): DevEmailProvider, EmailProvider, EmailSettings, get_email_provider(), normalize_email(), SmtpEmailProvider, _client_ip(), OtpRequest (+14 more)

### Community 89 - "ServerMeta"
Cohesion: 0.20
Nodes (9): ServerMeta, CodingKeys, minIOSVersion, version, State, failed, idle, loaded (+1 more)

### Community 90 - "ci (27)"
Cohesion: 0.07
Nodes (26): DATABASE_URL, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, TEST_DATABASE_URL, jobs, server, name (+18 more)

### Community 91 - "PlacesTests (27)"
Cohesion: 0.19
Nodes (4): Counter, json(), page(), PlacesTests

### Community 92 - "read (27)"
Cohesion: 0.13
Nodes (19): budget_json(), chosen_option(), days_json(), item_json(), leg_json(), leg_late_by_s(), local(), lodging_option_json() (+11 more)

### Community 93 - "test_planner_candidates (26)"
Cohesion: 0.23
Nodes (15): select_candidates(), test_planner_uses_the_profile_for_quiet_travellers(), test_favorite_place_and_category_get_a_small_bonus(), brief(), fixture_places(), names(), test_crowd_source_is_used_for_quiet_travellers(), test_event_bonus_hook_is_applied() (+7 more)

### Community 94 - "AppConfig (26)"
Cohesion: 0.17
Nodes (5): AppConfig, .apiBaseURL, .appleSignInEnabled, .isSimulator, APIBaseURLTests

### Community 96 - "Foundation"
Cohesion: 0.08
Nodes (10): CoreLocation, Foundation, L10n, Polyline, AlmatyCamera, Navigator, .body, MapLibre (+2 more)

### Community 97 - "test_memory.py"
Cohesion: 0.10
Nodes (42): call(), add_event(), test_admin_event_shown_on_localized_map_and_venue_card(), test_guest_can_search_evening_events_without_a_trip(), test_map_rejects_invalid_windows_and_boxes(), test_map_window_overlap_coordinates_and_hidden_places(), test_planner_and_chat_offer_an_attendable_event_with_its_ad_label(), test_public_places_are_ad_free_in_admin_database_and_map() (+34 more)

### Community 98 - "schemas (24)"
Cohesion: 0.15
Nodes (20): EventItem, CategoriesList, Category, CategoryRef, CrowdHour, CrowdLevel, CrowdProfile, CuratedRouteDetail (+12 more)

### Community 99 - "AppError"
Cohesion: 0.06
Nodes (29): RefreshReuse, AppError, StorageProvider, create_submission(), create_upload(), get_storage(), my_bonuses(), my_submissions() (+21 more)

### Community 100 - "AppContainer"
Cohesion: 0.09
Nodes (20): Итог прогона (Ш-37, Ш-47, Ш-48, Ш-49), Не сделано / ограничения, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-37 (iOS) — полная карта маршрута (веха M3), Что сделано, AppContainer (+12 more)

### Community 102 - "messages (21)"
Cohesion: 0.13
Nodes (9): _stats(), day_text(), _hour(), mountain_texts(), proposal_texts(), Problem, stop_problem(), visit_hours() (+1 more)

### Community 103 - "scoring (21)"
Cohesion: 0.26
Nodes (8): _clip01(), interest_match(), intolerance(), pick_pool(), rank(), Score, score_place(), Scored

### Community 104 - "AppLanguage (20)"
Cohesion: 0.14
Nodes (11): AppLanguage, english, .id, .nativeName, russian, system, LanguageSettings, .code (+3 more)

### Community 105 - "SSEParserTests (20)"
Cohesion: 0.16
Nodes (3): SSEEvent, SSEParser, SSEParserTests

### Community 106 - "PlaceModels (20)"
Cohesion: 0.10
Nodes (20): CodingKeys, address, booking, category, crowd, description, events, hours (+12 more)

### Community 107 - "service (20)"
Cohesion: 0.18
Nodes (7): aggregate(), card_block(), _distance(), label(), place_block(), ProfileCrowd, record()

### Community 108 - "test_clientip.py"
Cohesion: 0.09
Nodes (25): Замечания и компромиссы, Не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-51 — продакшен-инфраструктура (кодовая часть), Что сделано, client_ip(), _parse() (+17 more)

### Community 109 - "CLAUDE (19)"
Cohesion: 0.13
Nodes (11): .claude/CLAUDE.md graphify trigger document, graphify skill triggered by /graphify, Root CLAUDE.md project instructions, ADR numbering and supersession rules, ADR index and rules document, ADR status values (предложено, принято, отклонено, заменено), Decision log (SSOT §17), JOL_SSOT product single source of truth (+3 more)

### Community 110 - "ChatService"
Cohesion: 0.14
Nodes (8): Load, failed, idle, loaded, loading, ChatService, GuestBody, GuestMessage

### Community 111 - "JOL_SSOT (19)"
Cohesion: 0.15
Nodes (17): Weather day-suffers thresholds and planning rules, Prioritized next steps list, Place crowd level data source (open), Favorites feature, Getting-there screen with mode carousel, Profile menu and swipe sidebar navigation, Whole-trip route building by day, Transport options between points (walk, scooter, bus, metro, taxi, car) (+9 more)

### Community 112 - "schemas (19)"
Cohesion: 0.15
Nodes (10): _clean(), _line(), MenuItem, MenuPayload, _Payload, PhotoPayload, PricePayload, _required() (+2 more)

### Community 113 - "AuthService"
Cohesion: 0.07
Nodes (20): AuthenticationServices, AppleSignInView, .body, .service, AppleCredential, CodingKeys, authorizationCode, identityToken (+12 more)

### Community 114 - "SwiftUI"
Cohesion: 0.05
Nodes (24): JolApp, .body, RootView, .body, .content, JolRadius, JolSpacing, AccountGateSheet (+16 more)

### Community 115 - "MapCoordinator"
Cohesion: 0.07
Nodes (3): MapCoordinator, Layer, MapView

### Community 116 - "test_apple (17)"
Cohesion: 0.30
Nodes (10): get_nonce(), issue(), private_key(), submit(), test_invalid_signature_does_not_consume_challenge(), test_outage_is_rate_limited(), test_rejects_expired_nonce_and_wrong_algorithm_before_fetch(), test_rejects_invalid_claims() (+2 more)

### Community 117 - "TECH_PLAN (17)"
Cohesion: 0.13
Nodes (13): ADR 0003 default values for open SSOT questions, Default behavior table for SSOT §16 questions, Refresh token reuse grace window of 10 seconds, Deferred review items to fix before production or TestFlight, Bookings and orders via partner APIs, Two-stage monetization plan (growth then partnership), Open questions register (SSOT §16), Promoted events shown during trip dates (+5 more)

### Community 118 - "PlaceCategoryStyle (17)"
Cohesion: 0.15
Nodes (6): JolColor, UIColor, .content, PlaceCategoryStyle, .allImages, .color

### Community 119 - "test_planner_budget.py"
Cohesion: 0.20
Nodes (18): Case, over_budget_case(), plan_for(), priced(), stops(), test_cheaper_variant_replaces_meals_too(), test_cheaper_variant_swaps_for_cheaper_places_and_cheapest_lodging(), test_drop_variant_removes_the_least_valuable_costly_optionals_only() (+10 more)

### Community 120 - "XCTestCase"
Cohesion: 0.09
Nodes (5): AppConfigTests, SessionStoreTests, AppleSignInUITests, MapLaunchUITests, XCTest

### Community 121 - "candidates.py"
Cohesion: 0.11
Nodes (9): like_pattern(), _area(), Candidate, MustHave, _resolve_must_have(), Selection, trip_days(), CrowdSource (+1 more)

### Community 122 - "test_airport (17)"
Cohesion: 0.21
Nodes (11): airport_routes(), build_network(), bus(), ride_from_terminal(), test_airport_real_pbf(), test_airport_real_valhalla(), test_import_sends_stable_manual_stop_ids(), test_manual_stop_rows_survive_reimport() (+3 more)

### Community 123 - "geometry (16)"
Cohesion: 0.20
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 124 - "import_transit.py"
Cohesion: 0.11
Nodes (16): apply_manual_stops(), build_network(), extract(), haversine_m(), load_seed(), main(), norm_name(), parse_interval() (+8 more)

### Community 125 - "HANDOFF (16)"
Cohesion: 0.14
Nodes (14): OTP invalid versus expired error distinction, HANDOFF session handoff note (2026-11-21), Local dev environment on owner's Mac (Docker, PostGIS port 5433, Xcode), Items needed from the project owner, AppContainer dependency injection container, JOL_APPLE_SIGN_IN_ENABLED build switch, iOS app README (layout, build, config), UI-test stub launch switches (DEBUG) (+6 more)

### Community 126 - "DirectionsModels (16)"
Cohesion: 0.12
Nodes (16): CodingKeys, approximate, arriveAt, congestion, costKztMax, costKztMin, distanceM, durationS (+8 more)

### Community 128 - "test_bookings (16)"
Cohesion: 0.17
Nodes (14): booking_settings(), link_partner(), place(), test_book_from_card_and_read_confirmation(), test_event_ticket_requires_a_current_event_at_the_partner_place(), test_limits_below_the_minimum_and_localized_messages(), test_only_connected_partners_offer_bookings(), test_pagination_at_equal_timestamps() (+6 more)

### Community 129 - "Ш-20 (15)"
Cohesion: 0.19
Nodes (10): Ревью Ш-20 (движок маршрутизации Valhalla), RoutingProvider, ValhallaRouter, FakeRouter, Valhalla routing engine (docker, valhalla-scripted), Цель make osm-pbf и общий кэш OSM, Ревью Ш-21 (общественный транспорт), Импорт транспорта (120 маршрутов, 956 остановок), Поиск транспорта до 1 пересадки (transit.py), POST /v1/directions (+2 more)

### Community 130 - "test_ratelimit.py"
Cohesion: 0.18
Nodes (19): acquire(), acquire_own(), cleanup_expired(), key_hash(), RateRule, test_a_committed_count_survives_a_failing_request(), test_a_refused_request_counts_nothing_anywhere(), test_cleanup_removes_only_expired_rows() (+11 more)

### Community 131 - "dedupe (14)"
Cohesion: 0.21
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 132 - "JOL_SSOT (14)"
Cohesion: 0.19
Nodes (10): ADR 0002 planner vs LLM record, Budget overrun offers two variants for user choice (SSOT §16.3), Maximum trip length 60 days assumption, Dynamic one-branch thesis graph in chat, Collapsing AI chat home screen over map, Trip input parameters collected in chat, Data model draft (tables), LLMProvider interface (fake provider in dev) (+2 more)

### Community 133 - "bonus_policy.py"
Cohesion: 0.12
Nodes (13): Breakdown, compute(), Param, resolve(), validate(), accrue(), load_coefficients(), test_formula_age_and_frequency() (+5 more)

### Community 134 - ".swiftlint (14)"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 135 - "psycopg"
Cohesion: 0.20
Nodes (10): apply_migrations(), checksum_of(), discover(), main(), MigrationError, counts(), main(), test_applies_on_empty_db_and_rerun_is_noop() (+2 more)

### Community 136 - "live/engine.py"
Cohesion: 0.19
Nodes (12): _count(), _count_plan(), _count_rows(), find_proposal(), problem_of(), _minutes(), outdoor(), _problem() (+4 more)

### Community 137 - "StubURLProtocol"
Cohesion: 0.11
Nodes (4): StubURLProtocol, .requests, TripMapTests, Jol

### Community 138 - "GeoBounds"
Cohesion: 0.16
Nodes (5): EventsService, GeoBounds, .height, .queryValue, .width

### Community 139 - "fetch_all"
Cohesion: 0.20
Nodes (15): fetch_all(), order(), pending_ids(), a_user(), add_report(), body(), fill_profile(), test_account_deletion_removes_own_reports_and_checkins() (+7 more)

### Community 140 - "load_prompt"
Cohesion: 0.17
Nodes (9): load_prompt(), Prompt, versions(), test_every_prompt_exists_in_both_languages(), test_guest_prompt_exposes_place_and_event_search(), test_render_fills_today(), test_trip_brief_asks_dates_then_budget_then_lodging(), test_unknown_locale_falls_back_to_english_and_unknown_prompt_fails() (+1 more)

### Community 141 - "README (13)"
Cohesion: 0.27
Nodes (12): JOL_MAP_STYLE_URL map style configuration, Bundled placeholder style (MapLibre demo tiles, temporary), Map demo HTML page, load(theme, lang) style loader function, Theme and label-language selectors, almaty.pmtiles vector tile archive, build_tiles.sh Planetiler tile build, maps README (tiles, demo, hosting, styles) (+4 more)

### Community 142 - "get_settings"
Cohesion: 0.07
Nodes (47): decrypt_token(), challenge_key(), _checked(), decrypt(), encrypt(), _explicit(), _fernet_keys(), _generate() (+39 more)

### Community 143 - "Database"
Cohesion: 0.20
Nodes (8): Database, _main(), run_worker(), test_concurrent_email_send_limit_and_consume_once(), test_pending_delivery_does_not_hold_database_transaction(), two_pools(), clean_handlers(), db()

### Community 144 - "ChainNode"
Cohesion: 0.13
Nodes (10): ChainConnector, .animatableData, ChatChainFooter, .body, .openButton, .selectedIndex, ChatGraphView, .body (+2 more)

### Community 145 - "JOL_SSOT (12)"
Cohesion: 0.21
Nodes (11): Temporary bonus formula with demand multipliers, Memory penalty for rejected place categories, Demand coefficient for bonus amount, Downloaded route stored on device, Guest user without account, Memory and personalization for registered users, Registered user, User content submission and bonus system (+3 more)

### Community 146 - "Ш-07-09 (12)"
Cohesion: 0.27
Nodes (8): Импорт OSM по bbox Алматы (pyosmium), Подборка popular_places.csv (102 места), Ревью Ш-07/08/09 (данные мест), Слияние строк мест (data/osm/merge.py), Ревью доработки Ш-08: дедупликация мест OSM, Центроид полигона (data/osm/geometry.py), Импорт мультиполигонов-отношений OSM, Ревью доработки Ш-08: отношения OSM и связь ручных мест

### Community 147 - "TripDayListView"
Cohesion: 0.17
Nodes (4): TripDayListView, .body, TripFormatting, .loadedPanel

### Community 148 - "planner/hours.py"
Cohesion: 0.16
Nodes (5): earliest_start(), load_hours(), _minutes(), visit_minutes(), windows()

### Community 150 - "trip_brief.en.v4 (12)"
Cohesion: 0.23
Nodes (10): Trip brief prompt EN v1, Trip brief prompt EN v2, Trip brief prompt EN v3, Reply after build_trip (budget status rules), Trip brief prompt EN v4, Edit built plan via get/remove/replace tools, Trip brief prompt RU v1, Trip brief prompt RU v2 (+2 more)

### Community 151 - "HaversineMatrix"
Cohesion: 0.18
Nodes (3): HaversineMatrix, _plan_seconds(), PreferredLegs

### Community 152 - "ChatPanel"
Cohesion: 0.14
Nodes (8): BriefFormatting, ChatPanel, .canSend, .header, .inputBar, .isActive, CollapsedChatBar, .bottomBar

### Community 156 - "Ш-11-12 (10)"
Cohesion: 0.27
Nodes (8): Ревью Ш-11/12 (векторные тайлы и стиль карты), Статический сервер тайлов serve.py (Range, CORS), Генератор стилей build_styles.py (jol-light/dark, RU/EN), Сборка тайлов Planetiler (build_tiles.sh, almaty.pmtiles), AppConfig и JOL_MAP_STYLE_URL, MapView (UIViewRepresentable над MLNMapView), Ревью Ш-13 (iOS проект и карта), project.yml (XcodeGen) и Jol.xcodeproj

### Community 157 - "Ш-14 (10)"
Cohesion: 0.27
Nodes (8): APIClient с single-flight refresh, AppContainer (DI через Environment), LanguageSettings и L10n (RU/EN), Ревью Ш-14 (iOS-каркас), SSEClient и SSEParser, ProfileMenuSheet (меню аккаунта), ProfileModel (load, signOut, deleteAccount), Ревью Ш-16 (меню профиля)

### Community 158 - "Kind"
Cohesion: 0.18
Nodes (11): ChainNode, .id, Kind, budget, crowd, dates, interests, lodging (+3 more)

### Community 159 - ".report"
Cohesion: 0.19
Nodes (6): CrowdBody, CodingKeys, lat, level, lon, CrowdService

### Community 160 - "test_trips_followups.py"
Cohesion: 0.11
Nodes (17): RouteResult, encode_polyline6(), haversine_m(), _distinct_routes(), _near(), path_distance_m(), directed(), _resample() (+9 more)

### Community 162 - "serve (9)"
Cohesion: 0.12
Nodes (6): database_url(), main(), H, build(), interp(), name_expr()

### Community 163 - "load_memory"
Cohesion: 0.17
Nodes (11): load_memory(), Memory, penalties_from_signals(), memory_data_block(), museum_count(), new_user(), reject_museums(), test_data_block_is_escaped_capped_and_empty_when_there_is_nothing() (+3 more)

### Community 164 - "project (9)"
Cohesion: 0.22
Nodes (9): ASSETCATALOG_COMPILER_APPICON_NAME, CURRENT_PROJECT_VERSION, GENERATE_INFOPLIST_FILE, INFOPLIST_FILE, MARKETING_VERSION, PRODUCT_BUNDLE_IDENTIFIER, SWIFT_VERSION, TARGETED_DEVICE_FAMILY (+1 more)

### Community 165 - "Ш-18 (8)"
Cohesion: 0.32
Nodes (6): Слой мест jol-pins с кластеризацией MapLibre, PlaceCardSheet (мини и полная карточка), Ревью Ш-18 (места на карте и карточки), CuratedRoutesSheet и RouteBar, Ревью Ш-19 (готовые маршруты, iOS), Линия маршрута прямыми отрезками (jol-route)

### Community 166 - "Ш-23b-server (8)"
Cohesion: 0.25
Nodes (6): Кнопка «В избранное» в листе места, FavoritesModel (избранное, iOS), Список избранного в боковой панели, API избранного /v1/me/favorites, Перенос избранного при слиянии дублей мест, user_favorites (таблица)

### Community 167 - "resolve"
Cohesion: 0.22
Nodes (7): places_per_must_have(), pool_sizes(), PoolSizes, test_must_have_count_grows_with_the_trip(), test_a_longer_trip_or_denser_pace_never_shrinks_the_pool(), test_pool_sizes(), test_resolve_slugs()

### Community 168 - "project (8)"
Cohesion: 0.25
Nodes (8): package, product, dependencies, platform, settings, sources, type, Jol

### Community 169 - "project (8)"
Cohesion: 0.25
Nodes (8): target, dependencies, dependencies, platform, settings, sources, type, JolUITests

### Community 170 - "search_events"
Cohesion: 0.18
Nodes (8): AddGraphNodeArgs, event_for_model(), NoArgs, place_pin(), search_events(), search_places(), SearchEventsArgs, SearchPlacesArgs

### Community 171 - "Failure"
Cohesion: 0.18
Nodes (8): Failure, invalid, network, notSupported, other, rateLimited, signedOut, unavailable

### Community 172 - "TECH_PLAN (7)"
Cohesion: 0.38
Nodes (6): ADR 0001 technology stack record, API draft under /v1 prefix, Target architecture (iOS, FastAPI, worker, Valhalla, PostGIS), Postgres job queue with SKIP LOCKED, SSE chat stream events (text_delta, graph_node, map_places, route_ready), Valhalla routing engine for walk, scooter, car

### Community 173 - "ChatEvent"
Cohesion: 0.04
Nodes (75): ChatBrief, .isEmpty, ChatDetail, CodingKeys, brief, graphNodes, id, title (+67 more)

### Community 174 - "BookingModel"
Cohesion: 0.18
Nodes (4): BookingModel, .booking, .isSending, .form

### Community 175 - "ChatFailure"
Cohesion: 0.17
Nodes (8): ChatFailure, busy, .canRetry, full, network, other, rateLimited, server

### Community 176 - "project (7)"
Cohesion: 0.29
Nodes (6): configFiles, Debug, Release, name, settings, targets

### Community 177 - "jol-logo (7)"
Cohesion: 0.38
Nodes (7): Orange and Black Palette, Jol Logo, Jol Logo, Orange and Black Palette, Road Underline Bar, Road Underline Motif, Jol Wordmark

### Community 178 - "CodingKeys"
Cohesion: 0.15
Nodes (13): CodingKeys, budget, budgetChoice, budgetKzt, days, endDate, events, id (+5 more)

### Community 179 - "Деплой Jol: рабочая инструкция (Ш-51)"
Cohesion: 0.14
Nodes (13): Бэкапы и восстановление, Деплой Jol: рабочая инструкция (Ш-51), Клиентский IP за прокси, Ключи шифрования токенов Apple: ротация и миграция, Миграции, Наблюдаемость, Откат, Первый деплой (+5 more)

### Community 180 - "pg-common.sh"
Cohesion: 0.24
Nodes (10): backup.sh script, db_name_of(), die(), pg_admin(), pg_dump_to(), pg_restore_from(), pg-common.sh script, sha256() (+2 more)

### Community 181 - "Ш-01-03-06 (6)"
Cohesion: 0.40
Nodes (3): Воркер задач app.worker, Раннер миграций (schema_migrations, sha256, advisory lock), Ревью Ш-01/03/04/05/06 (основа и сервер-каркас)

### Community 182 - "Ш-17 (6)"
Cohesion: 0.40
Nodes (5): Схема мест 0002_places.sql, Расчёт is_open_now по времени Алматы, Поиск мест ILIKE и триграммная похожесть, GET /v1/places (bbox, категории, поиск), Ревью Ш-17 (API мест)

### Community 183 - "Ш-15 (6)"
Cohesion: 0.33
Nodes (5): ChatPanel (сворачиваемая карточка), HomeScreen (карта на весь экран, чат поверх), Ревью Ш-15 (главный экран), SidebarPanel и открытие свайпом от края, Переключение тёмного стиля карты по теме

### Community 184 - "CodingKeys"
Cohesion: 0.17
Nodes (12): CodingKeys, endsAt, estCostKzt, id, kind, meal, mustHave, ord (+4 more)

### Community 186 - "project (6)"
Cohesion: 0.33
Nodes (6): targets, build, test, schemes, Jol, targets

### Community 187 - "options"
Cohesion: 0.21
Nodes (12): logging, driver, options, logging, max-file, max-size, logging, x-app (+4 more)

### Community 189 - "Ш-22a (5)"
Cohesion: 0.50
Nodes (3): Отсев альтернатив маршрутов (3%, x1.6), Варианты по группам (group, variant, recommended), Ревью Ш-22a (несколько вариантов на вид транспорта)

### Community 190 - "project (5)"
Cohesion: 0.40
Nodes (5): iOS, options, bundleIdPrefix, deploymentTarget, developmentLanguage

### Community 191 - "project (5)"
Cohesion: 0.40
Nodes (5): platform, settings, sources, type, JolTests

### Community 193 - "Ш-23 (4)"
Cohesion: 0.50
Nodes (3): Карусель способов по кругу, Карточка места (лист «Как добраться»), Декодер polyline6 (Polyline.decode)

### Community 194 - "project (4)"
Cohesion: 0.50
Nodes (4): path, properties, entitlements, com.apple.developer.applesignin

### Community 195 - "project (4)"
Cohesion: 0.50
Nodes (4): exactVersion, url, packages, MapLibre

### Community 196 - "jol-icon-1024 (4)"
Cohesion: 0.67
Nodes (4): Jol App Icon (1024px), Jol Wordmark, Orange Brand Color, Underline Bar Motif

### Community 197 - "jol-icon (4)"
Cohesion: 0.67
Nodes (4): Jol App Icon, Orange and Black Palette, Road Underline Bar Motif, Jol Wordmark (J-o-l)

### Community 198 - "environment"
Cohesion: 0.17
Nodes (12): build_admins, build_elevation, build_tar, build_time_zones, serve_tiles, server_threads, use_default_speeds_config, valhalla (+4 more)

### Community 199 - "Ш-23 (3)"
Cohesion: 0.67
Nodes (3): DirectionsModel, Тесты DirectionsTests и DirectionsUITests, POST /v1/directions (контракт клиента)

### Community 200 - "icon-1024 (3)"
Cohesion: 0.67
Nodes (3): Jol app icon (1024px), Brand orange background, Jol wordmark

### Community 201 - "CodingKeys"
Cohesion: 0.20
Nodes (10): CodingKeys, feasible, lodgingChanged, removed, removedCount, savesKzt, shortfallKzt, swaps (+2 more)

### Community 202 - "README (3)"
Cohesion: 0.67
Nodes (3): Jol tourist trip-planning app (Almaty, iOS first), Repository README (placeholder), README title placeholder Jolm (spelling differs from Jol)

### Community 213 - "CodingKeys"
Cohesion: 0.20
Nodes (10): CodingKeys, chosenModeRaw, costKzt, departAt, estimated, fromItemID, id, options (+2 more)

### Community 216 - "analytics/events.py"
Cohesion: 0.43
Nodes (4): _flag(), _one_of(), _short_str(), _small_int()

### Community 217 - "deploy.sh"
Cohesion: 0.44
Nodes (7): compose(), die(), need_env(), previous_tag(), record_tag(), deploy.sh script, wait_ready()

### Community 218 - "postgres"
Cohesion: 0.22
Nodes (9): POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, environment, image, platform, restart, volumes (+1 more)

### Community 220 - "postgres"
Cohesion: 0.29
Nodes (8): depends_on, migrate, postgres, condition, depends_on, condition, depends_on, depends_on

### Community 221 - "metrics.py"
Cohesion: 0.25
Nodes (4): _esc(), render(), reset(), test_metrics_counts_requests_by_route_template()

### Community 224 - "resolve"
Cohesion: 0.31
Nodes (5): _matches(), resolve(), Resolved, _tokens(), test_resolve_flags_and_empty_input()

### Community 226 - "api"
Cohesion: 0.29
Nodes (7): env_file, environment, image, ports, restart, WEB_CONCURRENCY, api

### Community 227 - "worker"
Cohesion: 0.29
Nodes (7): disable, worker, command, env_file, healthcheck, image, restart

### Community 228 - "cli.py"
Cohesion: 0.39
Nodes (5): create_admin(), main(), password_check(), read_password(), test_directions_lifespan_closes_provider()

### Community 229 - "places/api.py"
Cohesion: 0.09
Nodes (18): checkin(), CrowdReport, report(), Where, crowd_aggregate(), list_events(), local_today(), now() (+10 more)

### Community 230 - "services"
Cohesion: 0.33
Nodes (5): name, services, volumes, pgdata, valhalla_data

### Community 231 - "healthcheck"
Cohesion: 0.53
Nodes (6): interval, retries, test, timeout, healthcheck, healthcheck

### Community 232 - "_retention_cleanup"
Cohesion: 0.29
Nodes (4): enqueue_due_schedules(), _retention_cleanup(), Schedule, test_schedule_enqueues_once_per_slot_even_when_called_twice()

### Community 233 - "migrate"
Cohesion: 0.40
Nodes (5): command, env_file, image, restart, migrate

### Community 234 - "upsert.py"
Cohesion: 0.33
Nodes (3): _as_list(), upsert_place(), test_upsert_place_is_exported()

### Community 235 - "State"
Cohesion: 0.29
Nodes (5): State, done, editing, failed, sending

### Community 257 - "CodingKeys"
Cohesion: 0.29
Nodes (7): CodingKeys, category, id, lat, lon, mustHave, name

### Community 258 - "ProposalState"
Cohesion: 0.29
Nodes (7): ProposalState, accepted, declined, expired, failed, pending, working

### Community 259 - "_run_job"
Cohesion: 0.29
Nodes (4): backoff_seconds(), _finish(), LeaseLost, _run_job()

### Community 260 - "iOS (цепочка, `Features/Chat/`)"
Cohesion: 0.33
Nodes (5): iOS (цепочка, `Features/Chat/`), Замечания, Проверки, Ревью Ш-32b — узлы графа = ответы пользователя (цепочка вместо кольца), Что сделано

### Community 262 - "WeatherUnavailable"
Cohesion: 0.40
Nodes (3): WeatherUnavailable, FailingWeather, test_build_trip_without_a_forecast_leaves_the_trip_due()

## Knowledge Gaps
- **582 isolated node(s):** `.total`, `.summary`, `.animatableData`, `.state`, `.message` (+577 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1949 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **61 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Что сделано` connect `JolFont` to `deps (52)`?**
  _High betweenness centrality (0.324) - this node is a cross-community bridge._
- **Are the 120 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 120 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.total`, `.summary`, `.animatableData` to the rest of the system?**
  _582 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Sendable` be split into smaller, more focused modules?**
  _Cohesion score 0.08955223880597014 - nodes in this community are weakly interconnected._
- **Why does `format_event()` connect `deps (52)` to `store (43)`, `db.py`, `JolFont`, `test_trip_edits.py`, `brief (28)`?**
  _High betweenness centrality (0.324) - this node is a cross-community bridge._
- **Should `api (106)` be split into smaller, more focused modules?**
  _Cohesion score 0.07744833782569632 - nodes in this community are weakly interconnected._
- **Why does `RouteCard` connect `JolFont` to `ProfileScreen (52)`, `ChatEvent`?**
  _High betweenness centrality (0.323) - this node is a cross-community bridge._