# Graph Report - Jol v2  (2026-11-21)

## Corpus Check
- 483 files · ~291,747 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 41 file(s) not represented in the graph (top: .sse 11, (none) 7, .csv 4)

## Summary
- 6539 nodes · 18047 edges · 285 communities (216 shown, 69 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 1250 edges (avg confidence: 0.87)
- Token cost: 211,973 input · 0 output

## Graph Freshness
- Built from commit: `6a07bcdb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- TripLeg
- admin/api.py
- conn
- htmx-1.9.12.min (105)
- TripMapModel (104)
- CodingKey
- sessions.py
- DirectionOption
- budget (78)
- routing/service.py
- ChatModelTests
- get_apple_grants
- places/api.py
- build_tool.py
- test_weather.py
- test_storage.py
- APIClientTests (64)
- layout (61)
- edit (61)
- test_live_plan (59)
- service (59)
- trips/api.py
- test_trip_edits.py
- Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке
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
- test_directions.py
- CrowdSection
- Ш-31 (45)
- Ш-44-server (45)
- test_admin (45)
- test_planner_layout (45)
- DirectionsModel (43)
- store (43)
- SignInModel (42)
- JolFont
- add_place
- test_popular_import (41)
- PlaceCardTabs (40)
- SignInTests (40)
- test_routing (40)
- test_osm_import (39)
- CrowdBlock
- base (39)
- test_analytics.py
- LocationProvider (38)
- edit_tools.py
- ChatState (37)
- CrowdModel
- SessionStore (36)
- analytics/service.py
- adapters (36)
- fetch_one
- test_llm.py
- ChatChainUITests
- docker-compose (35)
- test_osm_pipeline (34)
- test_transit_import (34)
- test_chat_guest (34)
- TripStub
- typing
- AuthState
- execute
- UITestSupport
- DirectionsFormatting (32)
- PlaceTab
- ChatModel
- open_meteo.py
- test_planner_scoring (32)
- find_transit_options
- _macros (30)
- test_transit_search (29)
- test_account_deletion.py
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
- ChatStub
- CoreLocation
- test_memory.py
- schemas (24)
- AppError
- AppContainer
- RoutingProvider
- messages (21)
- scoring (21)
- AppLanguage (20)
- SSEEvent
- PlaceModels (20)
- ForecastView
- test_clientip.py
- CLAUDE (19)
- ChatService
- JOL_SSOT (19)
- schemas (19)
- AuthService
- Foundation
- MapCoordinator
- test_apple (17)
- TECH_PLAN (17)
- PlaceCategoryStyle (17)
- test_planner_budget.py
- XCTestCase
- _resolve_must_have
- LocalStorage
- geometry (16)
- import_transit.py
- HANDOFF (16)
- ToolOutcome
- HomeScreenUITests (16)
- test_bookings (16)
- Ш-20 (15)
- test_ratelimit.py
- dedupe (14)
- JOL_SSOT (14)
- validate
- .swiftlint (14)
- psycopg
- live/engine.py
- TripMapTests
- is_open_now
- load_prompt
- README (13)
- get_settings
- CodingKeys
- ChainNode
- JOL_SSOT (12)
- Ш-07-09 (12)
- TripBudgetSheet
- windows
- SignInGateUITests (12)
- trip_brief.en.v4 (12)
- travel.py
- ChatPanel
- DirectionsUITests
- ChainNodesTests
- TripMapUITests
- Ш-11-12 (10)
- Ш-14 (10)
- test_geocode.py
- .report
- test_trips_followups.py
- PlacesUITests
- serve (9)
- chat/api.py
- project (9)
- Ш-18 (8)
- Ш-23b-server (8)
- resolve
- project (8)
- project (8)
- Failure
- TECH_PLAN (7)
- ChatEvent
- seed_report
- ChatFailure
- project (7)
- jol-logo (7)
- CodingKeys
- Деплой Jol: рабочая инструкция (Ш-51)
- pg-common.sh
- Ш-01-03-06 (6)
- Ш-17 (6)
- Ш-15 (6)
- JolColor
- APIClient
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
- UnknownForecast
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
- auth.py
- fetch_all
- services
- healthcheck
- period
- migrate
- upsert.py
- .parse
- CodingKey
- ProposalState
- error_response
- observability.py
- FeatureGalleryUITests
- register_device
- city_forecast
- CodingKeys
- get_settings
- install_admin
- ListState
- DeleteState
- admin_get
- parse_bbox
- .__call__
- Problem

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
- `Секреты` --references--> `SecretsError`  [INFERRED]
  docs/deploy.md → server/app/auth/keys.py
- `Не проверено` --references--> `S3Storage`  [INFERRED]
  docs/reviews/Ш-51.md → server/app/providers/storage/s3.py
- `Проверки` --references--> `TripMapUITests`  [INFERRED]
  docs/reviews/Ш-37-ios.md → ios/JolUITests/TripMapUITests.swift
- `Что сделано` --references--> `LocationProviding`  [INFERRED]
  docs/reviews/Ш-47-ios.md → ios/Jol/Features/Directions/LocationProvider.swift
- `Замечания и компромиссы` --references--> `test_guest_chat_writes_nothing_to_the_database()`  [INFERRED]
  docs/reviews/Ш-51.md → server/tests/test_chat_guest.py

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

## Communities (285 total, 69 thin omitted)

### Community 0 - "TripLeg"
Cohesion: 0.09
Nodes (12): TripLeg, .activeOption, CodingKeys, chosenModeRaw, costKzt, departAt, estimated, fromItemID (+4 more)

### Community 1 - "admin/api.py"
Cohesion: 0.16
Nodes (33): analytics_page(), _bonus_page(), bonuses_form(), categories_list(), category_edit(), _category_options(), client_ip(), _date_or_none() (+25 more)

### Community 2 - "conn"
Cohesion: 0.27
Nodes (24): AdminError, bonuses_save(), category_save(), event_create(), event_delete(), event_save(), logout(), moderation_decide() (+16 more)

### Community 3 - "htmx-1.9.12.min (105)"
Cohesion: 0.08
Nodes (104): A(), ae(), ar(), at(), B(), be(), br(), bt() (+96 more)

### Community 4 - "TripMapModel (104)"
Cohesion: 0.04
Nodes (30): TripLegSheet, .body, .choices, .current, .header, .language, TripMapLine, TripMapModel (+22 more)

### Community 5 - "CodingKey"
Cohesion: 0.03
Nodes (57): CodingKeys, entriesKzt, eventsKzt, lodgingKzt, mealsKzt, transportKzt, CodingKeys, changedDays (+49 more)

### Community 6 - "sessions.py"
Cohesion: 0.07
Nodes (31): AppleKeyCache, AppleSignIn, challenge(), Challenge, _exchange_code(), fetch_keys(), client_secret(), encrypt_token() (+23 more)

### Community 7 - "DirectionOption"
Cohesion: 0.03
Nodes (57): .currentPage, Congestion, high, low, medium, DirectionLine, DirectionOption, CodingKeys (+49 more)

### Community 8 - "budget (78)"
Cohesion: 0.09
Nodes (32): _cheaper_replacement(), cheaper_variant(), choose_lodging(), Costs, drop_variant(), _in_pool_order(), layout_centre(), leg_cost() (+24 more)

### Community 9 - "routing/service.py"
Cohesion: 0.08
Nodes (23): calculate_cost(), load_tariffs(), recommend(), _recommendation_rank(), Tariff, _finish_group(), get_directions(), _rank() (+15 more)

### Community 10 - "ChatModelTests"
Cohesion: 0.24
Nodes (4): ChatModelTests, Script, StatusBox, .value

### Community 11 - "get_apple_grants"
Cohesion: 0.09
Nodes (9): AppleGrantError, AppleGrants, credentials_configured(), _error(), get_apple_grants(), HttpAppleGrants, MissingCredentialsGrants, StubAppleGrants (+1 more)

### Community 12 - "places/api.py"
Cohesion: 0.09
Nodes (15): client_ip(), address_text(), reverse(), pick_locale(), _geojson(), get_curated_route(), get_place(), list_categories() (+7 more)

### Community 13 - "build_tool.py"
Cohesion: 0.06
Nodes (27): build_trip(), _model_budget(), _model_events(), AddGraphNodeArgs, event_for_model(), NoArgs, place_pin(), search_events() (+19 more)

### Community 14 - "test_weather.py"
Cohesion: 0.18
Nodes (17): cache_key(), Clock, FakeOpenMeteo, make(), test_a_failure_without_any_cache_raises_and_stores_nothing(), test_a_second_call_and_a_nearby_point_are_served_from_the_cache(), test_an_error_body_with_status_200_is_a_failure_too(), test_cache_key_rounds_the_point_and_the_elevation() (+9 more)

### Community 15 - "test_storage.py"
Cohesion: 0.11
Nodes (11): ObjectTooLarge, StorageError, _hmac(), S3Storage, sign_query(), s3(), test_make_storage_by_settings(), test_media_url() (+3 more)

### Community 16 - "APIClientTests (64)"
Cohesion: 0.08
Nodes (6): APIClientTests, ClearedFlag, .value, ProfileTests, StubURLProtocol, .requests

### Community 17 - "layout (61)"
Cohesion: 0.10
Nodes (30): _assign_activities(), assign(), best_day(), item_for(), _assign_meals(), _at(), _centroid(), _Ctx (+22 more)

### Community 18 - "edit (61)"
Cohesion: 0.12
Nodes (30): RetimedDay, _apply_retime(), budget_summary(), _candidates(), _day_stops(), _fetch_variant(), _find_item(), first_fit_replacement() (+22 more)

### Community 19 - "test_live_plan (59)"
Cohesion: 0.14
Nodes (44): d(), set_clock(), configure(), WeatherUnavailable, FakeRouter, TransactionalDatabase, test_build_plan_reads_the_profile(), at() (+36 more)

### Community 20 - "service (59)"
Cohesion: 0.06
Nodes (51): check_event_refs(), clean_text(), format_hours_day(), like_pattern(), list_places(), _norm(), page_number(), parse_bool() (+43 more)

### Community 21 - "trips/api.py"
Cohesion: 0.07
Nodes (33): accept_proposal(), budget_choice(), BudgetChoice, decline_proposal(), _edit(), etag_matches(), get_trip(), get_trip_offline() (+25 more)

### Community 22 - "test_trip_edits.py"
Cohesion: 0.25
Nodes (22): all_items(), assert_day_is_consistent(), built(), check_totals(), day_of(), pick(), plan(), post() (+14 more)

### Community 23 - "Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке"
Cohesion: 0.29
Nodes (6): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-47 (iOS) — загруженность: «я здесь», отчёт, блок в карточке, Что сделано

### Community 24 - "test_submissions (55)"
Cohesion: 0.12
Nodes (46): pending_ids(), test_approve_and_reject_flow(), test_approving_menu_and_price_applies_them_to_the_place(), test_deleted_admin_keeps_the_decision(), test_duplicate_photo_by_hash(), test_duplicate_review_text(), test_menu_and_transit_text_are_filtered_too(), test_moderation_requires_admin_and_csrf() (+38 more)

### Community 26 - "BookingSheet"
Cohesion: 0.08
Nodes (8): BookingModel, .booking, .isSending, BookingSheet, .body, .calendar, .form, .model

### Community 27 - "ProfileScreen (52)"
Cohesion: 0.05
Nodes (27): JolApp, .body, RootView, .body, .content, PlaceholderScreen, .body, Step (+19 more)

### Community 28 - "deps (52)"
Cohesion: 0.08
Nodes (13): Решения владельца, install_id(), make_llm(), error_payload(), run_turn(), TurnRecord, ChatTurn, guest_chat() (+5 more)

### Community 29 - "import_places (51)"
Cohesion: 0.11
Nodes (17): build_record(), clean(), extract(), load(), main(), build_record(), collect(), database_url() (+9 more)

### Community 30 - "Identifiable"
Cohesion: 0.07
Nodes (39): CuratedRouteDetail, .stops, CuratedRoutesList, CuratedRouteStop, CodingKeys, ord, .id, CuratedRouteSummary (+31 more)

### Community 31 - "test_chat (51)"
Cohesion: 0.15
Nodes (40): configure(), Step, day(), new_chat(), open_stream(), say(), StallingLLM, stream_request() (+32 more)

### Community 32 - "APIError"
Cohesion: 0.09
Nodes (14): APIError, invalidBaseURL, invalidResponse, .isUnauthorized, network, rateLimited, server, .serverMessage (+6 more)

### Community 33 - "BookingModels (50)"
Cohesion: 0.06
Nodes (33): Booking, CodingKeys, endsAt, id, kind, note, partySize, place (+25 more)

### Community 34 - "PlacesModel (50)"
Cohesion: 0.04
Nodes (27): EventsModel, MapScreen, .body, .tripOpen, .failedRow, GeoBounds, .height, .queryValue (+19 more)

### Community 35 - "Ш-32 (47)"
Cohesion: 0.06
Nodes (45): ChatGraphView (one-branch thesis graph), ChatPanel (collapsible chat), ChatService (iOS SSE chat client), MapCoordinator+Chat (live map pins), POST /v1/chats/{id}/messages (SSE), TripDaysSheet (route by days sheet), interests.py keyword table (RU+EN), _resolve_must_have (mandatory wishes) (+37 more)

### Community 36 - "DirectionsTests (47)"
Cohesion: 0.10
Nodes (9): .line, from, GeoPoint, .coordinate, .isInServiceArea, Counter, DirectionsTests, FakeLocator (+1 more)

### Community 37 - "test_directions.py"
Cohesion: 0.06
Nodes (36): check_mode(), Maneuver, NoRoute, RouteResult, RoutingError, RoutingUnavailable, encode_polyline6(), decode_polyline6() (+28 more)

### Community 38 - "CrowdSection"
Cohesion: 0.13
Nodes (4): CrowdSection, .actions, .body, .model

### Community 39 - "Ш-31 (45)"
Cohesion: 0.05
Nodes (30): osm_addresses (таблица), GET /v1/geocode/reverse, Схема аккаунтов (users, auth_identities, sessions, otp_codes), Обнаружение повторного использования refresh-токена, Ротация refresh-токена, Access JWT 15 минут и refresh-токен 60 дней, POST /v1/auth/otp/request и /v1/auth/otp/verify, EmailProvider и SmtpEmailProvider (+22 more)

### Community 40 - "Ш-44-server (45)"
Cohesion: 0.06
Nodes (38): Review Ш-44 server: content submissions, LocalStorage (dev only), retention.cleanup worker task, S3Storage with SigV4 presigned PUT, StorageProvider interface, Submissions API (five types), Review Ш-45: autofilter and moderation, Autofilter rules (rejected_auto) (+30 more)

### Community 41 - "test_admin (45)"
Cohesion: 0.15
Nodes (31): place_form_values(), get_place(), add_category(), add_place(), csrf_of(), logged_in(), login(), make_admin() (+23 more)

### Community 42 - "test_planner_layout (45)"
Cohesion: 0.11
Nodes (33): visit_minutes(), _at(), check_invariants(), dates(), DownRouter, fingerprint(), legs_provider(), mk() (+25 more)

### Community 43 - "DirectionsModel (43)"
Cohesion: 0.07
Nodes (22): DirectionsModel, Failure, generic, network, outsideArea, serviceUnavailable, Fallback, chosen (+14 more)

### Community 44 - "store (43)"
Cohesion: 0.12
Nodes (22): Сервер (порядок заполнения, восстановление), save(), merge_filled_order(), add_assistant_message(), add_graph_node(), add_user_message(), brief_from_row(), chat_messages() (+14 more)

### Community 45 - "SignInModel (42)"
Cohesion: 0.07
Nodes (22): CodeStep, .body, DestinationStep, .body, ProblemText, .body, .rateLimitedText, SignInEntryView (+14 more)

### Community 46 - "JolFont"
Cohesion: 0.05
Nodes (33): Проверки, Ревью координатора (2026-11-21), Ревью Ш-32a — граф-кольцо в чате, Решения и ограничения, Что сделано, Не сделано / ограничения, Пробелы серверного API, Проверки (+25 more)

### Community 47 - "add_place"
Cohesion: 0.17
Nodes (21): test_events_keep_the_place_and_block_its_deletion_without_a_merge(), add_place(), make_route(), set_names(), test_categories(), test_curated_routes_published_only(), test_pick_text_fallback_chain(), test_place_detail_404_and_422() (+13 more)

### Community 48 - "test_popular_import (41)"
Cohesion: 0.12
Nodes (20): _bool(), CsvError, import_csv(), _int(), link_manual_to_osm(), _opt(), parse_rows(), _csv() (+12 more)

### Community 49 - "PlaceCardTabs (40)"
Cohesion: 0.09
Nodes (10): PlaceGallery, .body, PlaceTabContent, .body, .overview, .photos, .reviews, PlaceFormatting (+2 more)

### Community 50 - "SignInTests (40)"
Cohesion: 0.10
Nodes (4): ContactValidator, apiError(), SignInTests, Fixture

### Community 51 - "test_routing (40)"
Cohesion: 0.16
Nodes (19): parse_matrix(), test_the_default_push_provider_sends_nothing_and_apns_needs_credentials(), load(), _router(), run(), test_client_error_mapping(), test_client_matrix_pairwise_fallback_marks_unreachable(), test_client_retries_connect_errors_only() (+11 more)

### Community 52 - "test_osm_import (39)"
Cohesion: 0.09
Nodes (25): _parse_days(), _parse_intervals(), parse_opening_hours(), _to_time(), category_for_food(), category_slug(), classify(), _clean() (+17 more)

### Community 53 - "CrowdBlock"
Cohesion: 0.12
Nodes (17): CrowdBlock, CodingKeys, now, samples, today, updatedAt, CrowdHour, CrowdLevel (+9 more)

### Community 54 - "base (39)"
Cohesion: 0.08
Nodes (18): optional_weather(), push(), reset(), router(), weather(), ApnsProvider, _reason(), LogPushProvider (+10 more)

### Community 55 - "test_analytics.py"
Cohesion: 0.20
Nodes (20): AnalyticsLimiters, make_limiters(), ev(), fixtures(), hdr(), post(), rows(), test_a_retried_batch_is_not_counted_twice() (+12 more)

### Community 56 - "LocationProvider (38)"
Cohesion: 0.07
Nodes (8): StubLocationProvider, CoreLocationProvider, LocationProviding, LocationResult, denied, located, unavailable, TestLocator

### Community 57 - "edit_tools.py"
Cohesion: 0.21
Nodes (13): _after_edit(), _chat_trip(), get_trip_plan(), _Names, _no_trip(), NoArgs, plan_days(), _refused() (+5 more)

### Community 58 - "ChatState (37)"
Cohesion: 0.11
Nodes (10): messages, ChatMessage, Role, assistant, user, ChatState, .isConverged, .isEmpty (+2 more)

### Community 59 - "CrowdModel"
Cohesion: 0.12
Nodes (13): CrowdModel, Action, checkIn, report, .isWorking, Outcome, alreadyRecorded, failed (+5 more)

### Community 60 - "SessionStore (36)"
Cohesion: 0.11
Nodes (10): EphemeralTokenStore, TokenStore, SessionStore, .query, SessionTokens, CodingKeys, accessToken, refreshToken (+2 more)

### Community 61 - "analytics/service.py"
Cohesion: 0.11
Nodes (12): _bearer(), _install_id(), post_events(), clean_props(), ClientEvent, EventBatch, anonymize_user(), funnel() (+4 more)

### Community 62 - "adapters (36)"
Cohesion: 0.07
Nodes (21): Availability, BookingLimits, BookingRequest, get_adapter(), limits_of(), PartnerAdapter, PartnerResult, StubAdapter (+13 more)

### Community 63 - "fetch_one"
Cohesion: 0.05
Nodes (46): fetch_one(), _days_ahead(), mountain_notify(), _stats(), _user_locale(), weather_recheck(), mountain_texts(), accept() (+38 more)

### Community 64 - "test_llm.py"
Cohesion: 0.07
Nodes (49): collect(), Completion, Done, ErrorEvent, LLMError, LLMNotConfigured, LLMProvider, LLMTimeout (+41 more)

### Community 65 - "ChatChainUITests"
Cohesion: 0.06
Nodes (11): CoreGraphics, Замечания, Проверки, Ревью Ш-32b — узлы графа = ответы пользователя (цепочка вместо кольца), Что сделано, ChainGeometry, Connector, .height (+3 more)

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
Cohesion: 0.21
Nodes (23): FakeToolCall, parse_sse(), post(), test_bad_tool_arguments_come_back_as_a_tool_error(), test_failure_after_text_keeps_the_text_and_sends_no_done(), test_guest_chat_writes_nothing_to_the_database(), snapshot(), test_history_at_the_limits_is_accepted() (+15 more)

### Community 70 - "TripStub"
Cohesion: 0.19
Nodes (3): TripStub, .isOver, .total

### Community 71 - "typing"
Cohesion: 0.03
Nodes (33): ChatLimiters, make_limiters(), EventList, EventVenue, JsonFormatter, setup_logging(), load_memory(), Memory (+25 more)

### Community 72 - "AuthState"
Cohesion: 0.11
Nodes (12): Не сделано, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-49 (iOS) — кнопка и запрос бронирования, Что сделано, AccountGate, AccountGateSheet (+4 more)

### Community 73 - "execute"
Cohesion: 0.04
Nodes (63): add_route_place(), move_route_item(), remove_route_item(), _renumber(), delete_account(), _remove_submissions(), lock_identity(), Database (+55 more)

### Community 74 - "UITestSupport"
Cohesion: 0.10
Nodes (10): FixtureURLProtocol, UITestSupport, .directionsJSON, .eventsItemsJSON, .favoritesJSON, .isStubbed, .placesJSON, .routeJSON (+2 more)

### Community 75 - "DirectionsFormatting (32)"
Cohesion: 0.07
Nodes (11): JolRadius, JolSpacing, L10n, DirectionsFormatting, .carousel, .chips, DirectionsPanel, .content (+3 more)

### Community 76 - "PlaceTab"
Cohesion: 0.10
Nodes (14): .body, Navigator, App, appleMaps, .id, twoGIS, NavigatorButton, .body (+6 more)

### Community 77 - "ChatModel"
Cohesion: 0.13
Nodes (3): ChatModel, .isGuestTranscript, .isStreaming

### Community 78 - "open_meteo.py"
Cohesion: 0.19
Nodes (8): DayWeather, _hour(), _hour_json(), OpenMeteoProvider, parse_response(), test_parse_rejects_a_broken_answer(), test_parse_the_recorded_response(), test_without_a_key_the_free_host_is_used()

### Community 79 - "test_planner_scoring (32)"
Cohesion: 0.24
Nodes (16): no_event_bonus(), UnknownCrowd, make_place(), scored(), test_an_interest_match_beats_a_little_popularity(), test_crowd_penalty_scales_with_intolerance(), test_default_hooks_mean_no_data(), test_event_bonus_counts_double_when_asked() (+8 more)

### Community 80 - "find_transit_options"
Cohesion: 0.09
Nodes (18): _candidates(), find_transit_options(), _line_key(), _local_hour(), Stop, TransitNetwork, airport_routes(), build_network() (+10 more)

### Community 81 - "_macros (30)"
Cohesion: 0.10
Nodes (5): checkbox macro, csrf_field macro, field macro, select macro, textarea macro

### Community 82 - "test_transit_search (29)"
Cohesion: 0.11
Nodes (25): haversine_m(), path_distance_m(), directed(), _resample(), hop_speed_boost(), build(), _load(), _load_dev_network() (+17 more)

### Community 83 - "test_account_deletion.py"
Cohesion: 0.11
Nodes (27): apple_login(), apple_signin(), auth(), count(), delivery(), ec_key(), FakeGrants, http_grants() (+19 more)

### Community 84 - "valhalla (29)"
Cohesion: 0.18
Nodes (10): MatrixResult, _costing_body(), _loc(), ValhallaRouter, find(), test_integration_matrix_and_unreachable(), go(), test_integration_route_three_profiles() (+2 more)

### Community 86 - "EventModels (28)"
Cohesion: 0.08
Nodes (19): EventItem, CodingKeys, adLabel, category, description, endsAt, id, isAd (+11 more)

### Community 87 - "brief (28)"
Cohesion: 0.09
Nodes (20): apply_update(), brief_data_block(), BriefError, BriefUpdate, _clean_items(), empty_brief(), fill_entries(), _merge_list() (+12 more)

### Community 88 - "email.py"
Cohesion: 0.09
Nodes (12): DevEmailProvider, EmailProvider, EmailSettings, get_email_provider(), normalize_email(), SmtpEmailProvider, _client_ip(), OtpRequest (+4 more)

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
Nodes (20): media_url(), budget_json(), chosen_option(), days_json(), item_json(), leg_json(), leg_late_by_s(), local() (+12 more)

### Community 93 - "test_planner_candidates (26)"
Cohesion: 0.18
Nodes (17): Candidate, select_candidates(), fill_profile(), test_card_shows_crowd_only_with_enough_data(), test_planner_uses_the_profile_for_quiet_travellers(), brief(), fixture_places(), names() (+9 more)

### Community 94 - "AppConfig (26)"
Cohesion: 0.14
Nodes (6): AppConfig, .apiBaseURL, .appleSignInEnabled, .isSimulator, AppConfigTests, APIBaseURLTests

### Community 96 - "CoreLocation"
Cohesion: 0.22
Nodes (4): CoreLocation, AlmatyCamera, MapLibre, UIKit

### Community 97 - "test_memory.py"
Cohesion: 0.12
Nodes (38): call(), add_event(), test_admin_event_shown_on_localized_map_and_venue_card(), test_guest_can_search_evening_events_without_a_trip(), test_map_rejects_invalid_windows_and_boxes(), test_map_window_overlap_coordinates_and_hidden_places(), test_planner_and_chat_offer_an_attendable_event_with_its_ad_label(), test_public_places_are_ad_free_in_admin_database_and_map() (+30 more)

### Community 98 - "schemas (24)"
Cohesion: 0.15
Nodes (20): EventItem, CategoriesList, Category, CategoryRef, CrowdHour, CrowdLevel, CrowdProfile, CuratedRouteDetail (+12 more)

### Community 99 - "AppError"
Cohesion: 0.05
Nodes (41): bearer_token(), delete_me(), logout(), me(), refresh(), RefreshRequest, current_user(), revoke() (+33 more)

### Community 100 - "AppContainer"
Cohesion: 0.06
Nodes (25): Итог прогона (Ш-37, Ш-47, Ш-48, Ш-49), Не сделано / ограничения, Пробелы серверного API, Проверки, Ревью координатора (2026-11-21), Ревью Ш-37 (iOS) — полная карта маршрута (веха M3), Что сделано, AppContainer (+17 more)

### Community 101 - "RoutingProvider"
Cohesion: 0.15
Nodes (4): leg_tools(), DirectionsLegs, RoutingProvider, test_planner_legs_ask_for_one_variant_per_mode()

### Community 102 - "messages (21)"
Cohesion: 0.17
Nodes (7): day_text(), _hour(), proposal_texts(), Problem, stop_problem(), visit_hours(), test_rules_thresholds()

### Community 103 - "scoring (21)"
Cohesion: 0.23
Nodes (9): Resolved, _clip01(), interest_match(), intolerance(), pick_pool(), rank(), Score, score_place() (+1 more)

### Community 104 - "AppLanguage (20)"
Cohesion: 0.14
Nodes (11): AppLanguage, english, .id, .nativeName, russian, system, LanguageSettings, .code (+3 more)

### Community 105 - "SSEEvent"
Cohesion: 0.16
Nodes (4): SSEEvent, SSEParser, GuestBody, GuestMessage

### Community 106 - "PlaceModels (20)"
Cohesion: 0.10
Nodes (20): CodingKeys, address, booking, category, crowd, description, events, hours (+12 more)

### Community 107 - "ForecastView"
Cohesion: 0.20
Nodes (5): replan(), ForecastView, HourWeather, test_a_rainy_forecast_moves_the_planner_not_the_unknown_one(), test_rain_rules_thunder_amount_and_unknown()

### Community 108 - "test_clientip.py"
Cohesion: 0.09
Nodes (24): Замечания и компромиссы, Не проверено, Проверки, Ревью координатора (2026-11-21), Ревью Ш-51 — продакшен-инфраструктура (кодовая часть), Что сделано, client_ip(), _parse() (+16 more)

### Community 109 - "CLAUDE (19)"
Cohesion: 0.13
Nodes (11): .claude/CLAUDE.md graphify trigger document, graphify skill triggered by /graphify, Root CLAUDE.md project instructions, ADR numbering and supersession rules, ADR index and rules document, ADR status values (предложено, принято, отклонено, заменено), Decision log (SSOT §17), JOL_SSOT product single source of truth (+3 more)

### Community 110 - "ChatService"
Cohesion: 0.18
Nodes (7): Load, failed, idle, loaded, loading, Loaded, ChatService

### Community 111 - "JOL_SSOT (19)"
Cohesion: 0.15
Nodes (17): Weather day-suffers thresholds and planning rules, Prioritized next steps list, Place crowd level data source (open), Favorites feature, Getting-there screen with mode carousel, Profile menu and swipe sidebar navigation, Whole-trip route building by day, Transport options between points (walk, scooter, bus, metro, taxi, car) (+9 more)

### Community 112 - "schemas (19)"
Cohesion: 0.15
Nodes (10): _clean(), _line(), MenuItem, MenuPayload, _Payload, PhotoPayload, PricePayload, _required() (+2 more)

### Community 113 - "AuthService"
Cohesion: 0.05
Nodes (33): AuthenticationServices, AppleSignInView, .body, .service, AppleCredential, CodingKeys, authorizationCode, identityToken (+25 more)

### Community 114 - "Foundation"
Cohesion: 0.09
Nodes (8): Foundation, Polyline, EventsService, FavoritesList, FavoritesModel, FavoritesSheet, .body, Observation

### Community 115 - "MapCoordinator"
Cohesion: 0.14
Nodes (3): MapCoordinator, Layer, MapView

### Community 116 - "test_apple (17)"
Cohesion: 0.26
Nodes (11): apple_jwks(), get_nonce(), issue(), private_key(), submit(), test_invalid_signature_does_not_consume_challenge(), test_outage_is_rate_limited(), test_rejects_expired_nonce_and_wrong_algorithm_before_fetch() (+3 more)

### Community 117 - "TECH_PLAN (17)"
Cohesion: 0.13
Nodes (13): ADR 0003 default values for open SSOT questions, Default behavior table for SSOT §16 questions, Refresh token reuse grace window of 10 seconds, Deferred review items to fix before production or TestFlight, Bookings and orders via partner APIs, Two-stage monetization plan (growth then partnership), Open questions register (SSOT §16), Promoted events shown during trip dates (+5 more)

### Community 118 - "PlaceCategoryStyle (17)"
Cohesion: 0.17
Nodes (3): .content, PlaceCategoryStyle, .allImages

### Community 119 - "test_planner_budget.py"
Cohesion: 0.20
Nodes (18): Case, over_budget_case(), plan_for(), priced(), stops(), test_cheaper_variant_replaces_meals_too(), test_cheaper_variant_swaps_for_cheaper_places_and_cheapest_lodging(), test_drop_variant_removes_the_least_valuable_costly_optionals_only() (+10 more)

### Community 120 - "XCTestCase"
Cohesion: 0.11
Nodes (5): SessionStoreTests, AppleSignInUITests, MapLaunchUITests, Jol, XCTest

### Community 121 - "_resolve_must_have"
Cohesion: 0.20
Nodes (6): like_pattern(), _area(), MustHave, _resolve_must_have(), trip_days(), test_like_pattern_escapes()

### Community 122 - "LocalStorage"
Cohesion: 0.26
Nodes (4): LocalStorage, _sig(), test_local_storage_roundtrip_and_traversal(), test_storage_delete_job_removes_objects()

### Community 123 - "geometry (16)"
Cohesion: 0.20
Nodes (8): _in_ring(), _inside(), representative_point(), _ring_area_centroid(), test_centroid_of_convex_polygon(), test_degenerate_input(), test_point_avoids_hole(), test_point_is_inside_concave_polygon()

### Community 124 - "import_transit.py"
Cohesion: 0.11
Nodes (17): apply_manual_stops(), build_network(), extract(), haversine_m(), load_seed(), localized_names(), main(), norm_name() (+9 more)

### Community 125 - "HANDOFF (16)"
Cohesion: 0.14
Nodes (14): OTP invalid versus expired error distinction, HANDOFF session handoff note (2026-11-21), Local dev environment on owner's Mac (Docker, PostGIS port 5433, Xcode), Items needed from the project owner, AppContainer dependency injection container, JOL_APPLE_SIGN_IN_ENABLED build switch, iOS app README (layout, build, config), UI-test stub launch switches (DEBUG) (+6 more)

### Community 126 - "ToolOutcome"
Cohesion: 0.27
Nodes (8): _add_graph_node(), _build_trip(), _search_events(), _search_places(), handle_tool(), _update_trip_brief(), ToolOutcome, parse_tool_args()

### Community 128 - "test_bookings (16)"
Cohesion: 0.18
Nodes (13): booking_settings(), link_partner(), place(), test_book_from_card_and_read_confirmation(), test_event_ticket_requires_a_current_event_at_the_partner_place(), test_limits_below_the_minimum_and_localized_messages(), test_only_connected_partners_offer_bookings(), test_pagination_at_equal_timestamps() (+5 more)

### Community 129 - "Ш-20 (15)"
Cohesion: 0.19
Nodes (10): Ревью Ш-20 (движок маршрутизации Valhalla), RoutingProvider, ValhallaRouter, FakeRouter, Valhalla routing engine (docker, valhalla-scripted), Цель make osm-pbf и общий кэш OSM, Ревью Ш-21 (общественный транспорт), Импорт транспорта (120 маршрутов, 956 остановок), Поиск транспорта до 1 пересадки (transit.py), POST /v1/directions (+2 more)

### Community 130 - "test_ratelimit.py"
Cohesion: 0.16
Nodes (19): acquire(), acquire_own(), cleanup_expired(), key_hash(), RateRule, test_a_committed_count_survives_a_failing_request(), test_a_refused_request_counts_nothing_anywhere(), test_cleanup_removes_only_expired_rows() (+11 more)

### Community 131 - "dedupe (14)"
Cohesion: 0.20
Nodes (7): class_of(), dedupe(), distance_m(), _fill_tags(), name_set(), normalize_name(), test_dedupe_rules_pure()

### Community 132 - "JOL_SSOT (14)"
Cohesion: 0.19
Nodes (10): ADR 0002 planner vs LLM record, Budget overrun offers two variants for user choice (SSOT §16.3), Maximum trip length 60 days assumption, Dynamic one-branch thesis graph in chat, Collapsing AI chat home screen over map, Trip input parameters collected in chat, Data model draft (tables), LLMProvider interface (fake provider in dev) (+2 more)

### Community 134 - ".swiftlint (14)"
Cohesion: 0.14
Nodes (13): disabled_rules, excluded, file_length, warning, function_body_length, warning, identifier_name, min_length (+5 more)

### Community 135 - "psycopg"
Cohesion: 0.09
Nodes (20): apply_migrations(), checksum_of(), discover(), main(), MigrationError, counts(), main(), chat_env() (+12 more)

### Community 136 - "live/engine.py"
Cohesion: 0.30
Nodes (10): _count(), _count_plan(), _count_rows(), find_proposal(), problem_of(), _minutes(), _option(), outdoor() (+2 more)

### Community 138 - "is_open_now"
Cohesion: 0.20
Nodes (10): _covers(), group_hours(), is_open_now(), at(), test_open_now_across_midnight(), test_open_now_converts_timezone(), test_open_now_no_hours_is_none(), test_open_now_round_the_clock() (+2 more)

### Community 140 - "load_prompt"
Cohesion: 0.18
Nodes (9): load_prompt(), Prompt, versions(), test_every_prompt_exists_in_both_languages(), test_guest_prompt_exposes_place_and_event_search(), test_render_fills_today(), test_trip_brief_asks_dates_then_budget_then_lodging(), test_unknown_locale_falls_back_to_english_and_unknown_prompt_fails() (+1 more)

### Community 141 - "README (13)"
Cohesion: 0.27
Nodes (12): JOL_MAP_STYLE_URL map style configuration, Bundled placeholder style (MapLibre demo tiles, temporary), Map demo HTML page, load(theme, lang) style loader function, Theme and label-language selectors, almaty.pmtiles vector tile archive, build_tiles.sh Planetiler tile build, maps README (tiles, demo, hosting, styles) (+4 more)

### Community 142 - "get_settings"
Cohesion: 0.11
Nodes (36): decrypt_token(), challenge_key(), _checked(), decrypt(), encrypt(), _explicit(), _fernet_keys(), _generate() (+28 more)

### Community 143 - "CodingKeys"
Cohesion: 0.17
Nodes (12): CodingKeys, budgetKzt, complete, crowdTolerance, endDate, filledOrder, hasAccommodation, interests (+4 more)

### Community 144 - "ChainNode"
Cohesion: 0.09
Nodes (25): iOS (цепочка, `Features/Chat/`), ChainNode, .id, ChainConnector, .animatableData, ChatChainFooter, .body, .selectedIndex (+17 more)

### Community 145 - "JOL_SSOT (12)"
Cohesion: 0.21
Nodes (11): Temporary bonus formula with demand multipliers, Memory penalty for rejected place categories, Demand coefficient for bonus amount, Downloaded route stored on device, Guest user without account, Memory and personalization for registered users, Registered user, User content submission and bonus system (+3 more)

### Community 146 - "Ш-07-09 (12)"
Cohesion: 0.27
Nodes (8): Импорт OSM по bbox Алматы (pyosmium), Подборка popular_places.csv (102 места), Ревью Ш-07/08/09 (данные мест), Слияние строк мест (data/osm/merge.py), Ревью доработки Ш-08: дедупликация мест OSM, Центроид полигона (data/osm/geometry.py), Импорт мультиполигонов-отношений OSM, Ревью доработки Ш-08: отношения OSM и связь ручных мест

### Community 147 - "TripBudgetSheet"
Cohesion: 0.10
Nodes (8): TripBudgetSheet, .body, .language, TripDayListView, .body, TripFormatting, .budgetChip, .loadedPanel

### Community 150 - "trip_brief.en.v4 (12)"
Cohesion: 0.23
Nodes (10): Trip brief prompt EN v1, Trip brief prompt EN v2, Trip brief prompt EN v3, Reply after build_trip (budget status rules), Trip brief prompt EN v4, Edit built plan via get/remove/replace tools, Trip brief prompt RU v1, Trip brief prompt RU v2 (+2 more)

### Community 151 - "travel.py"
Cohesion: 0.11
Nodes (7): HaversineMatrix, pick_default(), _plan_seconds(), PreferredLegs, RouterMatrix, TravelTimes, DirectionOption

### Community 152 - "ChatPanel"
Cohesion: 0.08
Nodes (14): ChainLabels, BriefFormatting, ChatPanel, .canSend, .header, .inputBar, .isActive, CollapsedChatBar (+6 more)

### Community 154 - "ChainNodesTests"
Cohesion: 0.10
Nodes (11): Kind, budget, crowd, dates, interests, lodging, mustHave, pace (+3 more)

### Community 156 - "Ш-11-12 (10)"
Cohesion: 0.27
Nodes (8): Ревью Ш-11/12 (векторные тайлы и стиль карты), Статический сервер тайлов serve.py (Range, CORS), Генератор стилей build_styles.py (jol-light/dark, RU/EN), Сборка тайлов Planetiler (build_tiles.sh, almaty.pmtiles), AppConfig и JOL_MAP_STYLE_URL, MapView (UIViewRepresentable над MLNMapView), Ревью Ш-13 (iOS проект и карта), project.yml (XcodeGen) и Jol.xcodeproj

### Community 157 - "Ш-14 (10)"
Cohesion: 0.27
Nodes (8): APIClient с single-flight refresh, AppContainer (DI через Environment), LanguageSettings и L10n (RU/EN), Ревью Ш-14 (iOS-каркас), SSEClient и SSEParser, ProfileMenuSheet (меню аккаунта), ProfileModel (load, signOut, deleteAccount), Ревью Ш-16 (меню профиля)

### Community 158 - "test_geocode.py"
Cohesion: 0.21
Nodes (6): load_fixture(), sconn(), test_address_when_no_place_close(), test_bare_point_and_validation(), test_extract_fixture(), test_place_wins_inside_radius()

### Community 159 - ".report"
Cohesion: 0.19
Nodes (6): CrowdBody, CodingKeys, lat, level, lon, CrowdService

### Community 160 - "test_trips_followups.py"
Cohesion: 0.09
Nodes (27): _distinct_routes(), _near(), same_path(), lock_log(), RacingRouter, road_leg(), test_a_trip_changed_while_planning_is_retried_once(), test_a_trip_that_keeps_changing_answers_409_and_writes_nothing() (+19 more)

### Community 162 - "serve (9)"
Cohesion: 0.12
Nodes (6): database_url(), main(), H, build(), interp(), name_expr()

### Community 163 - "chat/api.py"
Cohesion: 0.14
Nodes (14): _chat_json(), create_chat(), CreateChat, _finish(), get_chat(), lease_sec(), list_chats(), _own_chat() (+6 more)

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

### Community 171 - "Failure"
Cohesion: 0.12
Nodes (13): Failure, invalid, network, notSupported, other, rateLimited, signedOut, unavailable (+5 more)

### Community 172 - "TECH_PLAN (7)"
Cohesion: 0.38
Nodes (6): ADR 0001 technology stack record, API draft under /v1 prefix, Target architecture (iOS, FastAPI, worker, Valhalla, PostGIS), Postgres job queue with SKIP LOCKED, SSE chat stream events (text_delta, graph_node, map_places, route_ready), Valhalla routing engine for walk, scooter, car

### Community 173 - "ChatEvent"
Cohesion: 0.08
Nodes (62): ChatBrief, .isEmpty, ChatDetail, ChatEvent, briefUpdated, BriefUpdated, done, error (+54 more)

### Community 174 - "seed_report"
Cohesion: 0.36
Nodes (10): add_item(), checkin(), make_trip(), make_user(), seed_report(), test_a_checkin_is_not_a_visit_for_someone_elses_trip_or_another_place_or_variant(), test_a_visit_is_a_checkin_inside_the_item_window_plus_tolerance(), test_admin_page_needs_login_and_shows_the_report() (+2 more)

### Community 175 - "ChatFailure"
Cohesion: 0.22
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

### Community 184 - "JolColor"
Cohesion: 0.29
Nodes (3): JolColor, UIColor, .color

### Community 185 - "APIClient"
Cohesion: 0.07
Nodes (14): APIClient, RefreshBody, CodingKeys, refreshToken, Refresher, Endpoint, Method, delete (+6 more)

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

### Community 213 - "UnknownForecast"
Cohesion: 0.29
Nodes (3): Forecast, is_rainy(), UnknownForecast

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
Cohesion: 0.29
Nodes (4): _esc(), render(), reset(), test_metrics_counts_requests_by_route_template()

### Community 224 - "resolve"
Cohesion: 0.38
Nodes (4): _matches(), resolve(), _tokens(), test_resolve_flags_and_empty_input()

### Community 226 - "api"
Cohesion: 0.29
Nodes (7): env_file, environment, image, ports, restart, WEB_CONCURRENCY, api

### Community 227 - "worker"
Cohesion: 0.29
Nodes (7): disable, worker, command, env_file, healthcheck, image, restart

### Community 228 - "auth.py"
Cohesion: 0.11
Nodes (19): csrf_for_session(), hash_password(), hash_token(), load_session(), login(), LoginResult, logout(), new_token() (+11 more)

### Community 229 - "fetch_all"
Cohesion: 0.06
Nodes (30): checkin(), CrowdReport, report(), Where, crowd_aggregate(), aggregate(), card_block(), _distance() (+22 more)

### Community 230 - "services"
Cohesion: 0.33
Nodes (5): name, services, volumes, pgdata, valhalla_data

### Community 231 - "healthcheck"
Cohesion: 0.53
Nodes (6): interval, retries, test, timeout, healthcheck, healthcheck

### Community 232 - "period"
Cohesion: 0.22
Nodes (5): period(), place_visits_report(), test_funnel_counts_people_per_step(), test_period_defaults_swaps_and_uses_local_days(), test_place_visits_report_for_a_period()

### Community 233 - "migrate"
Cohesion: 0.40
Nodes (5): command, env_file, image, restart, migrate

### Community 234 - "upsert.py"
Cohesion: 0.33
Nodes (3): _as_list(), upsert_place(), test_upsert_place_is_exported()

### Community 257 - "CodingKey"
Cohesion: 0.03
Nodes (63): CodingKeys, brief, graphNodes, id, title, CodingKeys, content, finish (+55 more)

### Community 258 - "ProposalState"
Cohesion: 0.20
Nodes (7): ProposalState, accepted, declined, expired, failed, pending, working

### Community 259 - "error_response"
Cohesion: 0.36
Nodes (6): error_response(), install_error_handlers(), _app_error(), _http_error(), _unhandled(), _validation_error()

### Community 260 - "observability.py"
Cohesion: 0.38
Nodes (4): capture_exception(), init_error_reporting(), _release(), test_error_reporting_is_off_without_a_dsn_and_safe_without_the_sdk()

### Community 264 - "CodingKeys"
Cohesion: 0.33
Nodes (6): CodingKeys, budgetKzt, remainingKzt, shortfallKzt, status, totalKzt

### Community 266 - "get_settings"
Cohesion: 0.07
Nodes (26): get_sms_provider(), normalize_phone(), SmsProvider, _StubSmsProvider, get_settings(), create_app(), signing_secret(), test_end_to_end_per_ip_limit_follows_the_real_client() (+18 more)

### Community 267 - "install_admin"
Cohesion: 0.33
Nodes (3): install_admin(), _login_required(), is_htmx()

### Community 274 - "ListState"
Cohesion: 0.40
Nodes (5): ListState, failed, idle, loaded, loading

### Community 275 - "DeleteState"
Cohesion: 0.40
Nodes (4): DeleteState, deleting, failed, idle

### Community 276 - "admin_get"
Cohesion: 0.40
Nodes (3): admin_get(), admin_post(), AdminLoginRequired

### Community 277 - "parse_bbox"
Cohesion: 0.40
Nodes (3): parse_bbox(), test_parse_bbox_ok(), test_parse_bbox_rejects()

### Community 281 - "Problem"
Cohesion: 0.67
Nodes (3): Problem, failed, limit

## Knowledge Gaps
- **582 isolated node(s):** `.state`, `.message`, `.body`, `.body`, `.identity` (+577 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1951 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **69 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `format_event()` connect `deps (52)` to `chat/api.py`, `JolFont`, `test_trip_edits.py`?**
  _High betweenness centrality (0.318) - this node is a cross-community bridge._
- **Are the 120 inferred relationships involving `conn()` (e.g. with `main()` and `main()`) actually correct?**
  _`conn()` has 120 INFERRED edges - model-reasoned connections that need verification._
- **What connects `.state`, `.message`, `.body` to the rest of the system?**
  _582 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `TripLeg` be split into smaller, more focused modules?**
  _Cohesion score 0.09090909090909091 - nodes in this community are weakly interconnected._
- **Why does `Что сделано` connect `JolFont` to `deps (52)`?**
  _High betweenness centrality (0.318) - this node is a cross-community bridge._
- **Should `htmx-1.9.12.min (105)` be split into smaller, more focused modules?**
  _Cohesion score 0.0782051282051282 - nodes in this community are weakly interconnected._
- **Why does `RouteCard` connect `JolFont` to `ChainNode`, `ChatEvent`?**
  _High betweenness centrality (0.317) - this node is a cross-community bridge._