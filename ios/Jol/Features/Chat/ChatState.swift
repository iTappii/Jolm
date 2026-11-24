import Foundation

/// Why the last turn did not finish. The view turns it into a localized sentence.
enum ChatFailure: Equatable, Sendable {
    /// 409 `chat_busy`: the previous answer is still being written.
    case busy
    /// 409 `chat_full`: the chat reached its message limit; only a new chat helps.
    case full
    /// 429, with `Retry-After` seconds when the server sent them.
    case rateLimited(retryAfter: Int?)
    /// 429 `llm_budget_exceeded` (Ш-66): the daily AI limit is used up; empty message → local text. No retry.
    case budgetExceeded(message: String)
    /// An `error` event or an HTTP error that carries the server's own (localized) text.
    case server(message: String)
    case network
    case other

    var canRetry: Bool {
        switch self {
        case .full, .budgetExceeded: false
        default: true
        }
    }

    /// Only "chat full" asks for a new chat; the daily limit offers nothing to press.
    var offersNewChat: Bool { self == .full }
}

enum ProposalState: Equatable, Sendable {
    case pending
    case working
    case accepted
    case declined
    case expired
    /// The server refused (`proposal_stale`, `proposal_not_applicable`, …) or the call failed; the buttons stay.
    case failed
}

struct ChatMessage: Identifiable, Equatable, Sendable {
    enum Role: String, Sendable {
        case user
        case assistant
    }

    let id: String
    let role: Role
    var text: String
    var proposalID: UUID?
    var isStreaming = false
}

/// Everything the chat UI shows, reduced from the server's events. Pure value type: `apply(_:)` is the whole
/// event reduction and is unit-tested without a network.
struct ChatState: Equatable, Sendable {
    var messages: [ChatMessage] = []
    /// Theses of the single-branch graph (SSOT §11.2), ordered by `ord`.
    var graph: [GraphNode] = []
    var brief: ChatBrief?
    /// Keys of the chain nodes in the order of the tourist's answers (`ChainNodes`); the node values come from `brief`.
    var chainOrder: [String] = []
    /// Pins the chat put on the map. They replace each other for the guest (`search`), accumulate for a trip.
    var mapPlaces: [MapPlace] = []
    /// Bumped on every change to `mapPlaces` — the map redraws and animates when it changes.
    var mapVersion = 0
    /// The route that grows while the tourist talks (Ш-54). It wins over `mapPlaces` for drawing and goes away with
    /// `route_ready`, when the trip by days takes over.
    var liveRoute: LiveRoute?
    /// Bumped on every change to `liveRoute`: the map refits and animates.
    var liveVersion = 0
    /// Ш-64: the live route is being built in the background (`live_route_status`); the text does not wait for it.
    var liveStatus: LiveRouteStatus?
    /// Set by `route_ready`: the graph converges into the final node.
    var route: RouteReady?
    /// Bumped on every `trip_updated`; the model refreshes the trip when it changes.
    var tripRevision = 0
    var isStreaming = false
    var failure: ChatFailure?
    var proposals: [UUID: ProposalState] = [:]
    private var localCounter = 0

    /// The nodes of the chain (SSOT §11.2): one per answered brief field, in the order of the answers.
    var chainNodes: [ChainNode] { ChainNodes.nodes(brief: brief, order: chainOrder) }

    var isBuildingRoute: Bool { liveStatus == .building }
    var isConverged: Bool { route != nil }
    var isEmpty: Bool { messages.isEmpty && graph.isEmpty && chainOrder.isEmpty }

    // MARK: - Local actions

    mutating func appendUserMessage(_ text: String) {
        localCounter += 1
        messages.append(ChatMessage(id: "local-\(localCounter)", role: .user, text: text))
    }

    /// A turn starts: the next `text_delta`s go into a fresh assistant bubble.
    mutating func beginTurn() {
        isStreaming = true
        failure = nil
    }

    mutating func fail(_ reason: ChatFailure) {
        endTurn()
        failure = reason
    }

    private mutating func endTurn() {
        isStreaming = false
        for index in messages.indices where messages[index].isStreaming { messages[index].isStreaming = false }
    }

    // MARK: - Event reduction

    mutating func apply(_ event: ChatEvent) {
        switch event {
        case .textDelta(let text):
            appendAssistantText(text)
        case .graphNode(let node):
            addGraphNode(node)
        case .briefUpdated(let brief, let changed):
            let added = ChainNodes.keys(changed: changed, previous: self.brief, current: brief)
            chainOrder = ChainNodes.merged(chainOrder, with: added)
            self.brief = brief
        case .mapPlaces(let reason, let places):
            addMapPlaces(places, replacing: reason == "search")
        case .liveRoute(let live):
            setLiveRoute(live)
        case .liveRouteStatus, .routeReady:
            applyRouteState(event)
        case .tripUpdated:
            tripRevision += 1
        case .done:
            endTurn()
        case .error(_, let message):
            fail(.server(message: message))
        case .unknown:
            break
        }
    }

    private mutating func applyRouteState(_ event: ChatEvent) {
        if case .liveRouteStatus(let status) = event { liveStatus = status }
        guard case .routeReady(let route) = event else { return }
        self.route = route
        liveStatus = nil
        setLiveRoute(nil)
    }

    private mutating func addGraphNode(_ node: GraphNode) {
        guard !graph.contains(where: { $0.ord == node.ord }) else { return }
        graph.append(node)
        graph.sort { $0.ord < $1.ord }
    }

    private mutating func appendAssistantText(_ text: String) {
        if let last = messages.indices.last, messages[last].role == .assistant, messages[last].isStreaming {
            messages[last].text += text
            return
        }
        localCounter += 1
        messages.append(ChatMessage(id: "local-\(localCounter)", role: .assistant, text: text, isStreaming: true))
    }

    mutating func addMapPlaces(_ places: [MapPlace], replacing: Bool) {
        guard !places.isEmpty else { return }
        var next = replacing ? [] : mapPlaces
        for place in places {
            if let index = next.firstIndex(where: { $0.id == place.id }) {
                next[index] = place
            } else {
                next.append(place)
            }
        }
        replaceMapPlaces(next)
    }

    mutating func setLiveRoute(_ live: LiveRoute?) {
        let live = live?.isEmpty == true ? nil : live
        guard live != liveRoute else { return }
        liveRoute = live
        liveVersion += 1
    }

    mutating func replaceMapPlaces(_ places: [MapPlace]) {
        guard places != mapPlaces else { return }
        mapPlaces = places
        mapVersion += 1
    }

    // MARK: - Reopening a chat

    /// State of a saved chat: messages and graph come from the server as they are. `map_places` is not stored, so
    /// the pins are restored by the model from the trip (when there is one).
    init(detail: ChatDetail, route: RouteReady?, proposals: [UUID: ProposalState]) {
        messages = detail.messages.map {
            ChatMessage(
                id: "server-\($0.id)", role: $0.role == "user" ? .user : .assistant,
                text: $0.content, proposalID: $0.proposalID
            )
        }
        graph = detail.graphNodes.sorted { $0.ord < $1.ord }
        brief = detail.brief
        chainOrder = ChainNodes.normalized(detail.brief?.filledOrder ?? [])
        self.route = route
        // A finished plan replaces the live route.
        if route == nil, let live = detail.liveRoute, !live.isEmpty { liveRoute = live }
        self.proposals = proposals
        for message in messages {
            if let id = message.proposalID, self.proposals[id] == nil { self.proposals[id] = .pending }
        }
    }

    init() {}
}
