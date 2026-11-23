import Foundation

/// Calls of the chat API. Streams are raw SSE; `ChatEvent(_:)` decodes them.
struct ChatService: Sendable {
    /// Limits of `POST /v1/chat/guest` (Ш-30): 20 messages, 2000 characters each, 8000 in total.
    static let guestMaxMessages = 20
    static let guestMaxMessageChars = 2000
    static let guestMaxTotalChars = 8000

    let api: APIClient

    // MARK: - Registered chats

    func createChat(locale: String) async throws -> ChatSummary {
        try await api.send(Endpoint.post("v1/chats", json: ["locale": locale]))
    }

    func chats() async throws -> [ChatSummary] {
        let list: ChatsList = try await api.send(.get("v1/chats", query: [URLQueryItem(name: "limit", value: "50")]))
        return list.items
    }

    func chat(id: UUID) async throws -> ChatDetail {
        try await api.send(.get("v1/chats/\(Self.path(id))"))
    }

    func send(chatID: UUID, text: String) throws -> AsyncThrowingStream<SSEEvent, Error> {
        api.stream(try Endpoint.post("v1/chats/\(Self.path(chatID))/messages", json: ["content": text]))
    }

    /// `GET /v1/chats/{id}/events` (Ш-64): a long-lived stream with the live route and its build status — first a
    /// snapshot, then every change, also those of a build that finished after the answer.
    func events(chatID: UUID) -> AsyncThrowingStream<SSEEvent, Error> {
        api.stream(.get("v1/chats/\(Self.path(chatID))/events"))
    }

    /// An alternative becomes the stop (Ш-54); the answer is the whole live route again.
    func chooseLiveStop(chatID: UUID, ord: Int, placeID: UUID) async throws -> LiveRoute {
        try await api.send(Endpoint.post(
            "v1/chats/\(Self.path(chatID))/live-route/choose",
            json: ChooseBody(ord: ord, placeID: placeID.uuidString.lowercased())
        ))
    }

    // MARK: - Guest

    struct GuestMessage: Encodable, Equatable, Sendable {
        let role: String
        let content: String
    }

    private struct GuestBody: Encodable {
        let messages: [GuestMessage]
        let locale: String
    }

    func guest(messages: [GuestMessage], locale: String) throws -> AsyncThrowingStream<SSEEvent, Error> {
        api.stream(try Endpoint.post("v1/chat/guest", json: GuestBody(messages: messages, locale: locale)))
    }

    /// The history a guest request may carry: newest messages that fit the server limits, ending with the
    /// user's message. The conversation lives only on the device (SSOT §3.1).
    static func guestHistory(from messages: [ChatMessage]) -> [GuestMessage] {
        var kept: [GuestMessage] = []
        var total = 0
        for message in messages.reversed() where !message.text.isEmpty {
            let content = String(message.text.prefix(guestMaxMessageChars))
            if kept.count >= guestMaxMessages || total + content.count > guestMaxTotalChars { break }
            total += content.count
            kept.append(GuestMessage(role: message.role.rawValue, content: content))
        }
        kept.reverse()
        while let first = kept.first, first.role != "user" { kept.removeFirst() }
        return kept
    }

    // MARK: - Trip and proposals

    /// The trip built in `chatID`, if any (`GET /v1/trips` carries `chat_id`).
    func tripID(forChat chatID: UUID) async throws -> UUID? {
        let pageSize = 100
        var before: String?
        while true {
            var query = [URLQueryItem(name: "limit", value: String(pageSize))]
            if let before { query.append(URLQueryItem(name: "before", value: before)) }
            let page: TripLinks = try await api.send(.get("v1/trips", query: query))
            if let match = page.items.first(where: { $0.chatID == chatID }) { return match.id }
            guard page.items.count == pageSize, let cursor = page.items.last?.updatedAt, cursor != before else {
                return nil
            }
            try Task.checkCancellation()
            before = cursor
        }
    }

    func trip(id: UUID) async throws -> TripOverview {
        try await api.send(.get("v1/trips/\(Self.path(id))"))
    }

    func proposals(tripID: UUID) async throws -> [ProposalInfo] {
        let list: ProposalsList = try await api.send(.get("v1/trips/\(Self.path(tripID))/proposals"))
        return list.items
    }

    func accept(proposalID: UUID) async throws {
        try await api.send(.post("v1/proposals/\(Self.path(proposalID))/accept"))
    }

    func decline(proposalID: UUID) async throws {
        try await api.send(.post("v1/proposals/\(Self.path(proposalID))/decline"))
    }

    private static func path(_ id: UUID) -> String { id.uuidString.lowercased() }
}

private struct ChooseBody: Encodable {
    let ord: Int
    let placeID: String

    enum CodingKeys: String, CodingKey {
        case ord
        case placeID = "place_id"
    }
}
