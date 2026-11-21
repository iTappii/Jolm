@testable import Jol
import XCTest

/// Ш-32: decoding of the chat stream and the pure event reduction (`ChatEvent` → `ChatState`).
final class ChatReductionTests: XCTestCase {
    private let museum = UITestSupport.centerPlaceID
    private let cafe = UITestSupport.secondPlaceID

    private func event(_ name: String, _ json: String) -> ChatEvent {
        ChatEvent(SSEEvent(event: name, data: json, id: nil))
    }

    private func place(_ id: String, _ name: String) -> String {
        "{\"id\":\"\(id)\",\"name\":\"\(name)\",\"category\":\"museum\",\"lat\":43.2,\"lon\":76.9}"
    }

    /// The recorded stream (`Resources/Fixtures/chat-trip.sse`, produced with the server's `format_event`).
    private func recorded(_ name: String) async throws -> [ChatEvent] {
        let bytes = Array(ChatStub.fixture(name).utf8)
        XCTAssertFalse(bytes.isEmpty, "fixture \(name) is missing")
        let stream = AsyncStream<UInt8> { continuation in
            for byte in bytes { continuation.yield(byte) }
            continuation.finish()
        }
        var events: [ChatEvent] = []
        for try await raw in SSEParser.events(from: stream) { events.append(ChatEvent(raw)) }
        return events
    }

    // MARK: - Decoding

    func testDecodesEveryKnownEvent() {
        XCTAssertEqual(event("text_delta", "{\"text\":\"Hi\"}"), .textDelta("Hi"))
        XCTAssertEqual(
            event("graph_node", "{\"ord\":2,\"kind\":\"fact\",\"text\":\"Budget\"}"),
            .graphNode(GraphNode(ord: 2, kind: "fact", text: "Budget"))
        )
        guard case .briefUpdated(let brief, let changed) = event(
            "brief_updated",
            "{\"brief\":{\"start_date\":\"2026-12-05\",\"end_date\":\"2026-12-07\",\"budget_kzt\":900000,"
                + "\"has_accommodation\":false,\"must_haves\":[\"plov\"],\"missing\":[\"accommodation\"],"
                + "\"complete\":false},\"changed\":[\"budget_kzt\"]}"
        ) else { return XCTFail("brief_updated did not decode") }
        XCTAssertEqual(changed, ["budget_kzt"])
        XCTAssertEqual(brief.budgetKzt, 900_000)
        XCTAssertEqual(brief.hasAccommodation, false)
        XCTAssertEqual(brief.mustHaves, ["plov"])
        XCTAssertEqual(brief.interests, [], "a missing list becomes empty")
        guard case .mapPlaces(let reason, let places) = event(
            "map_places", "{\"reason\":\"must_have\",\"places\":[\(place(museum, "Fixture Museum"))]}"
        ) else { return XCTFail("map_places did not decode") }
        XCTAssertEqual(reason, "must_have")
        XCTAssertEqual(places.map(\.name), ["Fixture Museum"])
        XCTAssertEqual(
            event("error", "{\"code\":\"llm_error\",\"message\":\"Boom\"}"), .error(code: "llm_error", message: "Boom")
        )
        XCTAssertEqual(event("done", "{\"message_id\":3,\"usage\":{}}"), .done)
    }

    func testRouteReadyAndTripUpdatedKeepTheirFields() {
        guard case .routeReady(let route) = event(
            "route_ready",
            "{\"trip_id\":\"\(ChatStub.tripID)\",\"version\":2,\"days\":3,\"warnings\":[{\"code\":\"over_budget\","
                + "\"date\":null,\"detail\":\"9000\"}],\"must_have_unmet\":[{\"wish\":\"sushi\",\"place_name\":null,"
                + "\"reason\":\"no_place\"}],\"budget\":{\"budget_kzt\":900000,\"status\":\"over\","
                + "\"total_kzt\":909000,"
                + "\"shortfall_kzt\":9000}}"
        ) else { return XCTFail("route_ready did not decode") }
        XCTAssertEqual(route.days, 3)
        XCTAssertEqual(route.warnings.map(\.code), ["over_budget"])
        XCTAssertEqual(route.mustHaveUnmet.first?.wish, "sushi")
        XCTAssertEqual(route.budget?.isOver, true)

        guard case .tripUpdated(let update) = event(
            "trip_updated",
            "{\"trip_id\":\"\(ChatStub.tripID)\",\"version\":3,\"action\":\"remove\",\"changed_days\":[\"2026-12-05\"],"
                + "\"budget\":{\"status\":\"ok\"}}"
        ) else { return XCTFail("trip_updated did not decode") }
        XCTAssertEqual(update.version, 3)
        XCTAssertEqual(update.changedDays, ["2026-12-05"])
    }

    func testUnknownEventsAndBrokenPayloadsBecomeUnknown() {
        XCTAssertEqual(event("future_event", "{\"a\":1}"), .unknown("future_event"))
        XCTAssertEqual(event("graph_node", "not json"), .unknown("graph_node"))
        XCTAssertEqual(event("route_ready", "{\"days\":3}"), .unknown("route_ready"), "no trip id")
        XCTAssertEqual(event("message", "plain"), .unknown("message"))
    }

    // MARK: - Reduction

    func testTextDeltasFormOneAssistantBubbleAfterTheUsersMessage() {
        var state = ChatState()
        state.appendUserMessage("Hello")
        state.beginTurn()
        state.apply(.textDelta("Hel"))
        state.apply(.textDelta("lo there"))
        XCTAssertEqual(state.messages.map(\.text), ["Hello", "Hello there"])
        XCTAssertEqual(state.messages.last?.role, .assistant)
        XCTAssertTrue(state.messages.last?.isStreaming == true)
        state.apply(.done)
        XCTAssertFalse(state.isStreaming)
        XCTAssertFalse(state.messages.last?.isStreaming == true)
        state.beginTurn()
        state.apply(.textDelta("Again"))
        XCTAssertEqual(state.messages.count, 3, "the next turn starts a new bubble")
    }

    func testGraphGrowsInOrderIgnoresDuplicatesAndConvergesOnRouteReady() {
        var state = ChatState()
        state.apply(.graphNode(GraphNode(ord: 2, kind: nil, text: "B")))
        state.apply(.graphNode(GraphNode(ord: 1, kind: nil, text: "A")))
        state.apply(.graphNode(GraphNode(ord: 2, kind: nil, text: "B again")))
        XCTAssertEqual(state.graph.map(\.text), ["A", "B"])
        XCTAssertFalse(state.isConverged)
        state.apply(.routeReady(RouteReady(tripID: UUID(), days: 3)))
        XCTAssertTrue(state.isConverged)
        XCTAssertEqual(state.route?.days, 3)
        state.apply(.graphNode(GraphNode(ord: 3, kind: nil, text: "C")))
        XCTAssertEqual(state.graph.count, 3, "later theses still join before the final node")
        XCTAssertTrue(state.isConverged)
    }

    func testMapPlacesAccumulateForATripAndReplaceForGuestSearch() throws {
        func places(_ ids: [String]) throws -> [MapPlace] {
            let json = "[" + ids.map { place($0, "P-\($0.prefix(2))") }.joined(separator: ",") + "]"
            return try JSONDecoder().decode([MapPlace].self, from: Data(json.utf8))
        }
        var state = ChatState()
        state.apply(.mapPlaces(reason: "must_have", places: try places([museum])))
        state.apply(.mapPlaces(reason: "chosen", places: try places([cafe])))
        state.apply(.mapPlaces(reason: "chosen", places: try places([cafe])))
        XCTAssertEqual(state.mapPlaces.count, 2)
        XCTAssertEqual(state.mapVersion, 2, "an identical list does not redraw the map")
        state.replaceMapPlaces([])
        XCTAssertTrue(state.mapPlaces.isEmpty, "removing the final stop of a trip clears its pins")

        var guest = ChatState()
        guest.apply(.mapPlaces(reason: "search", places: try places([museum])))
        guest.apply(.mapPlaces(reason: "search", places: try places([cafe])))
        XCTAssertEqual(guest.mapPlaces.map { $0.id.uuidString.lowercased() }, [cafe])
        guest.apply(.mapPlaces(reason: "search", places: []))
        XCTAssertEqual(guest.mapPlaces.count, 1, "an empty search keeps the last pins")
    }

    func testErrorEndsTheTurnKeepingThePartialAnswer() {
        var state = ChatState()
        state.appendUserMessage("Hi")
        state.beginTurn()
        state.apply(.textDelta("Let me"))
        state.apply(.error(code: "llm_error", message: "Unavailable"))
        XCTAssertFalse(state.isStreaming)
        XCTAssertEqual(state.failure, .server(message: "Unavailable"))
        XCTAssertEqual(state.messages.last?.text, "Let me")
        state.beginTurn()
        XCTAssertNil(state.failure, "a new turn clears the failure")
    }

    func testTripUpdatedBumpsTheRevisionAndUnknownChangesNothing() {
        var state = ChatState()
        let before = state
        state.apply(.unknown("ping"))
        XCTAssertEqual(state, before)
        state.apply(.tripUpdated(TripUpdated(tripID: UUID(), version: 2, action: "remove", changedDays: [])))
        XCTAssertEqual(state.tripRevision, 1)
    }

    // MARK: - Recorded streams

    func testRecordedTripStreamEndsInAConvergedGraphWithPlacesOnTheMap() async throws {
        var state = ChatState()
        state.appendUserMessage("Plan 3 days in Almaty")
        state.beginTurn()
        let events = try await recorded("chat-trip")
        XCTAssertTrue(events.contains(.unknown("future_event")), "the recording has an event the app does not know")
        for event in events { state.apply(event) }

        XCTAssertEqual(
            state.messages.last?.text,
            "Three days in Almaty, sounds great. I put the museum on your map. Your route is ready."
        )
        XCTAssertEqual(state.graph.map(\.ord), [1, 2, 3])
        XCTAssertTrue(state.isConverged)
        XCTAssertEqual(state.route?.days, 3)
        XCTAssertEqual(state.mapPlaces.map(\.name), ["Fixture Museum", "Fixture Cafe"])
        XCTAssertEqual(state.brief?.budgetKzt, 900_000)
        XCTAssertEqual(state.brief?.hasAccommodation, true)
        // The chain has the answers (days, budget, lodging, the wish), not the three theses of the stream.
        XCTAssertEqual(
            state.chainNodes.map(\.key), ["dates", "budget_kzt", "has_accommodation", "must_haves:Fixture Museum"]
        )
        XCTAssertFalse(state.isStreaming)
        XCTAssertNil(state.failure)
    }

    func testRecordedGuestAndErrorStreams() async throws {
        var guest = ChatState()
        guest.beginTurn()
        for event in try await recorded("chat-guest") { guest.apply(event) }
        XCTAssertEqual(guest.messages.last?.text, "Try the museum in the centre.")
        XCTAssertEqual(guest.mapPlaces.count, 1)
        XCTAssertNil(guest.route)

        var broken = ChatState()
        broken.beginTurn()
        for event in try await recorded("chat-error") { broken.apply(event) }
        XCTAssertEqual(broken.messages.last?.text, "Let me think")
        guard case .server(let message)? = broken.failure else { return XCTFail("expected a server failure") }
        XCTAssertTrue(message.contains("unavailable"))
    }

    // MARK: - Reopening and helpers

    func testReopenedChatRebuildsGraphMessagesAndProposalState() throws {
        let proposal = UUID()
        let json = """
        {"id":"\(ChatStub.chatID)","title":"T","messages":[\
        {"id":1,"role":"user","content":"Hi","finish":"stop","proposal_id":null},\
        {"id":2,"role":"assistant","content":"Move?","finish":"stop","proposal_id":"\(proposal.uuidString)"}],\
        "brief":null,"graph_nodes":[{"ord":2,"kind":"fact","text":"B"},{"ord":1,"kind":"fact","text":"A"}]}
        """
        let detail = try JSONDecoder().decode(ChatDetail.self, from: Data(json.utf8))
        let route = RouteReady(tripID: UUID())
        let state = ChatState(detail: detail, route: route, proposals: [:])
        XCTAssertEqual(state.graph.map(\.text), ["A", "B"])
        XCTAssertTrue(state.chainNodes.isEmpty, "theses alone make no chain nodes")
        XCTAssertEqual(state.messages.map(\.role), [.user, .assistant])
        XCTAssertEqual(state.messages.last?.proposalID, proposal)
        XCTAssertEqual(state.proposals[proposal], .pending, "without a known status the buttons are offered")
        XCTAssertTrue(state.isConverged)
        XCTAssertTrue(state.mapPlaces.isEmpty, "map_places is not stored; the model restores pins from the trip")
    }

    func testGuestHistoryRespectsServerLimitsAndEndsWithTheUser() {
        func message(_ role: ChatMessage.Role, _ text: String) -> ChatMessage {
            ChatMessage(id: UUID().uuidString, role: role, text: text)
        }
        var messages = (0..<30).map { message($0.isMultiple(of: 2) ? .user : .assistant, "m\($0)") }
        messages.append(message(.user, "last"))
        let history = ChatService.guestHistory(from: messages)
        XCTAssertLessThanOrEqual(history.count, ChatService.guestMaxMessages)
        XCTAssertEqual(history.last, ChatService.GuestMessage(role: "user", content: "last"))
        XCTAssertEqual(history.first?.role, "user", "the history opens with a user turn")

        let long = String(repeating: "x", count: 5000)
        let trimmed = ChatService.guestHistory(from: [message(.user, long)])
        XCTAssertEqual(trimmed.first?.content.count, ChatService.guestMaxMessageChars)
        let chunk = String(repeating: "x", count: 2000)
        let big = (0..<5).map { message($0.isMultiple(of: 2) ? .user : .assistant, chunk) }
        let total = ChatService.guestHistory(from: big).reduce(0) { $0 + $1.content.count }
        XCTAssertLessThanOrEqual(total, ChatService.guestMaxTotalChars)
    }

    func testPersonalTripIntentIsDetectedInBothLanguages() {
        for text in ["Three days in Almaty", "plan my trip", "Build me a route", "I have a budget of 500k",
                     "Составь маршрут на 3 дня", "Хочу поездку в Алматы", "бюджет 300 000"] {
            XCTAssertTrue(ChatModel.wantsPersonalTrip(text), text)
        }
        for text in ["Where can I get plov?", "What is Medeu?", "Как добраться до Шымбулака?", "Hi"] {
            XCTAssertFalse(ChatModel.wantsPersonalTrip(text), text)
        }
    }

    func testTransportErrorsMapToFailures() {
        XCTAssertEqual(ChatModel.failure(for: APIError.server(status: 409, code: "chat_busy", message: "")), .busy)
        XCTAssertEqual(ChatModel.failure(for: APIError.server(status: 409, code: "chat_full", message: "")), .full)
        XCTAssertEqual(
            ChatModel.failure(for: APIError.rateLimited(retryAfter: 12.2, message: "")), .rateLimited(retryAfter: 13)
        )
        XCTAssertEqual(ChatModel.failure(for: APIError.network(URLError(.notConnectedToInternet))), .network)
        XCTAssertEqual(
            ChatModel.failure(for: APIError.server(status: 503, code: "llm_unavailable", message: "Down")),
            .server(message: "Down")
        )
        XCTAssertFalse(ChatFailure.full.canRetry)
        let stale = APIError.server(status: 409, code: "proposal_stale", message: "")
        XCTAssertEqual(ChatModel.proposalFailure(stale), .expired)
        XCTAssertEqual(ChatModel.proposalFailure(APIError.network(URLError(.timedOut))), .failed)
    }
}
