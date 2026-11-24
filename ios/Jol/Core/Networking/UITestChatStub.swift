#if DEBUG
import Foundation

/// Stub of the chat, trip and proposal endpoints for UI tests (`-JolStubAPI`). Streams are RECORDED SSE files
/// (`Resources/Fixtures/chat-*.sse`, written with the server's own `format_event`) replayed event by event with a
/// short pause, so the UI sees text, graph nodes and places arrive over time.
///
/// Scenario switches (by the text of the user's message): "busy" → the first attempt answers 409 `chat_busy`,
/// "full" → 409 `chat_full`, "boom" → the first attempt streams an `error` event; the retry then succeeds;
/// "#dlg0" … "#dlg7" → the turns of a recorded dialog for the answer chain (Ш-32b): a question, then the answers
/// days → budget → lodging → a wish → a changed budget → `route_ready`;
/// "live1" … "live4" (also "#live1" / "£live1": the simulator keyboard may type either) → the turns of a recorded
/// live-route dialog (Ш-54): a Chinese place with two alternatives, a second stop with a transit leg, a third with a
/// car leg, then `route_ready`. `POST /v1/chats/{id}/live-route/choose` swaps a stop for an alternative; the choice
/// is kept for the later turns, as the server does.
enum ChatStub {
    static let chatID = "66666666-6666-4666-8666-666666666666"
    static let oldChatID = "55555555-5555-4555-8555-555555555555"
    static let tripID = "44444444-4444-4444-8444-444444444444"
    static let oldTripID = "77777777-7777-4777-8777-777777777777"
    static let proposalID = "88888888-8888-4888-8888-888888888888"
    static let chunkDelay: TimeInterval = 0.12

    private static let lock = NSLock()
    private nonisolated(unsafe) static var created = false
    private nonisolated(unsafe) static var sent: [String] = []
    private nonisolated(unsafe) static var tripBuilt = false
    private nonisolated(unsafe) static var failedOnce: Set<String> = []
    private nonisolated(unsafe) static var proposalStatus = "pending"
    private nonisolated(unsafe) static var liveTurn = 0
    /// Ш-62: the owner's intercity scenario (`chat-icity-N`) instead of the Almaty one (`chat-live-N`).
    private nonisolated(unsafe) static var intercity = false
    /// Ш-64: the live route is built "in the background": after a live turn it reaches the events stream a moment
    /// later (`liveReadyAt`); `publishedTurn` is the turn whose route the events stream has delivered.
    private nonisolated(unsafe) static var liveReadyAt: Date?
    private nonisolated(unsafe) static var publishedTurn = 0
    /// ~1.6 s like a quick server; `-JolStubBuildDelay <seconds>` stretches it so a UI test can look at the indicator.
    static var buildDelay: TimeInterval {
        let args = ProcessInfo.processInfo.arguments
        guard let index = args.firstIndex(of: "-JolStubBuildDelay"), index + 1 < args.count,
              let seconds = TimeInterval(args[index + 1]) else { return 1.6 }
        return seconds
    }
    /// Stop `ord` → id of the alternative the tester chose for it.
    private nonisolated(unsafe) static var liveChoices: [Int: String] = [:]

    /// The place chosen for a live-route stop (an alternative the person picked), if any.
    static func liveChoice(ord: Int) -> String? { liveChoices[ord] }

    /// `-JolDemo`: plain phrases instead of the `live1`…`live4` tags.
    private static func demoTurn(_ lowered: String) -> Int? {
        guard UITestSupport.isDemo else { return nil }

        if lowered.contains("chinese") { return 1 }
        if lowered.contains("president") { return 2 }
        if lowered.contains("bazaar") { return 3 }
        if lowered.contains("build") || lowered.contains("route") || lowered.contains("ready") { return 4 }
        return nil
    }

    static func handles(_ path: String) -> Bool {
        path.hasPrefix("/v1/chat") || path.hasPrefix("/v1/trips") || path.hasPrefix("/v1/proposals")
    }

    static func fixture(_ name: String) -> String {
        guard let url = Bundle(for: FixtureURLProtocol.self).url(forResource: name, withExtension: "sse"),
              let text = try? String(contentsOf: url, encoding: .utf8) else { return "" }
        return text
    }

    struct Answer {
        var status = 200
        var headers = ["Content-Type": "application/json"]
        var body = ""
        /// Event chunks to replay one by one (SSE); empty for a plain body.
        var chunks: [String] = []
        /// `GET /v1/chats/{id}/events` (Ш-64): a long-lived stream driven by `eventsStep`.
        var isEvents = false
    }

    static func answer(method: String, path: String, signedIn: Bool, body: [String: Any]) -> Answer {
        lock.lock(); defer { lock.unlock() }
        if path == "/v1/chat/guest" { return stream("chat-guest") }
        guard signedIn else { return error(401, "unauthorized", "Sign in") }
        switch (method, path) {
        case ("POST", "/v1/chats"):
            created = true
            return Answer(status: 201, body: chatHeader(chatID, title: "null"))
        case ("GET", "/v1/chats"):
            return Answer(body: "{\"items\":[\(created ? summary(chatID) + "," : "")\(summary(oldChatID))]}")
        case ("GET", "/v1/chats/\(oldChatID)"):
            return Answer(body: oldChatDetail())
        case ("GET", "/v1/chats/\(chatID)"):
            return Answer(body: newChatDetail())
        case ("GET", "/v1/chats/\(chatID)/events"):
            return Answer(headers: ["Content-Type": "text/event-stream"], isEvents: true)
        case ("POST", "/v1/chats/\(chatID)/messages"):
            return message((body["content"] as? String) ?? "")
        case ("POST", "/v1/chats/\(chatID)/live-route/choose"):
            return chooseLive(ord: body["ord"] as? Int ?? 0, placeID: body["place_id"] as? String ?? "")
        default:
            return tripAnswer(method: method, path: path, body: body)
        }
    }

    private static func tripAnswer(method: String, path: String, body: [String: Any]) -> Answer {
        if method == "GET", path == "/v1/trips/\(IntercityStub.tripID)" {
            return Answer(body: IntercityStub.json(id: IntercityStub.tripID))
        }
        if let answer = TripStub.answer(method: method, path: path, body: body, tripIDs: [tripID, oldTripID]) {
            return answer
        }
        switch (method, path) {
        case ("GET", "/v1/trips"):
            let items = (tripBuilt ? [TripStub.listItem(id: tripID, chat: chatID)] : [])
                + [TripStub.listItem(id: oldTripID, chat: oldChatID)]
            return Answer(body: "{\"items\":[\(items.joined(separator: ","))]}")
        case ("GET", "/v1/trips/\(oldTripID)/proposals"):
            return Answer(body: "{\"items\":[{\"id\":\"\(proposalID)\",\"status\":\"\(proposalStatus)\"}]}")
        case ("POST", "/v1/proposals/\(proposalID)/accept"):
            proposalStatus = "accepted"
            return Answer(body: "{\"proposal\":{\"id\":\"\(proposalID)\",\"status\":\"accepted\"}}")
        case ("POST", "/v1/proposals/\(proposalID)/decline"):
            proposalStatus = "declined"
            return Answer(body: "{\"id\":\"\(proposalID)\",\"status\":\"declined\"}")
        default:
            return error(404, "not_found", "stub")
        }
    }

    // MARK: - Streams

    private static func message(_ text: String) -> Answer {
        let lowered = text.lowercased()
        if lowered.contains("budget") {
            return error(429, "llm_budget_exceeded", "", headers: ["Retry-After": "40000"])
        }
        if lowered.contains("full") { return error(409, "chat_full", "This chat is full.") }
        if lowered.contains("busy"), failedOnce.insert("busy").inserted { return error(409, "chat_busy", "busy") }
        if lowered.contains("boom"), failedOnce.insert("boom").inserted { return stream("chat-error") }
        // Intercity scenario (Ш-62): "icity1" … "icity5"; the demo phrases pick the same turns.
        let demoStep = UITestSupport.isDemo ? IntercityStub.demoTurn(lowered, underway: intercity) : nil
        for turn in 1...5 where lowered.contains("icity\(turn)") || demoStep == turn {
            sent.append(text)
            intercity = true
            liveTurn = turn
            if turn == 5 {
                tripBuilt = true
                publishedTurn = 0
                liveReadyAt = nil
                return stream("chat-icity-5")
            }
            liveReadyAt = Date().addingTimeInterval(buildDelay)
            return backgroundLive(stream("chat-icity-\(turn)"))
        }
        // Live route (Ш-54): "live2" replays the second turn of the recorded live dialog.
        for turn in 1...4 where lowered.contains("live\(turn)") || demoTurn(lowered) == turn {
            sent.append(text)
            intercity = false
            liveTurn = turn
            if turn == 4 {
                tripBuilt = true
                publishedTurn = 0
                liveReadyAt = nil
                return stream("chat-live-4")
            }
            liveReadyAt = Date().addingTimeInterval(buildDelay)
            return backgroundLive(stream("chat-live-\(turn)"))
        }
        // Chain dialog (Ш-32b): "#dlg3 …" replays the third turn of the recorded dialog.
        for turn in 0...7 where lowered.contains("#dlg\(turn)") {
            sent.append(text)
            return stream("chat-dlg-\(turn)")
        }
        sent.append(text)
        tripBuilt = true
        return stream("chat-trip")
    }

    /// What the events stream sends next, given the last (published turn, building) pair this connection sent.
    /// The first call is the snapshot; later ones deliver the finished build.
    static func eventsStep(last: [Int]?) -> (chunks: [String], key: [Int]) {
        lock.lock(); defer { lock.unlock() }
        if let at = liveReadyAt, Date() >= at {
            publishedTurn = liveTurn
            liveReadyAt = nil
        }
        let building = liveReadyAt != nil
        let key = [publishedTurn, building ? 1 : 0]
        guard key != last else { return ([], key) }
        let route = liveJSON(turn: publishedTurn) ?? "{\"stops\": [], \"legs\": []}"
        return (["event: live_route\ndata: \(route)\n\n", statusChunk(building ? "building" : "ready")], key)
    }

    private static func stream(_ name: String) -> Answer {
        let chunks = fixture(name).components(separatedBy: "\n\n").filter { !$0.isEmpty }
            .map { applyChoices($0) + "\n\n" }
        return Answer(headers: ["Content-Type": "text/event-stream"], chunks: chunks)
    }

    // MARK: - Live route (Ш-54)

    /// The route object of a `live_route` chunk with the tester's choices applied.
    private static func applyChoices(_ chunk: String) -> String {
        guard chunk.hasPrefix("event: live_route"), !liveChoices.isEmpty,
              let range = chunk.range(of: "data: "),
              let route = swapped(String(chunk[range.upperBound...])) else { return chunk }
        return "event: live_route\ndata: \(route)"
    }

    private static func swapped(_ json: String) -> String? {
        guard var route = (try? JSONSerialization.jsonObject(with: Data(json.utf8))) as? [String: Any],
              var stops = route["stops"] as? [[String: Any]] else { return nil }
        for index in stops.indices {
            guard let ord = stops[index]["ord"] as? Int, let wanted = liveChoices[ord],
                  var alternatives = stops[index]["alternatives"] as? [[String: Any]],
                  let place = stops[index]["place"] as? [String: Any],
                  let position = alternatives.firstIndex(where: { ($0["id"] as? String) == wanted }) else { continue }
            let chosen = alternatives[position]
            alternatives[position] = place
            stops[index]["place"] = chosen
            stops[index]["alternatives"] = alternatives
        }
        route["stops"] = stops
        guard let data = try? JSONSerialization.data(withJSONObject: route, options: [.sortedKeys]) else { return nil }
        return String(bytes: data, encoding: .utf8)
    }

    private static func liveJSON(turn: Int? = nil) -> String? {
        let liveTurn = turn ?? liveTurn
        guard liveTurn >= 1, liveTurn <= (intercity ? 4 : 3) else { return nil }
        let chunks = fixture("\(intercity ? "chat-icity" : "chat-live")-\(liveTurn)").components(separatedBy: "\n\n")
        guard let chunk = chunks.first(where: { $0.hasPrefix("event: live_route") }),
              let range = chunk.range(of: "data: ") else { return nil }
        let json = String(chunk[range.upperBound...])
        return swapped(json) ?? json
    }

    private static func chooseLive(ord: Int, placeID: String) -> Answer {
        guard let json = liveJSON(),
              let route = (try? JSONSerialization.jsonObject(with: Data(json.utf8))) as? [String: Any],
              let stops = route["stops"] as? [[String: Any]],
              let stop = stops.first(where: { ($0["ord"] as? Int) == ord }),
              let alternatives = stop["alternatives"] as? [[String: Any]],
              alternatives.contains(where: { ($0["id"] as? String) == placeID }) else {
            return error(422, "invalid_choice", "That alternative is not available.")
        }
        liveChoices[ord] = placeID
        return Answer(body: liveJSON() ?? "{}")
    }

    private static func error(_ status: Int, _ code: String, _ message: String,
                              headers: [String: String] = [:]) -> Answer {
        Answer(status: status, headers: ["Content-Type": "application/json"].merging(headers) { $1 },
               body: "{\"error\":{\"code\":\"\(code)\",\"message\":\"\(message)\"}}")
    }

    // MARK: - JSON

    private static func chatHeader(_ id: String, title: String) -> String {
        "{\"id\":\"\(id)\",\"title\":\(title),\"locale\":\"en\",\"created_at\":\"2026-11-21T10:00:00+05:00\","
            + "\"updated_at\":\"2026-11-21T10:00:00+05:00\"}"
    }

    private static func summary(_ id: String) -> String {
        if id == oldChatID {
            return "{\"id\":\"\(id)\",\"title\":\"Weather change\",\"locale\":\"en\","
                + "\"updated_at\":\"2026-11-20T10:00:00+05:00\",\"preview\":\"Plan 3 days\"}"
        }
        return "{\"id\":\"\(id)\",\"title\":null,\"locale\":\"en\",\"updated_at\":\"2026-11-21T10:00:00+05:00\","
            + "\"preview\":\"\(sent.first ?? "New chat")\"}"
    }

    private static let brief = """
    {"start_date":"2026-12-05","end_date":"2026-12-07","budget_kzt":900000,"has_accommodation":true,\
    "must_haves":["Fixture Museum"],"interests":[],"pace":null,"crowd_tolerance":null,"missing":[],"complete":true,\
    "filled_order":["start_date","end_date","budget_kzt","has_accommodation","must_haves:Fixture Museum"]}
    """

    private static func oldChatDetail() -> String {
        var messages = """
        {"id":1,"role":"user","content":"Plan 3 days in Almaty","finish":"stop","proposal_id":null},\
        {"id":2,"role":"assistant","content":"Done, your route is ready.","finish":"stop","proposal_id":null},\
        {"id":3,"role":"assistant","content":"Rain is forecast on Dec 6. Move the museum to Dec 7?",\
        "finish":"stop","proposal_id":"\(proposalID)"}
        """
        if proposalStatus == "accepted" {
            messages += ",{\"id\":4,\"role\":\"assistant\",\"content\":\"Done: the museum is now on Dec 7.\","
                + "\"finish\":\"stop\",\"proposal_id\":null}"
        }
        let nodes = "[{\"ord\":1,\"kind\":\"fact\",\"text\":\"3 days, Dec 5-7\"},"
            + "{\"ord\":2,\"kind\":\"fact\",\"text\":\"Budget 900 000 tenge\"}]"
        return String(chatHeader(oldChatID, title: "\"Weather change\"").dropLast())
            + ",\"messages\":[\(messages)],\"brief\":\(brief),\"graph_nodes\":\(nodes)}"
    }

    private static func newChatDetail() -> String {
        var messages: [String] = []
        for (index, text) in sent.enumerated() {
            messages.append("{\"id\":\(index * 2 + 1),\"role\":\"user\",\"content\":\"\(text)\",\"finish\":\"stop\","
                + "\"proposal_id\":null}")
            messages.append("{\"id\":\(index * 2 + 2),\"role\":\"assistant\",\"content\":\"Your route is ready.\","
                + "\"finish\":\"stop\",\"proposal_id\":null}")
        }
        let nodes = "[{\"ord\":1,\"kind\":\"fact\",\"text\":\"3 days, Dec 5-7\"}]"
        let live = liveJSON().map { ",\"live_route\":\($0)" } ?? ""
        return String(chatHeader(chatID, title: "null").dropLast())
            + ",\"messages\":[\(messages.joined(separator: ","))],\"brief\":\(brief),\"graph_nodes\":\(nodes)\(live)}"
    }
}

extension FixtureURLProtocol {
    /// Answers a chat / trip / proposal request; an event stream is replayed chunk by chunk.
    func startChat(path: String) {
        let signedIn = request.value(forHTTPHeaderField: "Authorization") != nil
        let answer = ChatStub.answer(
            method: request.httpMethod ?? "GET", path: path, signedIn: signedIn, body: requestBody()
        )
        let response = HTTPURLResponse(
            url: request.url ?? URL(fileURLWithPath: "/"), statusCode: answer.status, httpVersion: "HTTP/1.1",
            headerFields: answer.headers
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        if answer.isEvents {
            DispatchQueue.global().async { [self] in
                var last: [Int]?
                var quiet = 0.0
                while !stopped {
                    let step = ChatStub.eventsStep(last: last)
                    last = step.key
                    for chunk in step.chunks { client?.urlProtocol(self, didLoad: Data(chunk.utf8)) }
                    quiet = step.chunks.isEmpty ? quiet + 0.1 : 0
                    if quiet >= 15 {
                        client?.urlProtocol(self, didLoad: Data(": keepalive\n\n".utf8))
                        quiet = 0
                    }
                    Thread.sleep(forTimeInterval: 0.1)
                }
            }
            return
        }
        if answer.chunks.isEmpty {
            client?.urlProtocol(self, didLoad: Data(answer.body.utf8))
            client?.urlProtocolDidFinishLoading(self)
            return
        }
        DispatchQueue.global().async { [self] in
            for chunk in answer.chunks {
                // The plan takes a while to build: the graph stays unconverged long enough for a test to see it.
                let planPause: TimeInterval = chunk.hasPrefix("event: route_ready") ? 4 : 0
                Thread.sleep(forTimeInterval: ChatStub.chunkDelay + planPause)
                if stopped { return }
                client?.urlProtocol(self, didLoad: Data(chunk.utf8))
            }
            client?.urlProtocolDidFinishLoading(self)
        }
    }
}
#endif
