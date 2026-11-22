import Foundation
import Observation

/// The chat of the main screen (Ш-32). Lives in `AppContainer`, so a stream keeps running while the panel is
/// collapsed. A guest talks to `POST /v1/chat/guest` with a history kept only here; a signed-in user talks to a
/// saved chat (`/v1/chats…`). All event handling goes through `ChatState.apply`.
@MainActor
@Observable
final class ChatModel {
    enum Load<Value: Equatable>: Equatable {
        case idle
        case loading
        case loaded(Value)
        case failed
    }

    private(set) var state = ChatState()
    private(set) var chatID: UUID?
    private(set) var tripID: UUID?
    private(set) var trip: Load<TripOverview> = .idle
    private(set) var recent: Load<[ChatSummary]> = .idle
    /// A saved chat is being fetched (reopen from the side panel).
    private(set) var isOpening = false
    private(set) var openFailed = false
    /// A stop swap (Ш-54) is on its way, and the last one that failed: shown as a toast, never blocks the map.
    private(set) var isChoosing = false
    private(set) var liveRouteError: LiveRouteError?

    @ObservationIgnored private let service: ChatService
    @ObservationIgnored private let language: @MainActor () -> String
    @ObservationIgnored private var streamTask: Task<Void, Never>?
    @ObservationIgnored private var recentTask: Task<Void, Never>?
    @ObservationIgnored private var tripTask: Task<Void, Never>?
    @ObservationIgnored private var retryText: String?
    @ObservationIgnored private var transcriptIsGuest = true
    /// Bumped on every reset / reopen, so a late answer of an older chat is dropped.
    @ObservationIgnored private var generation = 0

    init(api: APIClient, language: @escaping @MainActor () -> String = { "en" }) {
        self.service = ChatService(api: api)
        self.language = language
    }

    var isStreaming: Bool { state.isStreaming }
    var isGuestTranscript: Bool { chatID == nil && transcriptIsGuest && !state.messages.isEmpty }

    // MARK: - Intent

    /// A guest who wants a personal multi-day trip must sign in first (SSOT §3.2). The server does not signal this
    /// (API gap), so the app checks the wording: trip / itinerary / budget / "N days in …".
    nonisolated static func wantsPersonalTrip(_ text: String) -> Bool {
        let lowered = text.lowercased()
        let patterns = [
            #"\bitinerar"#, #"\bmy trip\b"#, #"\bplan (my|a|the|our)\b"#, #"\bbuild (me )?(a |my )?(route|trip|plan)"#,
            #"\bbudget\b"#, #"\bdays? in\b"#, #"\b\d+[- ]days?\b"#, #"\bweek in\b"#,
            #"поездк"#, #"путешеств"#, #"бюджет"#, #"состав(ь|ить) .*маршрут"#, #"построй.*маршрут"#,
            #"маршрут на"#, #"\bдн(я|ей) в\b"#, #"\bнедел"#,
        ]
        return patterns.contains { lowered.range(of: $0, options: .regularExpression) != nil }
    }

    // MARK: - Sending

    /// Sends `text`. A signed-in user writes to a saved chat (created on the first message), a guest to the guest
    /// chat. The caller has already decided which one it is (gate, intent).
    func send(_ text: String, signedIn: Bool) {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !state.isStreaming, !isOpening else { return }
        if signedIn, isGuestTranscript { reset() }  // the guest talk does not move into the saved chat
        transcriptIsGuest = !signedIn
        state.appendUserMessage(text)
        run(text: text, signedIn: signedIn)
    }

    /// Sends the last message again after a failed turn.
    func retry() {
        guard let text = retryText, !state.isStreaming, state.failure?.canRetry == true else { return }
        // A half-written answer of the failed attempt is dropped; the user's message stays.
        while let last = state.messages.last, last.role == .assistant { state.messages.removeLast() }
        run(text: text, signedIn: !transcriptIsGuest)
    }

    /// Guest wants the personal route after all: carry the last thing they asked into a saved chat.
    func lastUserText() -> String? {
        state.messages.last { $0.role == .user }?.text
    }

    private func run(text: String, signedIn: Bool) {
        retryText = text
        state.beginTurn()
        let generation = generation
        streamTask = Task { [weak self] in
            guard let self else { return }
            do {
                let stream: AsyncThrowingStream<SSEEvent, Error>
                if signedIn { stream = try await openRegistered(text) } else { stream = try openGuest() }
                let finished = try await consume(stream, generation: generation)
                guard generation == self.generation else { return }
                if !finished { state.fail(.network) } else if state.isStreaming { state.apply(.done) }
                if signedIn { loadRecent(silently: true) }
            } catch is CancellationError {
                return
            } catch {
                guard generation == self.generation, !Task.isCancelled else { return }
                state.fail(Self.failure(for: error))
            }
        }
    }

    /// Feeds the stream to the reducer; true when it ended with `done` or `error`.
    private func consume(_ stream: AsyncThrowingStream<SSEEvent, Error>, generation: Int) async throws -> Bool {
        var finished = false
        for try await raw in stream {
            guard generation == self.generation else { return true }
            let event = ChatEvent(raw)
            state.apply(event)
            switch event {
            case .done, .error: finished = true
            default: sideEffects(of: event)
            }
        }
        return finished
    }

    private func openRegistered(_ text: String) async throws -> AsyncThrowingStream<SSEEvent, Error> {
        if chatID == nil {
            let chat = try await service.createChat(locale: language())
            try Task.checkCancellation()
            chatID = chat.id
        }
        guard let chatID else { throw APIError.invalidResponse }
        return try service.send(chatID: chatID, text: text)
    }

    private func openGuest() throws -> AsyncThrowingStream<SSEEvent, Error> {
        try service.guest(messages: ChatService.guestHistory(from: state.messages), locale: language())
    }

    private func sideEffects(of event: ChatEvent) {
        switch event {
        case .routeReady(let route):
            tripID = route.tripID
            loadTrip()
        case .tripUpdated(let update):
            tripID = update.tripID
            loadTrip()
        default:
            break
        }
    }

    nonisolated static func failure(for error: Error) -> ChatFailure {
        guard let error = error as? APIError else { return .other }
        switch error {
        case .server(_, let code, _) where code == "chat_busy": return .busy
        case .server(_, let code, _) where code == "chat_full": return .full
        case .rateLimited(let retryAfter, _): return .rateLimited(retryAfter: retryAfter.map { Int($0.rounded(.up)) })
        case .server(_, _, let message) where !message.isEmpty: return .server(message: message)
        case .network: return .network
        default: return .other
        }
    }

    // MARK: - New chat, reopen, reset

    /// "New chat": drops the current conversation (an answer being written is cancelled client-side only).
    func newChat() {
        reset()
    }

    func reset() {
        generation += 1
        streamTask?.cancel()
        tripTask?.cancel()
        streamTask = nil
        state = ChatState()
        chatID = nil
        tripID = nil
        trip = .idle
        retryText = nil
        isOpening = false
        openFailed = false
        transcriptIsGuest = true
        isChoosing = false
        liveRouteError = nil
    }

    /// Reopens a saved chat: messages, brief and graph from `GET /v1/chats/{id}`; the converged graph and the
    /// pins come from the trip that belongs to the chat (`map_places` itself is not stored).
    func open(_ id: UUID) {
        reset()
        isOpening = true
        transcriptIsGuest = false
        let generation = generation
        streamTask = Task { [weak self] in
            guard let self else { return }
            do {
                let loaded = try await load(chatID: id)
                guard generation == self.generation else { return }
                chatID = id
                state = loaded.state
                tripID = loaded.tripID
                isOpening = false
                if tripID != nil { loadTrip() }
            } catch {
                guard generation == self.generation, !Task.isCancelled else { return }
                isOpening = false
                openFailed = true
            }
        }
    }

    private struct Loaded {
        let state: ChatState
        let tripID: UUID?
    }

    private func load(chatID id: UUID) async throws -> Loaded {
        let detail = try await service.chat(id: id)
        let tripID = try? await service.tripID(forChat: id)
        var proposals: [UUID: ProposalState] = [:]
        if let tripID, detail.messages.contains(where: { $0.proposalID != nil }),
           let infos = try? await service.proposals(tripID: tripID) {
            for info in infos { proposals[info.id] = Self.proposalState(info.status) }
        }
        let route = tripID.map { RouteReady(tripID: $0) }
        return Loaded(state: ChatState(detail: detail, route: route, proposals: proposals), tripID: tripID)
    }

    private static func proposalState(_ status: String) -> ProposalState {
        switch status {
        case "accepted": .accepted
        case "declined": .declined
        case "expired": .expired
        default: .pending
        }
    }

    /// Re-reads the open chat (after a proposal was decided) without touching the map pins.
    private func reload() {
        guard let id = chatID, !state.isStreaming else { return }
        let generation = generation
        Task { [weak self] in
            guard let self, let loaded = try? await load(chatID: id), generation == self.generation,
                  !state.isStreaming else { return }
            var next = loaded.state
            next.mapPlaces = state.mapPlaces
            next.mapVersion = state.mapVersion
            next.liveRoute = state.liveRoute
            next.liveVersion = state.liveVersion
            if let route = state.route, next.route == nil || next.route?.tripID == route.tripID { next.route = route }
            state = next
            if let id = loaded.tripID { tripID = id }
        }
    }
}

/// Why swapping a live stop failed (the view turns it into a short sentence).
enum LiveRouteError: Equatable, Sendable {
    /// The alternative or the route is gone (404 / 409 / 422): the route was re-read.
    case outdated
    /// 409 `chat_busy`: the assistant is still writing; the route stays, try again in a moment.
    case busy
    case network
}

extension ChatModel {
    // MARK: - Live route (Ш-54)

    /// «Choose this instead»: the alternative `placeID` replaces stop `ord`. The answer is the whole route again.
    func chooseAlternative(ord: Int, placeID: UUID) {
        guard let chatID, !isChoosing, state.liveRoute != nil else { return }
        isChoosing = true
        liveRouteError = nil
        let generation = generation
        Task { [weak self] in
            guard let self else { return }
            do {
                let live = try await service.chooseLiveStop(chatID: chatID, ord: ord, placeID: placeID)
                guard generation == self.generation else { return }
                state.setLiveRoute(live)
            } catch {
                guard generation == self.generation else { return }
                if case .server(409, "chat_busy", _)? = error as? APIError {
                    liveRouteError = .busy
                } else if case .server(let status, _, _)? = error as? APIError, [404, 409, 422].contains(status) {
                    liveRouteError = .outdated
                    if let detail = try? await service.chat(id: chatID), generation == self.generation,
                       !state.isConverged {
                        state.setLiveRoute(detail.liveRoute)
                    }
                } else {
                    liveRouteError = .network
                }
            }
            if generation == self.generation { isChoosing = false }
        }
    }

    func dismissLiveRouteError() {
        liveRouteError = nil
    }

    // MARK: - Recent chats

    func loadRecent(silently: Bool = false) {
        recentTask?.cancel()
        if !silently { recent = .loading }
        recentTask = Task { [weak self] in
            guard let self else { return }
            do {
                let items = try await service.chats()
                guard !Task.isCancelled else { return }
                recent = .loaded(items)
            } catch {
                guard !Task.isCancelled else { return }
                if !silently { recent = .failed }
            }
        }
    }

    func clearRecent() {
        recentTask?.cancel()
        recent = .idle
    }

    // MARK: - Trip

    func loadTrip() {
        guard let id = tripID else { return }
        tripTask?.cancel()
        if case .loaded = trip {} else { trip = .loading }
        tripTask = Task { [weak self] in
            guard let self else { return }
            do {
                let overview = try await service.trip(id: id)
                guard !Task.isCancelled, tripID == id else { return }
                trip = .loaded(overview)
                var summary = state.route ?? RouteReady(tripID: id)
                summary.version = overview.version
                summary.days = overview.days.count
                if let budget = overview.budget { summary.budget = budget }
                state.route = summary
                // The plan is the truth for the map: every stop of every day.
                state.replaceMapPlaces(overview.places)
            } catch {
                guard !Task.isCancelled, tripID == id else { return }
                if case .loaded = trip {} else { trip = .failed }
            }
        }
    }

    // MARK: - Proposals (SSOT §7.1)

    func decide(_ proposalID: UUID, accept: Bool) {
        guard state.proposals[proposalID] != .working else { return }
        state.proposals[proposalID] = .working
        let generation = generation
        Task { [weak self] in
            guard let self else { return }
            do {
                if accept { try await service.accept(proposalID: proposalID) } else {
                    try await service.decline(proposalID: proposalID)
                }
                guard generation == self.generation else { return }
                state.proposals[proposalID] = accept ? .accepted : .declined
                if accept { loadTrip() }
                reload()
            } catch {
                guard generation == self.generation else { return }
                state.proposals[proposalID] = Self.proposalFailure(error)
                if case .server(409, _, _) = error as? APIError { reload() }
            }
        }
    }

    nonisolated static func proposalFailure(_ error: Error) -> ProposalState {
        guard case .server(409, let code, _)? = error as? APIError else { return .failed }
        switch code {
        case "proposal_stale": return .expired
        case "proposal_decided": return .declined
        default: return .failed
        }
    }
}
