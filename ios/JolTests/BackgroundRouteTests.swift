@testable import Jol
import XCTest

/// Ш-64: the chat does not wait for the map. `live_route_status` decoding and reduction, the events stream
/// (`GET /v1/chats/{id}/events`) with reconnect and backoff, idempotent snapshots, sending while a route is building.
@MainActor
final class BackgroundRouteTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let chatID = ChatStub.chatID

    private func sse(_ name: String, _ data: String) -> ChatEvent {
        ChatEvent(SSEEvent(event: name, data: data, id: nil))
    }

    private func liveRouteJSON() throws -> String {
        let chunk = try XCTUnwrap(ChatStub.fixture("chat-live-2").components(separatedBy: "\n\n")
            .first { $0.hasPrefix("event: live_route") })
        return String(try XCTUnwrap(chunk.components(separatedBy: "data: ").last))
    }

    private func liveRoute() throws -> LiveRoute {
        try JSONDecoder().decode(LiveRoute.self, from: Data(try liveRouteJSON().utf8))
    }

    private final class Delays: @unchecked Sendable {
        private let lock = NSLock()
        private var values: [Duration] = []
        func add(_ value: Duration) { lock.lock(); values.append(value); lock.unlock() }
        var all: [Duration] { lock.lock(); defer { lock.unlock() }; return values }
    }

    private final class Counter: @unchecked Sendable {
        private let lock = NSLock()
        private var count = 0
        func next() -> Int { lock.lock(); defer { lock.unlock() }; count += 1; return count }
    }

    private func makeModel(delays: Delays = Delays()) -> ChatModel {
        let tokens = MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r"))
        let client = APIClient(
            baseURL: .success(base), tokens: tokens, installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return ChatModel(api: client, language: { "en" }, sleeper: { delay in
            delays.add(delay)
            try await Task.sleep(for: .milliseconds(5))
        })
    }

    private func waitUntil(_ what: String, timeout: TimeInterval = 5, _ condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
        XCTAssertTrue(condition(), "timed out waiting for \(what)")
    }

    private func requests(_ method: String, _ path: String) -> [URLRequest] {
        StubURLProtocol.requests.filter { $0.httpMethod == method && $0.url?.path == path }
    }

    private nonisolated static func status(_ state: String) -> String {
        "event: live_route_status\ndata: {\"state\": \"\(state)\"}\n\n"
    }

    // MARK: - Decoding and reducer

    func testStatusEventDecodesAndUnknownStatesAreIgnored() {
        XCTAssertEqual(sse("live_route_status", "{\"state\":\"building\"}"), .liveRouteStatus(.building))
        XCTAssertEqual(sse("live_route_status", "{\"state\":\"ready\"}"), .liveRouteStatus(.ready))
        XCTAssertEqual(sse("live_route_status", "{\"state\":\"failed\"}"), .liveRouteStatus(.failed))
        XCTAssertEqual(sse("live_route_status", "{\"state\":\"melting\"}"), .unknown("live_route_status"))
        XCTAssertEqual(sse("live_route_status", "nope"), .unknown("live_route_status"))
    }

    func testEmptySnapshotRouteDecodes() {
        guard case .liveRoute(let route) = sse("live_route", "{\"stops\":[],\"legs\":[]}") else {
            return XCTFail("not a live route")
        }
        XCTAssertTrue(route.isEmpty)
    }

    func testReducerTracksBuildingAndRouteReadyEndsIt() {
        var state = ChatState()
        state.apply(.liveRouteStatus(.building))
        XCTAssertTrue(state.isBuildingRoute)
        state.apply(.liveRouteStatus(.ready))
        XCTAssertFalse(state.isBuildingRoute)
        state.apply(.liveRouteStatus(.building))
        state.apply(.routeReady(RouteReady(tripID: UUID())))
        XCTAssertFalse(state.isBuildingRoute)
    }

    func testSnapshotOfAnUnchangedRouteChangesNothing() throws {
        let model = makeModel()
        let route = try liveRoute()
        model.applyBackground(.liveRoute(route))
        let version = model.state.liveVersion
        XCTAssertEqual(model.backgroundLiveVersion, version, "a change from the events stream is announced")
        model.applyBackground(.liveRoute(route))
        model.applyBackground(.liveRouteStatus(.ready))
        XCTAssertEqual(model.state.liveVersion, version, "no camera jump")
        XCTAssertEqual(model.backgroundLiveVersion, version)
    }

    func testStoredLiveRouteDoesNotBringPinsBackOverAFinishedPlan() throws {
        let model = makeModel()
        model.applyBackground(.liveRoute(try liveRoute()))
        model.applyBackground(.liveRouteStatus(.building))
        XCTAssertTrue(model.isBuildingRoute)
        XCTAssertNotNil(model.state.liveRoute)
    }

    func testFailureFlagIsSetAndDismissed() {
        let model = makeModel()
        model.applyBackground(.liveRouteStatus(.failed))
        XCTAssertTrue(model.routeBuildFailed)
        model.dismissRouteBuildFailure()
        XCTAssertFalse(model.routeBuildFailed)
        model.applyBackground(.liveRouteStatus(.failed))
        model.applyBackground(.liveRouteStatus(.ready))
        XCTAssertFalse(model.routeBuildFailed)
    }

    func testBackoffStepsCapAtTenSeconds() {
        let steps = (0..<6).map { ChatModel.backoff(attempt: $0) }
        XCTAssertEqual(steps, [.seconds(1), .seconds(2), .seconds(5), .seconds(10), .seconds(10), .seconds(10)])
        XCTAssertEqual(ChatModel.backoff(attempt: -3), .seconds(1))
    }

    // MARK: - The stream

    private func installChat(events: @escaping @Sendable (Int) -> (Int, String)) {
        let counter = Counter()
        StubURLProtocol.install { request in
            let key = "\(request.httpMethod ?? "GET") \(request.url?.path ?? "")"
            let url = request.url!
            switch key {
            case "POST /v1/chats":
                return (StubURLProtocol.response(url, status: 201),
                        Data("{\"id\":\"\(ChatStub.chatID)\",\"title\":null,\"locale\":\"en\"}".utf8))
            case "POST /v1/chats/\(ChatStub.chatID)/messages":
                let body = "event: brief_updated\ndata: {\"brief\":{},\"changed\":[]}\n\n"
                    + "event: live_route_status\ndata: {\"state\":\"building\"}\n\n"
                    + "event: text_delta\ndata: {\"text\":\"Sure.\"}\n\n"
                    + "event: done\ndata: {}\n\n"
                return (StubURLProtocol.response(url), Data(body.utf8))
            case "GET /v1/chats/\(ChatStub.chatID)/events":
                let (status, body) = events(counter.next())
                return (StubURLProtocol.response(url, status: status), Data(body.utf8))
            default:
                return (StubURLProtocol.response(url, status: 404),
                        Data("{\"error\":{\"code\":\"not_found\",\"message\":\"stub\"}}".utf8))
            }
        }
    }

    func testEventsStreamAppliesTheSnapshotThenTheFinishedBuildAndReconnectsAfterAClose() async throws {
        let route = try liveRoute()
        let routeJSON = try liveRouteJSON()
        installChat { attempt in
            let first = "event: live_route\ndata: {\"stops\":[],\"legs\":[]}\n\n" + Self.status("building")
            let later = "event: live_route\ndata: \(routeJSON)\n\n" + Self.status("ready")
            return (200, attempt == 1 ? first : later)
        }
        let delays = Delays()
        let model = makeModel(delays: delays)
        model.setEventsEnabled(true)
        model.send("Chinese food", signedIn: true)
        await waitUntil("the text to finish") { !model.isStreaming && model.chatID != nil }
        await waitUntil("the route from the events stream") {
            model.state.liveRoute == route && !model.isBuildingRoute
        }

        let events = requests("GET", "/v1/chats/\(chatID)/events")
        XCTAssertEqual(events.first?.value(forHTTPHeaderField: "Authorization"), "Bearer a")
        XCTAssertEqual(events.first?.value(forHTTPHeaderField: "Accept"), "text/event-stream")
        await waitUntil("a reconnect after the close") { delays.all.count >= 2 }
        XCTAssertEqual(delays.all.prefix(2), [.seconds(1), .seconds(1)], "events reset the backoff")
        XCTAssertEqual(model.state.liveVersion, 1, "the repeated snapshot did not move the camera")
        model.setEventsEnabled(false)
    }

    func testBackoffGrowsWhileTheServerIsDownAndStopsOnDisable() async {
        installChat { _ in (500, "{\"error\":{\"code\":\"boom\",\"message\":\"down\"}}") }
        let delays = Delays()
        let model = makeModel(delays: delays)
        model.setEventsEnabled(true)
        model.send("hello", signedIn: true)
        await waitUntil("five attempts") { delays.all.count >= 5 }
        XCTAssertEqual(delays.all.prefix(5), [.seconds(1), .seconds(2), .seconds(5), .seconds(10), .seconds(10)])

        model.setEventsEnabled(false)
        XCTAssertFalse(model.isEventsRunning)
        try? await Task.sleep(for: .milliseconds(100))
        let settled = requests("GET", "/v1/chats/\(chatID)/events").count
        try? await Task.sleep(for: .milliseconds(150))
        XCTAssertEqual(requests("GET", "/v1/chats/\(chatID)/events").count, settled, "no requests after stopping")
    }

    func testChatSwitchStopsTheStreamAndAGuestHasNone() async {
        installChat { _ in (200, ": keepalive\n\n") }
        let model = makeModel()
        model.setEventsEnabled(true)
        XCTAssertFalse(model.isEventsRunning, "no chat, no stream")
        model.send("hello", signedIn: true)
        await waitUntil("the stream") { model.isEventsRunning }
        model.newChat()
        XCTAssertFalse(model.isEventsRunning)
        XCTAssertFalse(model.isBuildingRoute)
    }

    func testSendingIsAllowedWhileTheRouteIsBuilding() async {
        installChat { _ in (200, ": keepalive\n\n") }
        let model = makeModel()
        model.send("first wish", signedIn: true)
        await waitUntil("the first answer") { !model.isStreaming && model.state.messages.count == 2 }
        model.applyBackground(.liveRouteStatus(.building))
        XCTAssertTrue(model.isBuildingRoute)
        XCTAssertFalse(model.isStreaming, "the text is done; the input is free")
        model.send("second wish", signedIn: true)
        await waitUntil("the second message") { self.requests("POST", "/v1/chats/\(self.chatID)/messages").count == 2 }
    }
}
