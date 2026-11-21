import Foundation

// Wire shape of `GET /v1/trips/{id}/offline` (SSOT §7.4, Ш-42; exact JSON: docs/reviews/Ш-42-server.md). The same
// types are written to the device as they are, so what the app reads without a network is what the server sent.

struct OfflineInterval: Codable, Equatable, Sendable {
    let opens: String
    let closes: String
}

struct OfflineHours: Codable, Equatable, Sendable {
    /// 0 = Monday.
    let weekday: Int
    let intervals: [OfflineInterval]
}

struct OfflinePlace: Codable, Equatable, Sendable {
    let name: String
    let nameLang: String?
    let names: [String: String]?
    let category: String?
    let categoryName: String?
    let lat: Double
    let lon: Double
    let address: String?
    let hours: [OfflineHours]?
    let photoURL: String?

    enum CodingKeys: String, CodingKey {
        case name, names, category, lat, lon, address, hours
        case nameLang = "name_lang"
        case categoryName = "category_name"
        case photoURL = "photo_url"
    }
}

struct OfflineItem: Codable, Equatable, Sendable {
    let id: UUID
    let ord: Int?
    let kind: String
    let meal: String?
    let placeID: UUID
    let startsAt: String?
    let endsAt: String?
    let visitMin: Int?
    let mustHave: Bool?
    let estCostKzt: Int?

    enum CodingKeys: String, CodingKey {
        case id, ord, kind, meal
        case placeID = "place_id"
        case startsAt = "starts_at"
        case endsAt = "ends_at"
        case visitMin = "visit_min"
        case mustHave = "must_have"
        case estCostKzt = "est_cost_kzt"
    }
}

struct OfflineLeg: Codable, Equatable, Sendable {
    let id: UUID
    let fromItemID: UUID?
    let toItemID: UUID
    let departAt: String?
    let travelS: Int?
    let estimated: Bool?
    let mode: String?
    let costKzt: Int?
    let distanceM: Int?
    /// polyline6 of the chosen mode's best path; `nil` when it was not computed.
    let geometry: String?

    enum CodingKeys: String, CodingKey {
        case id, estimated, mode, geometry
        case fromItemID = "from_item_id"
        case toItemID = "to_item_id"
        case departAt = "depart_at"
        case travelS = "travel_s"
        case costKzt = "cost_kzt"
        case distanceM = "distance_m"
    }
}

struct OfflineDay: Codable, Equatable, Sendable {
    let date: String
    let items: [OfflineItem]
    let legs: [OfflineLeg]
}

/// The trip as the device keeps it: days with times, every place once, the chosen way for each leg.
struct OfflineTrip: Codable, Equatable, Sendable {
    let tripID: UUID
    let version: Int
    let locale: String?
    let timezone: String?
    let startDate: String
    let endDate: String
    let budgetKzt: Int?
    let totalCostKzt: Int?
    let days: [OfflineDay]
    /// By place id (lower-case UUID string).
    let places: [String: OfflinePlace]

    enum CodingKeys: String, CodingKey {
        case version, locale, timezone, days, places
        case tripID = "trip_id"
        case startDate = "start_date"
        case endDate = "end_date"
        case budgetKzt = "budget_kzt"
        case totalCostKzt = "total_cost_kzt"
    }

    func place(_ id: UUID) -> OfflinePlace? {
        places[id.uuidString.lowercased()] ?? places[id.uuidString]
    }

    var itemCount: Int { days.reduce(0) { $0 + $1.items.count } }
}

/// What is stored next to the trip: the validator for `If-None-Match` and when the copy was made.
struct OfflineTripMeta: Codable, Equatable, Sendable {
    let etag: String?
    let savedAt: Date

    enum CodingKeys: String, CodingKey {
        case etag
        case savedAt = "saved_at"
    }
}

/// A saved copy with its metadata.
struct SavedTrip: Codable, Equatable, Sendable {
    let meta: OfflineTripMeta
    let trip: OfflineTrip
}
