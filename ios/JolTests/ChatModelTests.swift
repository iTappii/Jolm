@testable import Jol
import XCTest

/// Ш-32: `ChatModel` against a scripted API (`StubURLProtocol`): which endpoint a guest / a signed-in user talks to,
/// retries after `chat_busy` and stream errors, reopening a saved chat and deciding a proposal.
@MainActor
// swiftlint:disable:next type_body_length
final class ChatModelTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let chatID = ChatStub.chatID
    private let tripID = ChatStub.tripID

    /// Answers by `"METHOD /path"`; unknown requests get 404. A route may be replaced while the test runs.
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

    private func install(_ script: Script) {
        StubURLProtocol.install { request in
            let (status, body) = script.answer(request)
            return (StubURLProtocol.response(request.url!, status: status), Data(body.utf8))
        }
    }

    private func makeModel(signedIn: Bool = true) -> ChatModel {
        let tokens = MemoryTokenStore(signedIn ? SessionTokens(accessToken: "a", refreshToken: "r") : nil)
        let client = APIClient(
            baseURL: .success(base), tokens: tokens, installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return ChatModel(api: client, language: { "ru" })
    }

    private func requests(_ method: String, _ path: String) -> [URLRequest] {
        StubURLProtocol.requests.filter { $0.httpMethod == method && $0.url?.path == path }
    }

    private func waitUntil(_ what: String, timeout: TimeInterval = 5, _ condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(20)) }
        XCTAssertTrue(condition(), "timed out waiting for \(what)")
    }

    private func scriptedTripChat() -> Script {
        let script = Script()
        script.set("POST /v1/chats") { _ in (201, "{\"id\":\"\(ChatStub.chatID)\",\"title\":null,\"locale\":\"ru\"}") }
        script.set("POST /v1/chats/\(chatID)/messages") { _ in (200, ChatStub.fixture("chat-trip")) }
        script.set("GET /v1/chats") { _ in (200, "{\"items\":[]}") }
        script.set("GET /v1/trips/\(tripID)") { _ in (200, Self.tripJSON()) }
        return script
    }

    private nonisolated static func tripJSON() -> String {
        func item(_ id: String, _ pid: String, _ name: String) -> String {
            "{\"id\":\"\(id)\",\"kind\":\"activity\",\"starts_at\":\"2026-12-05T09:30:00+05:00\","
                + "\"place\":{\"id\":\"\(pid)\",\"name\":\"\(name)\",\"category\":\"museum\","
                + "\"lat\":43.2,\"lon\":76.9}}"
        }
        let first = item("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01", UITestSupport.centerPlaceID, "Fixture Museum")
        let second = item("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02", UITestSupport.secondPlaceID, "Fixture Cafe")
        return "{\"id\":\"\(ChatStub.tripID)\",\"version\":1,\"start_date\":\"2026-12-05\",\"end_date\":\"2026-12-05\","
            + "\"budget_kzt\":900000,\"total_cost_kzt\":1000,\"days\":[{\"date\":\"2026-12-05\","
            + "\"items\":[\(first),\(second)]}]}"
    }

    // MARK: - Sending

    func testSignedInUserWritesToASavedChatAndTheStreamBuildsEverything() async throws {
        install(scriptedTripChat())
        let model = makeModel()
        model.send("  Plan 3 days  ", signedIn: true)
        await waitUntil("the stream to finish") { !model.isStreaming && model.state.route != nil }

        let create = try XCTUnwrap(requests("POST", "/v1/chats").first)
        XCTAssertEqual(create.value(forHTTPHeaderField: "Authorization"), "Bearer a")
        XCTAssertEqual(String(data: create.httpBody ?? Data(), encoding: .utf8), "{\"locale\":\"ru\"}")
        let message = try XCTUnwrap(requests("POST", "/v1/chats/\(chatID)/messages").first)
        XCTAssertEqual(String(data: message.httpBody ?? Data(), encoding: .utf8), "{\"content\":\"Plan 3 days\"}")
        XCTAssertEqual(message.value(forHTTPHeaderField: "Accept"), "text/event-stream")

        XCTAssertEqual(model.chatID, UUID(uuidString: chatID))
        XCTAssertEqual(model.state.graph.count, 3)
        XCTAssertTrue(model.state.isConverged)
        XCTAssertEqual(model.state.messages.first?.text, "Plan 3 days")
        XCTAssertEqual(model.state.messages.last?.text.hasSuffix("Your route is ready."), true)
        await waitUntil("the trip to load") { model.trip != .idle && model.trip != .loading }
        guard case .loaded(let trip) = model.trip else { return XCTFail("trip not loaded") }
        XCTAssertEqual(trip.days.first?.items.count, 2)
        XCTAssertEqual(model.state.mapPlaces.count, 2, "the plan's stops are on the map")
        await waitUntil("the recent list to refresh") { !self.requests("GET", "/v1/chats").isEmpty }
    }

    func testGuestTalksToTheGuestEndpointWithClientSideHistory() async throws {
        let script = Script()
        script.set("POST /v1/chat/guest") { _ in (200, ChatStub.fixture("chat-guest")) }
        install(script)
        let model = makeModel(signedIn: false)
        model.send("Where is the museum?", signedIn: false)
        await waitUntil("the first answer") { !model.isStreaming }
        model.send("And a cafe?", signedIn: false)
        await waitUntil("the second answer") { !model.isStreaming && model.state.messages.count == 4 }

        let calls = requests("POST", "/v1/chat/guest")
        XCTAssertEqual(calls.count, 2)
        XCTAssertNil(calls[0].value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(calls[0].value(forHTTPHeaderField: "X-Install-ID"), "install-1")
        let body = try XCTUnwrap(JSONSerialization.jsonObject(with: calls[1].httpBody ?? Data()) as? [String: Any])
        let history = try XCTUnwrap(body["messages"] as? [[String: String]])
        XCTAssertEqual(history.map { $0["role"] }, ["user", "assistant", "user"])
        XCTAssertEqual(history.last?["content"], "And a cafe?")
        XCTAssertEqual(body["locale"] as? String, "ru")
        XCTAssertNil(model.chatID, "a guest chat is never saved")
        XCTAssertTrue(requests("POST", "/v1/chats").isEmpty)
        XCTAssertEqual(model.state.mapPlaces.count, 1)
        XCTAssertTrue(model.isGuestTranscript)
    }

    func testChatBusyShowsAFailureAndRetrySendsTheSameTextWithoutANewBubble() async throws {
        let script = scriptedTripChat()
        script.set("POST /v1/chats/\(chatID)/messages") { _ in
            (409, "{\"error\":{\"code\":\"chat_busy\",\"message\":\"busy\"}}")
        }
        install(script)
        let model = makeModel()
        model.send("Plan 3 days", signedIn: true)
        await waitUntil("chat_busy") { model.state.failure == .busy }
        XCTAssertFalse(model.isStreaming)
        XCTAssertEqual(model.state.messages.count, 1)

        script.set("POST /v1/chats/\(chatID)/messages") { _ in (200, ChatStub.fixture("chat-trip")) }
        model.retry()
        await waitUntil("the retry to finish") { model.state.isConverged && !model.isStreaming }
        XCTAssertNil(model.state.failure)
        XCTAssertEqual(model.state.messages.filter { $0.role == .user }.count, 1)
        XCTAssertEqual(requests("POST", "/v1/chats").count, 1, "the chat is created once")
        XCTAssertEqual(requests("POST", "/v1/chats/\(chatID)/messages").count, 2)
    }

    func testChatFullOffersNoRetryAndRateLimitCarriesRetryAfter() async {
        let script = scriptedTripChat()
        script.set("POST /v1/chats/\(chatID)/messages") { _ in
            (409, "{\"error\":{\"code\":\"chat_full\",\"message\":\"full\"}}")
        }
        install(script)
        let model = makeModel()
        model.send("Hi", signedIn: true)
        await waitUntil("chat_full") { model.state.failure == .full }
        let before = StubURLProtocol.requests.count
        model.retry()
        XCTAssertEqual(StubURLProtocol.requests.count, before, "a full chat cannot be retried")

        let limited = scriptedTripChat()
        limited.set("POST /v1/chats/\(chatID)/messages") { _ in
            (429, "{\"error\":{\"code\":\"rate_limited\",\"message\":\"slow\"}}")
        }
        install(limited)
        let second = makeModel()
        second.send("Hi", signedIn: true)
        await waitUntil("rate limit") { second.state.failure != nil }
        guard case .rateLimited? = second.state.failure else { return XCTFail("expected a rate limit failure") }
    }

    func testStreamErrorKeepsThePartialTextAndRetryDropsIt() async {
        let script = scriptedTripChat()
        script.set("POST /v1/chats/\(chatID)/messages") { _ in (200, ChatStub.fixture("chat-error")) }
        install(script)
        let model = makeModel()
        model.send("Hello", signedIn: true)
        await waitUntil("the error event") { model.state.failure != nil }
        XCTAssertEqual(model.state.messages.last?.text, "Let me think")
        XCTAssertFalse(model.isStreaming)

        script.set("POST /v1/chats/\(chatID)/messages") { _ in (200, ChatStub.fixture("chat-trip")) }
        model.retry()
        await waitUntil("a good answer") { model.state.isConverged && !model.isStreaming }
        XCTAssertFalse(model.state.messages.contains { $0.text == "Let me think" })
    }

    // MARK: - Reopening and proposals

    private func oldChatScript(status: @escaping @Sendable () -> String) -> Script {
        let proposal = ChatStub.proposalID
        let script = Script()
        script.set("GET /v1/chats/\(chatID)") { _ in
            (200, "{\"id\":\"\(ChatStub.chatID)\",\"title\":\"Weather\",\"messages\":["
                + "{\"id\":1,\"role\":\"assistant\",\"content\":\"Move the museum?\",\"finish\":\"stop\","
                + "\"proposal_id\":\"\(proposal)\"}],\"brief\":null,\"graph_nodes\":["
                + "{\"ord\":1,\"kind\":\"fact\",\"text\":\"3 days\"}]}")
        }
        script.set("GET /v1/trips") { _ in
            (200, "{\"items\":[{\"id\":\"\(ChatStub.tripID)\",\"chat_id\":\"\(ChatStub.chatID)\"}]}")
        }
        script.set("GET /v1/trips/\(tripID)") { _ in (200, Self.tripJSON()) }
        script.set("GET /v1/trips/\(tripID)/proposals") { _ in
            (200, "{\"items\":[{\"id\":\"\(proposal)\",\"status\":\"\(status())\"}]}")
        }
        return script
    }

    func testReopeningRebuildsGraphConvergesAndRestoresPinsFromTheTrip() async {
        install(oldChatScript { "pending" })
        let model = makeModel()
        model.open(UUID(uuidString: chatID)!)
        XCTAssertTrue(model.isOpening)
        await waitUntil("the chat to open") { !model.isOpening && model.state.mapPlaces.count == 2 }
        XCTAssertEqual(model.state.graph.map(\.text), ["3 days"])
        XCTAssertTrue(model.state.isConverged, "the chat has a trip, so its graph is converged")
        XCTAssertEqual(model.state.proposals[UUID(uuidString: ChatStub.proposalID)!], .pending)
        XCTAssertEqual(model.tripID, UUID(uuidString: tripID))
    }

    func testOlderTripReopensFromTheNextPageAndRestoresItsDayCount() async {
        let script = oldChatScript { "pending" }
        let cursor = "2026-11-20T10:00:00+05:00"
        let item = "{\"id\":\"\(ChatStub.oldTripID)\",\"chat_id\":null,\"updated_at\":\"\(cursor)\"}"
        let firstPage = Array(repeating: item, count: 100).joined(separator: ",")
        script.set("GET /v1/trips") { request in
            let query = request.url.flatMap { URLComponents(url: $0, resolvingAgainstBaseURL: false)?.queryItems }
            if query?.first(where: { $0.name == "before" })?.value == cursor,
               request.url?.absoluteString.contains("%2B") == true {
                return (200, "{\"items\":[{\"id\":\"\(ChatStub.tripID)\",\"chat_id\":\"\(ChatStub.chatID)\"}]}")
            }
            return (200, "{\"items\":[\(firstPage)]}")
        }
        install(script)
        let model = makeModel()
        model.open(UUID(uuidString: chatID)!)
        await waitUntil("day count and pins from the saved trip") { model.state.route?.days == 1 }
        XCTAssertEqual(model.state.mapPlaces.count, 2)
    }

    func testAcceptingAProposalCallsTheServerAndReloadsTheChat() async {
        let status = StatusBox()
        let script = oldChatScript { status.value }
        script.set("POST /v1/proposals/\(ChatStub.proposalID)/accept") { _ in
            status.value = "accepted"
            return (200, "{\"proposal\":{\"id\":\"\(ChatStub.proposalID)\",\"status\":\"accepted\"}}")
        }
        install(script)
        let model = makeModel()
        model.open(UUID(uuidString: chatID)!)
        await waitUntil("the chat to open") { !model.isOpening && model.state.messages.count == 1 }
        let id = UUID(uuidString: ChatStub.proposalID)!
        let loadsBefore = requests("GET", "/v1/chats/\(chatID)").count

        model.decide(id, accept: true)
        XCTAssertEqual(model.state.proposals[id], .working)
        await waitUntil("the proposal to be accepted") { model.state.proposals[id] == .accepted }
        await waitUntil("the chat to reload") { self.requests("GET", "/v1/chats/\(self.chatID)").count > loadsBefore }
        XCTAssertEqual(requests("POST", "/v1/proposals/\(ChatStub.proposalID)/accept").count, 1)
        XCTAssertEqual(model.state.proposals[id], .accepted, "the status comes back from the server after the reload")
    }

    func testDecliningAndAStaleProposal() async {
        let status = StatusBox()
        let script = oldChatScript { status.value }
        script.set("POST /v1/proposals/\(ChatStub.proposalID)/decline") { _ in
            status.value = "declined"
            return (200, "{\"id\":\"\(ChatStub.proposalID)\",\"status\":\"declined\"}")
        }
        install(script)
        let model = makeModel()
        model.open(UUID(uuidString: chatID)!)
        await waitUntil("the chat to open") { !model.isOpening && model.state.messages.count == 1 }
        let id = UUID(uuidString: ChatStub.proposalID)!
        model.decide(id, accept: false)
        await waitUntil("declined") { model.state.proposals[id] == .declined }

        script.set("POST /v1/proposals/\(ChatStub.proposalID)/accept") { _ in
            (409, "{\"error\":{\"code\":\"proposal_stale\",\"message\":\"old\"}}")
        }
        script.set("GET /v1/trips/\(tripID)/proposals") { _ in
            (200, "{\"items\":[{\"id\":\"\(ChatStub.proposalID)\",\"status\":\"expired\"}]}")
        }
        model.decide(id, accept: true)
        await waitUntil("expired") { model.state.proposals[id] == .expired }
    }

    func testNewChatDropsTheConversation() async {
        install(scriptedTripChat())
        let model = makeModel()
        model.send("Plan 3 days", signedIn: true)
        await waitUntil("a converged chat") { model.state.isConverged && !model.isStreaming }
        model.newChat()
        XCTAssertTrue(model.state.isEmpty)
        XCTAssertNil(model.chatID)
        XCTAssertNil(model.tripID)
        XCTAssertTrue(model.state.mapPlaces.isEmpty)
    }
}

/// A value the scripted server changes while the test runs.
private final class StatusBox: @unchecked Sendable {
    private let lock = NSLock()
    private var stored = "pending"

    var value: String {
        get { lock.lock(); defer { lock.unlock() }; return stored }
        set { lock.lock(); defer { lock.unlock() }; stored = newValue }
    }
}
