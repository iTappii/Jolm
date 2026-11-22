@testable import Jol
import XCTest

/// Ш-54: the live route — wire shapes, the reducer, edge-label geometry, duration texts and the choose flow, all on the
/// recorded fixtures (`chat-live-1…4.sse`).
@MainActor
// swiftlint:disable:next type_body_length
final class LiveRouteTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let chatID = ChatStub.chatID

    private func events(_ fixture: String) -> [ChatEvent] {
        ChatStub.fixture(fixture).components(separatedBy: "\n\n").filter { !$0.isEmpty }.compactMap { chunk in
            var name = ""
            var data = ""
            for line in chunk.components(separatedBy: "\n") {
                if line.hasPrefix("event: ") { name = String(line.dropFirst(7)) }
                if line.hasPrefix("data: ") { data = String(line.dropFirst(6)) }
            }
            return ChatEvent(SSEEvent(event: name, data: data, id: nil))
        }
    }

    private func liveRoute(_ turn: Int) throws -> LiveRoute {
        for case .liveRoute(let route) in events("chat-live-\(turn)") { return route }
        throw XCTSkip("no live_route in turn \(turn)")
    }

    // MARK: - Decoding

    func testTurnOneDecodesOneStopWithTwoAlternatives() throws {
        let route = try liveRoute(1)
        XCTAssertEqual(route.stops.count, 1)
        XCTAssertEqual(route.stops[0].wish, "Chinese food")
        XCTAssertEqual(route.stops[0].place.name, "Lan Zhou Noodle House")
        XCTAssertEqual(route.stops[0].alternatives.map(\.name), ["Dragon Pearl", "Beijing Garden"])
        XCTAssertTrue(route.legs.isEmpty)
        XCTAssertEqual(route.coordinates.count, 3, "the camera shows stops and alternatives")
    }

    func testTurnThreeDecodesLegsWithModes() throws {
        let route = try liveRoute(3)
        XCTAssertEqual(route.stops.map(\.ord), [1, 2, 3])
        XCTAssertEqual(route.legs.map(\.mode), [.transit, .car])
        XCTAssertEqual(route.legs.map(\.durationS), [1080, 1260])
        XCTAssertEqual(route.edges.map(\.id), ["1-2", "2-3"])
        XCTAssertEqual(route.edges.map(\.toNumber), [2, 3])
    }

    func testUnknownModeAndMissingFieldsDoNotBreakTheDecode() throws {
        let json = """
        {"stops":[{"ord":2,"place":{"id":"1a000000-0000-4000-8000-000000000001","name":"A","lat":1,"lon":2}}],
         "legs":[{"from_ord":1,"to_ord":2,"mode":"rocket","duration_s":60}],"future":1}
        """
        let route = try JSONDecoder().decode(LiveRoute.self, from: Data(json.utf8))
        XCTAssertEqual(route.stops[0].alternatives, [])
        XCTAssertNil(route.legs[0].mode)
        XCTAssertTrue(route.edges.isEmpty, "a leg whose stops are not both on the route is not drawn")
    }

    func testRouteReadyIsStillDecodedAndLiveRouteIsPartOfTheEventStream() {
        let names = events("chat-live-4").map { event -> String in
            switch event {
            case .routeReady: "route_ready"
            case .textDelta: "text"
            case .done: "done"
            default: "other"
            }
        }
        XCTAssertEqual(names, ["text", "route_ready", "done"])
        XCTAssertTrue(events("chat-live-2").contains { if case .liveRoute = $0 { true } else { false } })
    }

    func testChatDetailCarriesTheLiveRouteAndToleratesGarbage() throws {
        let route = try liveRoute(2)
        let live = String(data: try JSONEncoderForTests.encode(route), encoding: .utf8) ?? "{}"
        let json = "{\"id\":\"\(chatID)\",\"messages\":[],\"live_route\":\(live)}"
        let detail = try JSONDecoder().decode(ChatDetail.self, from: Data(json.utf8))
        XCTAssertEqual(detail.liveRoute, route)
        let broken = try JSONDecoder().decode(
            ChatDetail.self, from: Data("{\"id\":\"\(chatID)\",\"live_route\":\"nope\"}".utf8))
        XCTAssertNil(broken.liveRoute)
    }

    // MARK: - Reducer

    func testStopsGrowOneByOneAndRouteReadyClearsTheLiveRoute() throws {
        var state = ChatState()
        for turn in 1...3 {
            for event in events("chat-live-\(turn)") { state.apply(event) }
            XCTAssertEqual(state.liveRoute?.stops.count, turn)
        }
        XCTAssertEqual(state.liveVersion, 3)
        XCTAssertTrue(state.mapPlaces.isEmpty, "the live route does not use map_places")
        for event in events("chat-live-4") { state.apply(event) }
        XCTAssertNil(state.liveRoute, "the trip by days takes over")
        XCTAssertTrue(state.isConverged)
        XCTAssertEqual(state.liveVersion, 4)
    }

    func testSameRouteTwiceDoesNotBumpTheVersion() throws {
        var state = ChatState()
        let route = try liveRoute(1)
        state.apply(.liveRoute(route))
        state.apply(.liveRoute(route))
        XCTAssertEqual(state.liveVersion, 1)
    }

    func testReopenedChatRestoresTheLiveRouteUnlessThereIsAFinishedTrip() throws {
        let route = try liveRoute(3)
        let live = String(data: try JSONEncoderForTests.encode(route), encoding: .utf8) ?? "{}"
        let detail = try JSONDecoder().decode(
            ChatDetail.self, from: Data("{\"id\":\"\(chatID)\",\"live_route\":\(live)}".utf8))
        XCTAssertEqual(ChatState(detail: detail, route: nil, proposals: [:]).liveRoute, route)
        let finished = ChatState(detail: detail, route: RouteReady(tripID: UUID()), proposals: [:])
        XCTAssertNil(finished.liveRoute)
    }

    // MARK: - Geometry

    func testLabelSitsAboveTheMiddleOfAHorizontalEdge() {
        let center = LiveRouteGeometry.labelCenter(from: CGPoint(x: 0, y: 100), to: CGPoint(x: 200, y: 100), offset: 20)
        XCTAssertEqual(center.x, 100, accuracy: 0.001)
        XCTAssertEqual(center.y, 80, accuracy: 0.001)
        // The direction of the edge does not flip the side.
        let back = LiveRouteGeometry.labelCenter(from: CGPoint(x: 200, y: 100), to: CGPoint(x: 0, y: 100), offset: 20)
        XCTAssertEqual(back.y, 80, accuracy: 0.001)
    }

    func testLabelOfAVerticalEdgeSitsToTheRightAndADiagonalOneAboveTheLine() {
        let vertical = LiveRouteGeometry.labelCenter(from: CGPoint(x: 50, y: 0), to: CGPoint(x: 50, y: 300), offset: 20)
        XCTAssertEqual(vertical.x, 70, accuracy: 0.001)
        XCTAssertEqual(vertical.y, 150, accuracy: 0.001)
        let diagonal = LiveRouteGeometry.labelCenter(from: .zero, to: CGPoint(x: 100, y: 100), offset: 20)
        // Distance 20 from the middle, perpendicular to the edge, on the upper side.
        XCTAssertEqual(hypot(diagonal.x - 50, diagonal.y - 50), 20, accuracy: 0.001)
        XCTAssertLessThan(diagonal.y, 50)
        XCTAssertEqual((diagonal.x - 50) * 1 + (diagonal.y - 50) * 1, 0, accuracy: 0.001)
    }

    func testDegenerateEdgeFallsBackToStraightAbove() {
        let point = CGPoint(x: 30, y: 40)
        XCTAssertEqual(LiveRouteGeometry.labelCenter(from: point, to: point, offset: 20), CGPoint(x: 30, y: 20))
    }

    // MARK: - Texts

    func testDurationRoundsMinutesAndUsesHoursFromSixty() {
        XCTAssertEqual(LiveRouteFormatting.duration(12 * 60 + 20, language: "en"), "12 min")
        XCTAssertEqual(LiveRouteFormatting.duration(12 * 60 + 40, language: "en"), "13 min")
        XCTAssertEqual(LiveRouteFormatting.duration(5, language: "en"), "1 min")
        XCTAssertEqual(LiveRouteFormatting.duration(65 * 60, language: "en"), "1 h 5 min")
        XCTAssertEqual(LiveRouteFormatting.duration(65 * 60, language: "ru"), "1 ч 5 мин")
        XCTAssertEqual(LiveRouteFormatting.duration(18 * 60, language: "ru"), "18 мин")
        XCTAssertEqual(LiveRouteFormatting.duration(120 * 60, language: "en"), "2 h")
    }

    func testSymbolsPerMode() {
        XCTAssertEqual(LiveRouteFormatting.symbol(.walk), "figure.walk")
        XCTAssertEqual(LiveRouteFormatting.symbol(.transit), "bus.fill")
        XCTAssertEqual(LiveRouteFormatting.symbol(.car), "car.fill")
    }

    func testSpokenEdgeIsLocalized() throws {
        let edge = try XCTUnwrap(liveRoute(3).edges.first)
        XCTAssertEqual(LiveRouteFormatting.spokenEdge(edge, language: "ru"), "От 1 до 2: на транспорте 18 минут")
        XCTAssertEqual(
            LiveRouteFormatting.spokenEdge(edge, language: "en"), "From 1 to 2: by public transport 18 minutes")
        let long = LiveEdge(
            leg: LiveLeg(fromOrd: 1, toOrd: 2, mode: .walk, durationS: 65 * 60),
            from: .init(), to: .init(), fromNumber: 1, toNumber: 2)
        XCTAssertTrue(LiveRouteFormatting.spokenEdge(long, language: "en").contains("1 hour"))
    }

    func testSpokenPins() {
        XCTAssertEqual(LiveRouteFormatting.spokenStop(number: 2, name: "Парк", language: "ru"), "Остановка 2: Парк")
        XCTAssertEqual(LiveRouteFormatting.spokenAlternative(name: "Park", language: "en"), "Alternative: Park")
    }

    // MARK: - Choose flow

    private final class Script: @unchecked Sendable {
        private let lock = NSLock()
        private var routes: [String: @Sendable (URLRequest) -> (Int, String)] = [:]

        func set(_ key: String, _ answer: @escaping @Sendable (URLRequest) -> (Int, String)) {
            lock.lock(); defer { lock.unlock() }
            routes[key] = answer
        }

        func answer(_ request: URLRequest) -> (Int, String) {
            lock.lock(); defer { lock.unlock() }
            let key = "\(request.httpMethod ?? "GET") \(request.url?.path ?? "")"
            return routes[key]?(request) ?? (404, "{\"error\":{\"code\":\"not_found\",\"message\":\"stub\"}}")
        }
    }

    private func makeModel(_ script: Script) -> ChatModel {
        StubURLProtocol.install { request in
            let (status, body) = script.answer(request)
            return (StubURLProtocol.response(request.url!, status: status), Data(body.utf8))
        }
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r")),
            installID: "install-1", session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return ChatModel(api: client, language: { "en" })
    }

    private func liveChat(choose: @escaping @Sendable (URLRequest) -> (Int, String)) -> Script {
        let script = Script()
        script.set("POST /v1/chats") { _ in (201, "{\"id\":\"\(ChatStub.chatID)\",\"title\":null,\"locale\":\"en\"}") }
        script.set("POST /v1/chats/\(chatID)/messages") { _ in (200, ChatStub.fixture("chat-live-1")) }
        script.set("GET /v1/chats") { _ in (200, "{\"items\":[]}") }
        script.set("POST /v1/chats/\(chatID)/live-route/choose", choose)
        return script
    }

    private func waitUntil(_ what: String, timeout: TimeInterval = 5, _ condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(20)) }
        XCTAssertTrue(condition(), "timed out waiting for \(what)")
    }

    func testChoosingAnAlternativeRedrawsFromTheAnswer() async throws {
        let swapped = try {
            var route = try liveRoute(1)
            let stop = route.stops[0]
            route = LiveRoute(stops: [LiveStop(
                ord: 1, wish: stop.wish, place: stop.alternatives[0], alternatives: [stop.place, stop.alternatives[1]]
            )], legs: [])
            return String(data: try JSONEncoderForTests.encode(route), encoding: .utf8) ?? ""
        }()
        let model = makeModel(liveChat { _ in (200, swapped) })
        model.send("Chinese restaurant live1", signedIn: true)
        await waitUntil("the live route") { !model.isStreaming && model.state.liveRoute != nil }
        let first = try XCTUnwrap(model.state.liveRoute?.stops.first)
        let alternative = try XCTUnwrap(first.alternatives.first)

        model.chooseAlternative(ord: first.ord, placeID: alternative.id)
        XCTAssertTrue(model.isChoosing)
        await waitUntil("the swap") { model.state.liveRoute?.stops.first?.place.id == alternative.id }
        await waitUntil("choosing to end") { !model.isChoosing }

        let call = try XCTUnwrap(StubURLProtocol.requests.last { $0.url?.path.hasSuffix("/live-route/choose") == true })
        let body = try XCTUnwrap(JSONSerialization.jsonObject(with: call.httpBody ?? Data()) as? [String: Any])
        XCTAssertEqual(body["ord"] as? Int, 1)
        XCTAssertEqual(body["place_id"] as? String, alternative.id.uuidString.lowercased())
        XCTAssertNil(model.liveRouteError)
        XCTAssertEqual(model.state.liveRoute?.stops.first?.alternatives.count, 2)
    }

    func testRejectedChoiceKeepsTheRouteShowsAnErrorAndRereadsTheChat() async throws {
        let script = liveChat { _ in (409, "{\"error\":{\"code\":\"route_changed\",\"message\":\"gone\"}}") }
        let route = try liveRoute(1)
        let live = String(data: try JSONEncoderForTests.encode(route), encoding: .utf8) ?? "{}"
        script.set("GET /v1/chats/\(chatID)") { _ in (200, "{\"id\":\"\(ChatStub.chatID)\",\"live_route\":\(live)}") }
        let model = makeModel(script)
        model.send("Chinese restaurant live1", signedIn: true)
        await waitUntil("the live route") { !model.isStreaming && model.state.liveRoute != nil }
        let stop = try XCTUnwrap(model.state.liveRoute?.stops.first)

        model.chooseAlternative(ord: stop.ord, placeID: stop.alternatives[0].id)
        await waitUntil("the error") { model.liveRouteError == .outdated }
        await waitUntil("choosing to end") { !model.isChoosing }
        XCTAssertEqual(model.state.liveRoute, route)
        let rereads = StubURLProtocol.requests.filter {
            $0.httpMethod == "GET" && $0.url?.path == "/v1/chats/\(chatID)"
        }
        XCTAssertFalse(rereads.isEmpty)
        model.dismissLiveRouteError()
        XCTAssertNil(model.liveRouteError)
    }

    func testChatBusyKeepsTheRouteAndAsksToTryAgain() async throws {
        let model = makeModel(liveChat { _ in (409, "{\"error\":{\"code\":\"chat_busy\",\"message\":\"busy\"}}") })
        model.send("Chinese restaurant live1", signedIn: true)
        await waitUntil("the live route") { !model.isStreaming && model.state.liveRoute != nil }
        let stop = try XCTUnwrap(model.state.liveRoute?.stops.first)
        let before = model.state.liveRoute
        model.chooseAlternative(ord: stop.ord, placeID: stop.alternatives[0].id)
        await waitUntil("the busy toast") { model.liveRouteError == .busy }
        await waitUntil("choosing to end") { !model.isChoosing }
        XCTAssertEqual(model.state.liveRoute, before)
        let rereads = StubURLProtocol.requests.filter {
            $0.httpMethod == "GET" && $0.url?.path == "/v1/chats/\(chatID)"
        }
        XCTAssertTrue(rereads.isEmpty, "no re-read: the route is fine")
    }

    func testAStopWithoutALegIsDrawnWithoutAnEdge() throws {
        let json = """
        {"stops":[{"ord":1,"place":{"id":"1a000000-0000-4000-8000-000000000001","name":"A","lat":43.2,"lon":76.9}},
                  {"ord":2,"place":{"id":"1a000000-0000-4000-8000-000000000002","name":"B","lat":43.3,"lon":76.9}},
                  {"ord":3,"place":{"id":"1a000000-0000-4000-8000-000000000003","name":"C","lat":43.4,"lon":76.9}}],
         "legs":[{"from_ord":2,"to_ord":3,"mode":"walk","duration_s":600,"distance_m":800}]}
        """
        let route = try JSONDecoder().decode(LiveRoute.self, from: Data(json.utf8))
        XCTAssertEqual(route.stops.count, 3)
        XCTAssertEqual(route.edges.map(\.id), ["2-3"], "no leg 1→2: no edge, no crash")
        XCTAssertEqual(route.edges.first?.fromNumber, 2)
    }

    func testEmptyRouteClearsTheLiveRoute() throws {
        var state = ChatState()
        state.apply(.liveRoute(try liveRoute(3)))
        XCTAssertNotNil(state.liveRoute)
        let empty = try JSONDecoder().decode(LiveRoute.self, from: Data("{\"stops\":[],\"legs\":[]}".utf8))
        let event = ChatEvent(SSEEvent(event: "live_route", data: "{\"stops\":[],\"legs\":[]}", id: nil))
        XCTAssertEqual(event, .liveRoute(empty))
        state.apply(event)
        XCTAssertNil(state.liveRoute, "all wishes removed")
        XCTAssertEqual(state.liveVersion, 2)
    }

    func testNetworkFailureIsAToastAndDoesNotTouchTheRoute() async throws {
        let model = makeModel(liveChat { _ in (500, "") })
        model.send("Chinese restaurant live1", signedIn: true)
        await waitUntil("the live route") { !model.isStreaming && model.state.liveRoute != nil }
        let stop = try XCTUnwrap(model.state.liveRoute?.stops.first)
        let before = model.state.liveRoute
        model.chooseAlternative(ord: stop.ord, placeID: stop.alternatives[0].id)
        await waitUntil("the error") { model.liveRouteError == .network }
        XCTAssertEqual(model.state.liveRoute, before)
    }

    func testRouteReadyAfterTheLiveRouteHidesIt() async throws {
        let script = liveChat { _ in (404, "") }
        script.set("POST /v1/chats/\(chatID)/messages") { request in
            let text = String(data: request.httpBody ?? Data(), encoding: .utf8) ?? ""
            return (200, ChatStub.fixture(text.contains("live4") ? "chat-live-4" : "chat-live-1"))
        }
        let model = makeModel(script)
        model.send("Chinese restaurant live1", signedIn: true)
        await waitUntil("the live route") { !model.isStreaming && model.state.liveRoute != nil }
        model.send("build the route live4", signedIn: true)
        await waitUntil("route ready") { model.state.isConverged }
        XCTAssertNil(model.state.liveRoute)
    }
}

/// Re-encodes the decoded route into the wire shape (tests only).
private enum JSONEncoderForTests {
    static func encode(_ route: LiveRoute) throws -> Data {
        func place(_ place: LivePlace) -> [String: Any] {
            ["id": place.id.uuidString.lowercased(), "name": place.name, "category": place.category ?? NSNull(),
             "lat": place.lat, "lon": place.lon]
        }
        let stops = route.stops.map { stop -> [String: Any] in
            [
                "ord": stop.ord, "wish": stop.wish ?? NSNull(), "place": place(stop.place),
                "alternatives": stop.alternatives.map(place),
            ]
        }
        let legs = route.legs.map { leg -> [String: Any] in
            ["from_ord": leg.fromOrd, "to_ord": leg.toOrd, "mode": leg.mode?.rawValue ?? NSNull(),
             "duration_s": leg.durationS,
             "distance_m": leg.distanceM ?? NSNull()]
        }
        return try JSONSerialization.data(withJSONObject: ["stops": stops, "legs": legs])
    }
}
