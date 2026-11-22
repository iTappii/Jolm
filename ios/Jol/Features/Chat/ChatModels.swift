import CoreLocation
import Foundation

// Wire shapes of the chat API (Ш-30, Ш-31, Ш-36, Ш-38, Ш-40). Everything is decoded tolerantly: a field the server
// adds later is ignored, a missing optional one becomes `nil` / empty.

struct ChatSummary: Decodable, Identifiable, Equatable, Sendable {
    let id: UUID
    let title: String?
    let locale: String?
    let updatedAt: String?
    let preview: String?

    enum CodingKeys: String, CodingKey {
        case id, title, locale, preview
        case updatedAt = "updated_at"
    }

    /// What the side panel shows: title, else the first words of the conversation.
    var displayTitle: String? {
        for candidate in [title, preview] {
            if let text = candidate?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty { return text }
        }
        return nil
    }
}

struct ChatsList: Decodable, Sendable {
    let items: [ChatSummary]
}

/// Trip brief as the server keeps it (`brief_updated` and `GET /v1/chats/{id}`).
struct ChatBrief: Decodable, Equatable, Sendable {
    var startDate: String?
    var endDate: String?
    var budgetKzt: Int?
    var hasAccommodation: Bool?
    var mustHaves: [String] = []
    var interests: [String] = []
    var pace: String?
    var crowdTolerance: Int?
    var missing: [String] = []
    var complete = false
    /// Order in which the tourist filled the fields (Ш-32b; only in `GET /v1/chats/{id}`): the chain's node order.
    var filledOrder: [String] = []

    enum CodingKeys: String, CodingKey {
        case startDate = "start_date"
        case endDate = "end_date"
        case budgetKzt = "budget_kzt"
        case hasAccommodation = "has_accommodation"
        case mustHaves = "must_haves"
        case interests, pace, missing, complete
        case filledOrder = "filled_order"
        case crowdTolerance = "crowd_tolerance"
    }

    init() {}

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        startDate = try values.decodeIfPresent(String.self, forKey: .startDate)
        endDate = try values.decodeIfPresent(String.self, forKey: .endDate)
        budgetKzt = try values.decodeIfPresent(Int.self, forKey: .budgetKzt)
        hasAccommodation = try values.decodeIfPresent(Bool.self, forKey: .hasAccommodation)
        mustHaves = try values.decodeIfPresent([String].self, forKey: .mustHaves) ?? []
        interests = try values.decodeIfPresent([String].self, forKey: .interests) ?? []
        pace = try values.decodeIfPresent(String.self, forKey: .pace)
        crowdTolerance = try values.decodeIfPresent(Int.self, forKey: .crowdTolerance)
        missing = try values.decodeIfPresent([String].self, forKey: .missing) ?? []
        complete = try values.decodeIfPresent(Bool.self, forKey: .complete) ?? false
        filledOrder = try values.decodeIfPresent([String].self, forKey: .filledOrder) ?? []
    }

    /// Nothing worth a chip yet.
    var isEmpty: Bool {
        startDate == nil && endDate == nil && budgetKzt == nil && hasAccommodation == nil
    }
}

struct GraphNode: Decodable, Equatable, Identifiable, Sendable {
    let ord: Int
    let kind: String?
    let text: String

    var id: Int { ord }
}

struct ChatMessageDTO: Decodable, Equatable, Sendable {
    let id: Int
    let role: String
    let content: String
    let finish: String?
    let proposalID: UUID?

    enum CodingKeys: String, CodingKey {
        case id, role, content, finish
        case proposalID = "proposal_id"
    }
}

struct ChatDetail: Decodable, Equatable, Sendable {
    let id: UUID
    let title: String?
    let messages: [ChatMessageDTO]
    let brief: ChatBrief?
    let graphNodes: [GraphNode]
    /// The live route as the server kept it (Ш-54); `nil` before the first stop.
    let liveRoute: LiveRoute?

    enum CodingKeys: String, CodingKey {
        case id, title, messages, brief
        case graphNodes = "graph_nodes"
        case liveRoute = "live_route"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(UUID.self, forKey: .id)
        title = try values.decodeIfPresent(String.self, forKey: .title)
        messages = try values.decodeIfPresent([ChatMessageDTO].self, forKey: .messages) ?? []
        brief = try values.decodeIfPresent(ChatBrief.self, forKey: .brief)
        graphNodes = try values.decodeIfPresent([GraphNode].self, forKey: .graphNodes) ?? []
        liveRoute = try? values.decodeIfPresent(LiveRoute.self, forKey: .liveRoute)
    }
}

/// A place the chat talks about (`map_places`): pins on the live map.
struct MapPlace: Decodable, Equatable, Identifiable, Sendable {
    let id: UUID
    let name: String
    let category: String?
    let lat: Double
    let lon: Double
    let mustHave: Bool?

    enum CodingKeys: String, CodingKey {
        case id, name, category, lat, lon
        case mustHave = "must_have"
    }

    /// The map layer and the place card work on `PlaceSummary`; a chat pin is a public venue.
    var summary: PlaceSummary {
        PlaceSummary(
            id: id, name: name, category: category, kind: "venue", lat: lat, lon: lon,
            isPublic: true, isPartner: false, popularity: 50
        )
    }
}

struct RouteBudget: Decodable, Equatable, Sendable {
    let budgetKzt: Int?
    let status: String?
    let totalKzt: Int?
    let remainingKzt: Int?
    let shortfallKzt: Int?

    enum CodingKeys: String, CodingKey {
        case status
        case budgetKzt = "budget_kzt"
        case totalKzt = "total_kzt"
        case remainingKzt = "remaining_kzt"
        case shortfallKzt = "shortfall_kzt"
    }

    var isOver: Bool { status == "over" }
}

struct RouteUnmet: Decodable, Equatable, Sendable {
    let wish: String?
    let placeName: String?

    enum CodingKeys: String, CodingKey {
        case wish
        case placeName = "place_name"
    }
}

/// `route_ready`: the plan is saved; the plan itself is read with `GET /v1/trips/{id}`.
struct RouteReady: Decodable, Equatable, Sendable {
    struct Warning: Decodable, Equatable, Sendable {
        let code: String
    }

    let tripID: UUID
    var version: Int
    var days: Int
    let warnings: [Warning]
    let mustHaveUnmet: [RouteUnmet]
    var budget: RouteBudget?

    enum CodingKeys: String, CodingKey {
        case version, days, warnings, budget
        case tripID = "trip_id"
        case mustHaveUnmet = "must_have_unmet"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        tripID = try values.decode(UUID.self, forKey: .tripID)
        version = try values.decodeIfPresent(Int.self, forKey: .version) ?? 1
        days = try values.decodeIfPresent(Int.self, forKey: .days) ?? 0
        warnings = try values.decodeIfPresent([Warning].self, forKey: .warnings) ?? []
        mustHaveUnmet = try values.decodeIfPresent([RouteUnmet].self, forKey: .mustHaveUnmet) ?? []
        budget = try values.decodeIfPresent(RouteBudget.self, forKey: .budget)
    }

    init(tripID: UUID, version: Int = 1, days: Int = 0, budget: RouteBudget? = nil) {
        self.tripID = tripID
        self.version = version
        self.days = days
        self.warnings = []
        self.mustHaveUnmet = []
        self.budget = budget
    }
}

/// `trip_updated`: an edit (remove / replace / accepted proposal) changed the plan.
struct TripUpdated: Decodable, Equatable, Sendable {
    let tripID: UUID
    let version: Int
    let action: String?
    let changedDays: [String]

    enum CodingKeys: String, CodingKey {
        case version, action
        case tripID = "trip_id"
        case changedDays = "changed_days"
    }

    init(tripID: UUID, version: Int, action: String?, changedDays: [String]) {
        self.tripID = tripID
        self.version = version
        self.action = action
        self.changedDays = changedDays
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        tripID = try values.decode(UUID.self, forKey: .tripID)
        version = try values.decodeIfPresent(Int.self, forKey: .version) ?? 0
        action = try values.decodeIfPresent(String.self, forKey: .action)
        changedDays = try values.decodeIfPresent([String].self, forKey: .changedDays) ?? []
    }
}

// MARK: - Trip link (the full trip is in `Features/Trip/TripModels.swift`)

struct TripLink: Decodable, Equatable, Sendable {
    let id: UUID
    let chatID: UUID?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case chatID = "chat_id"
        case updatedAt = "updated_at"
    }
}

struct TripLinks: Decodable, Sendable {
    let items: [TripLink]
}

struct ProposalInfo: Decodable, Equatable, Sendable {
    let id: UUID
    let status: String
}

struct ProposalsList: Decodable, Sendable {
    let items: [ProposalInfo]
}

// MARK: - SSE

/// One decoded server-sent event of a chat stream. Unknown events — and known ones whose payload does not
/// decode — become `.unknown` and are ignored by the reducer, so a newer server never breaks an older app.
enum ChatEvent: Equatable, Sendable {
    case textDelta(String)
    case graphNode(GraphNode)
    /// The brief and the names of the fields this update changed.
    case briefUpdated(ChatBrief, changed: [String])
    case mapPlaces(reason: String, places: [MapPlace])
    case liveRoute(LiveRoute)
    case routeReady(RouteReady)
    case tripUpdated(TripUpdated)
    case done
    case error(code: String, message: String)
    case unknown(String)

    init(_ event: SSEEvent) {
        let data = Data(event.data.utf8)
        self = Self.decode(event.event, data) ?? .unknown(event.event)
    }

    private static func decode(_ name: String, _ data: Data) -> ChatEvent? {
        let decoder = JSONDecoder()
        switch name {
        case "text_delta": return (try? decoder.decode(TextDelta.self, from: data)).map { .textDelta($0.text) }
        case "graph_node": return (try? decoder.decode(GraphNode.self, from: data)).map { .graphNode($0) }
        case "brief_updated":
            return (try? decoder.decode(BriefUpdated.self, from: data))
                .map { .briefUpdated($0.brief, changed: $0.changed ?? []) }
        case "map_places":
            return (try? decoder.decode(MapPlacesPayload.self, from: data))
                .map { .mapPlaces(reason: $0.reason ?? "chosen", places: $0.places) }
        case "live_route": return (try? decoder.decode(LiveRoute.self, from: data)).map { .liveRoute($0) }
        case "route_ready": return (try? decoder.decode(RouteReady.self, from: data)).map { .routeReady($0) }
        case "trip_updated": return (try? decoder.decode(TripUpdated.self, from: data)).map { .tripUpdated($0) }
        case "done": return .done
        case "error":
            let payload = try? decoder.decode(ErrorPayload.self, from: data)
            return .error(code: payload?.code ?? "error", message: payload?.message ?? "")
        default: return nil
        }
    }

    private struct TextDelta: Decodable { let text: String }
    private struct BriefUpdated: Decodable {
        let brief: ChatBrief
        let changed: [String]?
    }
    private struct ErrorPayload: Decodable {
        let code: String?
        let message: String?
    }

    private struct MapPlacesPayload: Decodable {
        let reason: String?
        let places: [MapPlace]
    }
}
