import CoreLocation
import Foundation

// Wire shapes of `GET /v1/trips/{id}` and of the edit endpoints (Ш-37, Ш-38). Exact JSON: docs/reviews/Ш-37-server.md.
// Everything not needed to draw the trip is optional or ignored, so a field the server adds later changes nothing.

struct TripPlace: Decodable, Equatable, Sendable {
    let id: UUID
    let name: String
    let category: String?
    let categoryName: String?
    let lat: Double
    let lon: Double

    enum CodingKeys: String, CodingKey {
        case id, name, category, lat, lon
        case categoryName = "category_name"
    }

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    /// The card and the map layers work on `PlaceSummary`; a stop of the plan is a public venue to them.
    var summary: PlaceSummary {
        PlaceSummary(
            id: id, name: name, category: category, kind: "venue", lat: lat, lon: lon,
            isPublic: true, isPartner: false, popularity: 50
        )
    }
}

struct TripDayItem: Decodable, Equatable, Identifiable, Sendable {
    let id: UUID
    let ord: Int?
    let kind: String
    let meal: String?
    let startsAt: String?
    let endsAt: String?
    let visitMin: Int?
    let mustHave: Bool?
    let estCostKzt: Int?
    let rainExposed: Bool?
    let place: TripPlace

    enum CodingKeys: String, CodingKey {
        case id, ord, kind, meal, place
        case startsAt = "starts_at"
        case endsAt = "ends_at"
        case visitMin = "visit_min"
        case mustHave = "must_have"
        case estCostKzt = "est_cost_kzt"
        case rainExposed = "rain_exposed"
    }

    /// "HH:mm" of the local start time as the server wrote it (`2026-12-05T09:30:00+05:00`).
    var startTime: String? { Self.clock(startsAt) }
    var endTime: String? { Self.clock(endsAt) }

    static func clock(_ iso: String?) -> String? {
        guard let iso, let index = iso.firstIndex(of: "T") else { return nil }
        return String(iso[iso.index(after: index)...].prefix(5))
    }
}

/// A way to get from one stop to the next, as stored in the plan: the same fields as a directions option.
struct TripLeg: Decodable, Equatable, Identifiable, Sendable {
    let id: UUID
    let fromItemID: UUID?
    let toItemID: UUID
    let departAt: String?
    let travelS: Int?
    let estimated: Bool?
    let chosenModeRaw: String?
    let costKzt: Int?
    let options: [DirectionOption]

    enum CodingKeys: String, CodingKey {
        case id, estimated, options
        case fromItemID = "from_item_id"
        case toItemID = "to_item_id"
        case departAt = "depart_at"
        case travelS = "travel_s"
        case chosenModeRaw = "chosen_mode"
        case costKzt = "cost_kzt"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(UUID.self, forKey: .id)
        fromItemID = try values.decodeIfPresent(UUID.self, forKey: .fromItemID)
        toItemID = try values.decode(UUID.self, forKey: .toItemID)
        departAt = try values.decodeIfPresent(String.self, forKey: .departAt)
        travelS = try values.decodeIfPresent(Int.self, forKey: .travelS)
        estimated = try values.decodeIfPresent(Bool.self, forKey: .estimated)
        chosenModeRaw = try values.decodeIfPresent(String.self, forKey: .chosenModeRaw)
        costKzt = try values.decodeIfPresent(Int.self, forKey: .costKzt)
        // One option with a mode this app does not know must not hide the whole plan.
        options = (try values.decodeIfPresent([Lossy<DirectionOption>].self, forKey: .options) ?? [])
            .compactMap(\.value)
    }

    var chosenMode: TransportMode? { chosenModeRaw.flatMap(TransportMode.init(rawValue:)) }

    /// One option per mode, the best variant of each (what `POST …/mode` can choose between).
    var modeChoices: [DirectionOption] {
        var seen = Set<TransportMode>()
        let ordered = options.sorted {
            let (left, right) = ($0.variant ?? 0, $1.variant ?? 0)
            return left != right ? left < right : ($0.recommended && !$1.recommended)
        }
        let picked = ordered.filter { seen.insert($0.mode).inserted }
        return picked.sorted { lhs, rhs in
            (TransportPage.Kind(lhs.mode), lhs.durationS) < (TransportPage.Kind(rhs.mode), rhs.durationS)
        }
    }

    /// The option the leg is travelled by: the chosen mode, else the recommended one, else the first.
    var activeOption: DirectionOption? {
        let choices = modeChoices
        if let mode = chosenMode, let match = choices.first(where: { $0.mode == mode }) { return match }
        return choices.first { $0.recommended } ?? choices.first
    }
}

private struct Lossy<Value: Decodable>: Decodable {
    let value: Value?

    init(from decoder: Decoder) throws {
        value = try? Value(from: decoder)
    }
}

struct TripDay: Decodable, Equatable, Identifiable, Sendable {
    let date: String
    var items: [TripDayItem]
    var legs: [TripLeg]

    var id: String { date }

    enum CodingKeys: String, CodingKey { case date, items, legs }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        date = try values.decode(String.self, forKey: .date)
        items = try values.decodeIfPresent([TripDayItem].self, forKey: .items) ?? []
        legs = try values.decodeIfPresent([TripLeg].self, forKey: .legs) ?? []
    }

    /// The leg that arrives at `item` (the first stop of a day has none).
    func leg(to item: TripDayItem) -> TripLeg? { legs.first { $0.toItemID == item.id } }
}

// MARK: - Budget

struct TripPlaceRef: Decodable, Equatable, Sendable {
    let id: UUID?
    let name: String
}

struct TripSwap: Decodable, Equatable, Sendable {
    let from: TripPlaceRef
    let to: TripPlaceRef?
}

/// One of the two ways out of an over-budget plan (SSOT §5.2): `drop_places` or `cheaper`.
struct BudgetVariant: Decodable, Equatable, Sendable {
    let feasible: Bool
    let totalKzt: Int
    let savesKzt: Int
    let shortfallKzt: Int
    let removedCount: Int?
    let removed: [TripPlaceRef]
    let swapsCount: Int?
    let swaps: [TripSwap]
    let lodgingChanged: Bool

    enum CodingKeys: String, CodingKey {
        case feasible, removed, swaps
        case totalKzt = "total_kzt"
        case savesKzt = "saves_kzt"
        case shortfallKzt = "shortfall_kzt"
        case removedCount = "removed_count"
        case swapsCount = "swaps_count"
        case lodgingChanged = "lodging_changed"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        feasible = try values.decodeIfPresent(Bool.self, forKey: .feasible) ?? false
        totalKzt = try values.decodeIfPresent(Int.self, forKey: .totalKzt) ?? 0
        savesKzt = try values.decodeIfPresent(Int.self, forKey: .savesKzt) ?? 0
        shortfallKzt = try values.decodeIfPresent(Int.self, forKey: .shortfallKzt) ?? 0
        removedCount = try values.decodeIfPresent(Int.self, forKey: .removedCount)
        removed = try values.decodeIfPresent([TripPlaceRef].self, forKey: .removed) ?? []
        swapsCount = try values.decodeIfPresent(Int.self, forKey: .swapsCount)
        swaps = try values.decodeIfPresent([TripSwap].self, forKey: .swaps) ?? []
        lodgingChanged = try values.decodeIfPresent(Bool.self, forKey: .lodgingChanged) ?? false
    }

    /// How many places leave (drop) or are swapped (cheaper).
    var changedCount: Int { removedCount ?? removed.count + (swapsCount ?? swaps.count) }
}

struct BudgetBreakdown: Decodable, Equatable, Sendable {
    let lodgingKzt: Int?
    let entriesKzt: Int?
    let mealsKzt: Int?
    let transportKzt: Int?
    let eventsKzt: Int?

    enum CodingKeys: String, CodingKey {
        case lodgingKzt = "lodging_kzt"
        case entriesKzt = "entries_kzt"
        case mealsKzt = "meals_kzt"
        case transportKzt = "transport_kzt"
        case eventsKzt = "events_kzt"
    }

    struct Line: Equatable, Identifiable, Sendable {
        /// A String Catalog key.
        let label: String
        let value: Int

        var id: String { label }
    }

    /// Lines worth showing (a zero line is noise), in a fixed order.
    var lines: [Line] {
        let all: [(String, Int?)] = [
            ("Lodging", lodgingKzt), ("Entries", entriesKzt), ("Meals", mealsKzt),
            ("Transport", transportKzt), ("Events", eventsKzt),
        ]
        return all.compactMap { label, value in (value ?? 0) > 0 ? Line(label: label, value: value ?? 0) : nil }
    }
}

struct TripLodging: Decodable, Equatable, Sendable {
    let needed: Bool?
    let nights: Int?
    let costKzt: Int?
    let priceAssumed: Bool?

    enum CodingKeys: String, CodingKey {
        case needed, nights
        case costKzt = "cost_kzt"
        case priceAssumed = "price_assumed"
    }
}

/// The budget block of a trip: summary, breakdown and — when the plan is over budget — the two variants.
struct TripBudget: Decodable, Equatable, Sendable {
    let status: String?
    let budgetKzt: Int?
    let totalKzt: Int?
    let remainingKzt: Int?
    let shortfallKzt: Int?
    let breakdown: BudgetBreakdown?
    let lodging: TripLodging?
    let dropPlaces: BudgetVariant?
    let cheaper: BudgetVariant?
    let choice: String?

    enum CodingKeys: String, CodingKey {
        case status, breakdown, lodging, variants, choice
        case budgetKzt = "budget_kzt"
        case totalKzt = "total_kzt"
        case remainingKzt = "remaining_kzt"
        case shortfallKzt = "shortfall_kzt"
    }

    private enum VariantKeys: String, CodingKey {
        case dropPlaces = "drop_places"
        case cheaper
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        status = try values.decodeIfPresent(String.self, forKey: .status)
        budgetKzt = try values.decodeIfPresent(Int.self, forKey: .budgetKzt)
        totalKzt = try values.decodeIfPresent(Int.self, forKey: .totalKzt)
        remainingKzt = try values.decodeIfPresent(Int.self, forKey: .remainingKzt)
        shortfallKzt = try values.decodeIfPresent(Int.self, forKey: .shortfallKzt)
        breakdown = try values.decodeIfPresent(BudgetBreakdown.self, forKey: .breakdown)
        lodging = try values.decodeIfPresent(TripLodging.self, forKey: .lodging)
        choice = try? values.decodeIfPresent(String.self, forKey: .choice)
        if let variants = try? values.nestedContainer(keyedBy: VariantKeys.self, forKey: .variants) {
            dropPlaces = try? variants.decodeIfPresent(BudgetVariant.self, forKey: .dropPlaces)
            cheaper = try? variants.decodeIfPresent(BudgetVariant.self, forKey: .cheaper)
        } else {
            dropPlaces = nil
            cheaper = nil
        }
    }

    var isOver: Bool { status == "over" }
    var hasVariants: Bool { dropPlaces != nil || cheaper != nil }
}

struct TripWarning: Decodable, Equatable, Sendable {
    let code: String
    let detail: String?
}

struct TripOverview: Decodable, Equatable, Sendable {
    let id: UUID
    var version: Int
    let startDate: String
    let endDate: String
    let budgetKzt: Int?
    var totalCostKzt: Int?
    /// The short summary (`RouteBudget`) the chat card shows.
    var budget: RouteBudget?
    /// The full block (breakdown, variants).
    var budgetDetail: TripBudget?
    /// `drop_places`, `cheaper`, `keep` once the person chose, else nil.
    var budgetChoice: String?
    var days: [TripDay]
    let warnings: [TripWarning]
    let mustHaveUnmet: [RouteUnmet]
    let events: [EventItem]

    enum CodingKeys: String, CodingKey {
        case id, version, days, budget, warnings, events
        case startDate = "start_date"
        case endDate = "end_date"
        case budgetKzt = "budget_kzt"
        case totalCostKzt = "total_cost_kzt"
        case budgetChoice = "budget_choice"
        case mustHaveUnmet = "must_have_unmet"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(UUID.self, forKey: .id)
        version = try values.decodeIfPresent(Int.self, forKey: .version) ?? 1
        startDate = try values.decode(String.self, forKey: .startDate)
        endDate = try values.decode(String.self, forKey: .endDate)
        budgetKzt = try values.decodeIfPresent(Int.self, forKey: .budgetKzt)
        totalCostKzt = try values.decodeIfPresent(Int.self, forKey: .totalCostKzt)
        budget = try? values.decodeIfPresent(RouteBudget.self, forKey: .budget)
        budgetDetail = try? values.decodeIfPresent(TripBudget.self, forKey: .budget)
        budgetChoice = try? values.decodeIfPresent(String.self, forKey: .budgetChoice)
        days = try values.decodeIfPresent([TripDay].self, forKey: .days) ?? []
        warnings = try values.decodeIfPresent([TripWarning].self, forKey: .warnings) ?? []
        mustHaveUnmet = try values.decodeIfPresent([RouteUnmet].self, forKey: .mustHaveUnmet) ?? []
        events = try values.decodeIfPresent([EventItem].self, forKey: .events) ?? []
    }

    var places: [MapPlace] {
        var seen = Set<UUID>()
        return days.flatMap(\.items).compactMap { item in
            guard seen.insert(item.place.id).inserted else { return nil }
            return MapPlace(
                id: item.place.id, name: item.place.name, category: item.place.category,
                lat: item.place.lat, lon: item.place.lon, mustHave: nil
            )
        }
    }

    var itemCount: Int { days.reduce(0) { $0 + $1.items.count } }

    /// The budget is over and the person has not chosen a way out yet.
    var needsBudgetChoice: Bool {
        (budgetDetail?.isOver ?? budget?.isOver ?? false) && budgetChoice == nil
            && (budgetDetail?.hasVariants ?? false)
    }
}

/// Budget part of a `GET /v1/trips` entry.
struct TripSummaryBudget: Decodable, Equatable, Sendable {
    let status: String?
    let budgetKzt: Int?
    let totalKzt: Int?

    enum CodingKeys: String, CodingKey {
        case status
        case budgetKzt = "budget_kzt"
        case totalKzt = "total_kzt"
    }
}

/// `GET /v1/trips` entry for the side panel.
struct TripSummary: Decodable, Equatable, Identifiable, Sendable {
    let id: UUID
    let startDate: String?
    let endDate: String?
    let days: Int?
    let budget: TripSummaryBudget?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, days, budget
        case startDate = "start_date"
        case endDate = "end_date"
        case updatedAt = "updated_at"
    }
}

struct TripSummaries: Decodable, Sendable {
    let items: [TripSummary]
}

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
