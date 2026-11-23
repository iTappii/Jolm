import Foundation

// Answers of the plan's edit endpoints (Ш-37, Ш-38, Ш-55). Exact JSON: docs/reviews/Ш-37-server.md.

// MARK: - Edit answers

/// `POST /v1/trips/{id}/legs/{leg_id}/mode`.
struct LegModeChange: Decodable, Equatable, Sendable {
    let version: Int
    let leg: TripLeg
    let lateByS: Int?
    let changedDays: [String]
    let budget: RouteBudget?

    enum CodingKeys: String, CodingKey {
        case version, leg, budget
        case lateByS = "late_by_s"
        case changedDays = "changed_days"
    }
}

/// `POST /v1/trips/{id}/budget-choice`: the new stored budget block; the plan itself is re-read.
struct BudgetChoiceResult: Decodable, Equatable, Sendable {
    let version: Int
}

/// A stop that no longer fits after a removal.
struct DroppedStop: Decodable, Equatable, Sendable {
    let mustHave: Bool?

    enum CodingKeys: String, CodingKey { case mustHave = "must_have" }
}

/// `POST /v1/trips/{id}/items/{item_id}/remove`.
struct ItemRemoval: Decodable, Equatable, Sendable {
    let version: Int
    let changedDays: [String]
    let dropped: [DroppedStop]

    enum CodingKeys: String, CodingKey {
        case version, dropped
        case changedDays = "changed_days"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        version = try values.decodeIfPresent(Int.self, forKey: .version) ?? 0
        changedDays = try values.decodeIfPresent([String].self, forKey: .changedDays) ?? []
        dropped = try values.decodeIfPresent([DroppedStop].self, forKey: .dropped) ?? []
    }
}

// MARK: - Replacing a stop (Ш-55)

/// A place the stop can be swapped for: `GET /v1/trips/{id}/items/{item_id}/alternatives` (up to 5, nearby, similar,
/// not yet in the trip).
struct TripAlternative: Decodable, Equatable, Identifiable, Sendable {
    let id: UUID
    let name: String
    let category: String?
    let categoryName: String?
    let lat: Double
    let lon: Double
    let priceKzt: Int?
    let distanceM: Double?

    enum CodingKeys: String, CodingKey {
        case id, name, category, lat, lon
        case categoryName = "category_name"
        case priceKzt = "price_kzt"
        case distanceM = "distance_m"
    }
}

struct TripAlternatives: Decodable, Equatable, Sendable {
    let items: [TripAlternative]

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        items = (try values.decodeIfPresent([Lossy<TripAlternative>].self, forKey: .items) ?? []).compactMap(\.value)
    }

    enum CodingKeys: String, CodingKey { case items }
}

/// `POST /v1/trips/{id}/items/{item_id}/replace` body: exactly one of `place_id`, `category`, `query` (here the id).
struct ItemReplacement: Encodable, Equatable, Sendable {
    let placeID: UUID
    let force: Bool

    enum CodingKeys: String, CodingKey {
        case force
        case placeID = "place_id"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(placeID.uuidString.lowercased(), forKey: .placeID)
        try container.encode(force, forKey: .force)
    }
}
