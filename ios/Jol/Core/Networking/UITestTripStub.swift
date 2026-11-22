#if DEBUG
import Foundation

/// Stub of the trips API for UI tests (`-JolStubAPI`): a three-day trip that is OVER budget (variants: drop places is
/// feasible, cheaper is not), with legs that carry transport options, and the edit endpoints (mode of a leg, budget
/// choice, remove a stop; the first stop is a must-have and needs `force`). State lives in the process: one test, one
/// process. Callers hold `ChatStub`'s lock.
enum TripStub {
    static let museumItem = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa01"
    static let cafeItem = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa02"
    static let dayTwoCafeItem = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa03"
    static let dayTwoMuseumItem = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaa04"
    static let legOne = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb02"
    static let legTwo = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbb04"

    /// Places a stop can be replaced with (Ш-55): id, name, category, offset from the centre.
    static let galleryID = "33333333-3333-4333-8333-000000000001"
    static let parkID = "33333333-3333-4333-8333-000000000002"
    static let closedID = "33333333-3333-4333-8333-000000000003"
    private struct Candidate {
        let id: String
        let name: String
        let category: String
        let dLat: Double
        let dLon: Double
        let price: Int?
        let meters: Int
    }

    private static let candidates = [
        Candidate(id: galleryID, name: "Fixture Gallery", category: "museum", dLat: 0.004, dLon: -0.003,
                  price: 2000, meters: 850),
        Candidate(id: parkID, name: "Fixture Park", category: "park", dLat: -0.006, dLon: 0.005, price: nil,
                  meters: 1400),
        Candidate(id: closedID, name: "Fixture Closed Place", category: "museum", dLat: 0.002, dLon: 0.002,
                  price: 500, meters: 300),
    ]

    private nonisolated(unsafe) static var replaced: [String: String] = [:]
    private nonisolated(unsafe) static var removed: Set<String> = []
    private nonisolated(unsafe) static var modes: [String: String] = [:]
    private nonisolated(unsafe) static var choice: String?
    private nonisolated(unsafe) static var version = 1

    static func answer(method: String, path: String, body: [String: Any], tripIDs: [String]) -> ChatStub.Answer? {
        let parts = path.split(separator: "/").map(String.init)  // v1 trips {id} [legs|items {x} {action}]
        guard parts.count >= 3, parts[1] == "trips", tripIDs.contains(parts[2]) else { return nil }
        let id = parts[2]
        switch (method, parts.count) {
        case ("GET", 3):
            return ChatStub.Answer(body: UITestSupport.isDemo ? DemoTrip.json(id: id) : json(id: id))
        case ("POST", 4) where parts[3] == "budget-choice":
            guard choice == nil else { return error(409, "budget_choice_unavailable") }
            choice = body["choice"] as? String
            if choice == "drop_places" { removed.insert(dayTwoMuseumItem) }
            version += 1
            return ChatStub.Answer(body: "{\"trip_id\":\"\(id)\",\"version\":\(version),\"budget\":{}}")
        case ("POST", 6) where parts[3] == "legs" && parts[5] == "mode":
            return setMode(id: id, legID: parts[4], body: body)
        case ("POST", 6) where parts[3] == "items" && parts[5] == "remove":
            return remove(id: id, itemID: parts[4], body: body)
        case ("GET", 6) where parts[3] == "items" && parts[5] == "alternatives":
            return alternatives()
        case ("POST", 6) where parts[3] == "items" && parts[5] == "replace":
            return replace(id: id, itemID: parts[4], body: body)
        default:
            return nil
        }
    }

    private static func setMode(id: String, legID: String, body: [String: Any]) -> ChatStub.Answer {
        let mode = (body["mode"] as? String) ?? "walk"
        guard ["walk", "bus", "taxi"].contains(mode) else { return error(422, "validation_error") }
        modes[legID] = mode
        version += 1
        let late = mode == "walk" ? 900 : 0
        return ChatStub.Answer(body: """
        {"trip_id":"\(id)","version":\(version),"leg":\(leg(legID)),"arrives_at":"2026-12-05T12:15:00+05:00",\
        "late_by_s":\(late),"changed_days":["2026-12-05"],"budget":\(summary())}
        """)
    }

    private static func remove(id: String, itemID: String, body: [String: Any]) -> ChatStub.Answer {
        if itemID == museumItem, (body["force"] as? Bool) != true {
            return error(409, "must_have", "This place is a must-have of your trip.")
        }
        removed.insert(itemID)
        version += 1
        return ChatStub.Answer(body: """
        {"trip_id":"\(id)","version":\(version),"action":"remove","changed_days":["2026-12-05"],\
        "budget":\(summary()),"dropped":[]}
        """)
    }

    private static func alternatives() -> ChatStub.Answer {
        let items = candidates.map { candidate in
            "{\"id\":\"\(candidate.id)\",\"name\":\"\(candidate.name)\",\"category\":\"\(candidate.category)\","
                + "\"lat\":\(Region.current.center.latitude + candidate.dLat),"
                + "\"lon\":\(Region.current.center.longitude + candidate.dLon),"
                + "\"price_kzt\":\(candidate.price.map(String.init) ?? "null"),\"distance_m\":\(candidate.meters)}"
        }
        return ChatStub.Answer(body: "{\"items\":[\(items.joined(separator: ","))]}")
    }

    /// The must-have museum needs `force`; the "closed" candidate never fits (409 `no_replacement`).
    private static func replace(id: String, itemID: String, body: [String: Any]) -> ChatStub.Answer {
        let target = (body["place_id"] as? String) ?? ""
        if itemID == museumItem, (body["force"] as? Bool) != true {
            return error(409, "must_have", "This place is a must-have of your trip.")
        }
        guard target != closedID else { return error(409, "no_replacement", "Nothing fits.") }
        guard candidates.contains(where: { $0.id == target }) else { return error(422, "validation_error") }
        replaced[itemID] = target
        version += 1
        return ChatStub.Answer(body: """
        {"trip_id":"\(id)","version":\(version),"action":"replace","changed_days":["2026-12-05"],\
        "budget":\(summary()),"replaced":{"item_id":"\(itemID)"},"replacement":{"item_id":"\(itemID)"},\
        "dropped":[]}
        """)
    }

    private static func error(_ status: Int, _ code: String, _ message: String = "stub") -> ChatStub.Answer {
        ChatStub.Answer(status: status, body: "{\"error\":{\"code\":\"\(code)\",\"message\":\"\(message)\"}}")
    }

    // MARK: - JSON

    private static var isOver: Bool { choice != "drop_places" }
    private static var total: Int { choice == "drop_places" ? 90_000 : 120_000 }

    private static func summary() -> String {
        let over = isOver
        return "{\"status\":\"\(over ? "over" : "ok")\",\"total_kzt\":\(total),\"remaining_kzt\":\(100_000 - total),"
            + "\"shortfall_kzt\":\(over ? total - 100_000 : 0)}"
    }

    private static func place(_ pid: String, _ name: String, _ category: String, _ dLat: Double, _ dLon: Double)
        -> String {
        "{\"id\":\"\(pid)\",\"name\":\"\(name)\",\"name_lang\":\"en\",\"category\":\"\(category)\","
            + "\"category_name\":\"\(category.capitalized)\",\"lat\":\(Region.current.center.latitude + dLat),"
            + "\"lon\":\(Region.current.center.longitude + dLon),\"photo\":null}"
    }

    private static func item(_ id: String, _ order: Int, _ place: String, _ time: String, day: String,
                             must: Bool = false, meal: String? = nil) -> String {
        "{\"id\":\"\(id)\",\"ord\":\(order),\"kind\":\"\(meal == nil ? "activity" : "meal")\","
            + "\"meal\":\(meal.map { "\"\($0)\"" } ?? "null"),\"place\":\(place),"
            + "\"starts_at\":\"\(day)T\(time):00+05:00\",\"ends_at\":\"\(day)T\(time):00+05:00\",\"visit_min\":60,"
            + "\"must_have\":\(must),\"est_cost_kzt\":3000,\"cost_assumed\":false,\"hours_assumed\":false,"
            + "\"rain_exposed\":false}"
    }

    private static let geometry: [String: [String: String]] = [
        legOne: ["walk": "_f`nqAoejwqC_yF??otLozD?ozDowH", "bus": "_f`nqAoejwqC_|BowH_vJozD_|B_yF",
                 "taxi": "_f`nqAoejwqC_vJotL_yFowH"],
        legTwo: ["walk": "_wsnqAosaxqCnzDnwHnzD??ntL~xF?", "bus": "_wsnqAosaxqC~{B~xF~uJnzD~{BnwH",
                 "taxi": "_wsnqAosaxqC~xFnwH~uJntL"],
    ]

    private static func option(_ leg: String, _ mode: String, seconds: Int, meters: Int, cost: Int) -> String {
        let recommended = mode == "bus"
        return "{\"mode\":\"\(mode)\",\"duration_s\":\(seconds).0,\"distance_m\":\(meters).0,\"cost_kzt_min\":\(cost),"
            + "\"cost_kzt_max\":\(cost),\"geometry\":\"\(geometry[leg]?[mode] ?? "")\",\"approximate\":false,"
            + "\"recommended\":\(recommended)}"
    }

    private static func leg(_ id: String) -> String {
        let from = id == legOne ? museumItem : dayTwoCafeItem
        let to = id == legOne ? cafeItem : dayTwoMuseumItem
        let day = id == legOne ? "2026-12-05" : "2026-12-06"
        let time = id == legOne ? "11:50" : "13:40"
        let chosen = modes[id] ?? "bus"
        let options = [
            option(id, "walk", seconds: 3000, meters: 3100, cost: 0),
            option(id, "bus", seconds: 780, meters: 2400, cost: 120),
            option(id, "taxi", seconds: 420, meters: 2300, cost: 1200),
        ]
        return "{\"id\":\"\(id)\",\"from_item_id\":\"\(from)\",\"to_item_id\":\"\(to)\","
            + "\"depart_at\":\"\(day)T\(time):00+05:00\",\"travel_s\":780,\"estimated\":false,"
            + "\"chosen_mode\":\"\(chosen)\",\"cost_kzt\":120,\"options\":[\(options.joined(separator: ","))]}"
    }

    private static func variants() -> String {
        guard isOver, choice == nil else { return "null" }
        return """
        {"drop_places":{"feasible":true,"total_kzt":90000,"saves_kzt":30000,"shortfall_kzt":0,"removed_count":1,\
        "removed":[{"id":"\(UITestSupport.centerPlaceID)","name":"Fixture Museum"}]},\
        "cheaper":{"feasible":false,"total_kzt":110000,"saves_kzt":10000,"shortfall_kzt":10000,"swaps_count":1,\
        "lodging_changed":false,"lodging_total_kzt":0,"swaps":[{"from":{"id":"\(UITestSupport.centerPlaceID)",\
        "name":"Fixture Museum"},"to":{"id":"\(UITestSupport.secondPlaceID)","name":"Fixture Cafe"}}]}}
        """
    }

    static func json(id: String) -> String {
        let museum = place(UITestSupport.centerPlaceID, "Fixture Museum", "museum", 0, 0)
        let cafe = place(UITestSupport.secondPlaceID, "Fixture Cafe", "coffee", 0.01, 0.012)
        let dayOne = [swapped(item(museumItem, 1, museum, "09:30", day: "2026-12-05", must: true), museum, museumItem),
                      swapped(item(cafeItem, 2, cafe, "12:00", day: "2026-12-05", meal: "lunch"), cafe, cafeItem)]
        let dayTwo = [swapped(item(dayTwoCafeItem, 1, cafe, "10:00", day: "2026-12-06"), cafe, dayTwoCafeItem),
                      swapped(item(dayTwoMuseumItem, 2, museum, "14:00", day: "2026-12-06"), museum,
                              dayTwoMuseumItem)]
        func swapped(_ item: String, _ original: String, _ itemID: String) -> String {
            guard let target = replaced[itemID], let new = candidates.first(where: { $0.id == target }) else {
                return item
            }
            let replacement = place(new.id, new.name, new.category, new.dLat, new.dLon)
            return item.replacingOccurrences(of: original, with: replacement)
        }
        func shown(_ items: [String], _ ids: [String]) -> String {
            zip(items, ids).filter { !removed.contains($0.1) }.map(\.0).joined(separator: ",")
        }
        func legs(_ leg: String, _ ids: [String]) -> String {
            ids.contains { removed.contains($0) } ? "" : self.leg(leg)
        }
        let days = """
        [{"date":"2026-12-05","items":[\(shown(dayOne, [museumItem, cafeItem]))],\
        "legs":[\(legs(legOne, [museumItem, cafeItem]))]},\
        {"date":"2026-12-06","items":[\(shown(dayTwo, [dayTwoCafeItem, dayTwoMuseumItem]))],\
        "legs":[\(legs(legTwo, [dayTwoCafeItem, dayTwoMuseumItem]))]},\
        {"date":"2026-12-07","items":[],"legs":[]}]
        """
        let over = isOver
        let budget = """
        {"budget_kzt":100000,"status":"\(over ? "over" : "ok")","total_kzt":\(total),\
        "remaining_kzt":\(100_000 - total),"shortfall_kzt":\(over ? total - 100_000 : 0),\
        "breakdown":{"lodging_kzt":0,"entries_kzt":40000,\
        "meals_kzt":50000,"transport_kzt":\(total - 90_000 + 0),"events_kzt":0},\
        "lodging":{"needed":false,"nights":0,"cost_kzt":0,"price_assumed":false,"options":[]},\
        "variants":\(variants()),"choice":\(choice.map { "\"\($0)\"" } ?? "null")}
        """
        return """
        {"id":"\(id)","chat_id":null,"version":\(version),"status":"active","start_date":"2026-12-05",\
        "end_date":"2026-12-07","budget_kzt":100000,"total_cost_kzt":\(total),\
        "budget_choice":\(choice.map { "\"\($0)\"" } ?? "null"),"weather_checked_at":null,"days":\(days),\
        "budget":\(budget),"warnings":[],"must_have_unmet":[],"events":[\(UITestSupport.eventsItemsJSON)]}
        """
    }

    static func listItem(id: String, chat: String) -> String {
        "{\"id\":\"\(id)\",\"chat_id\":\"\(chat)\",\"start_date\":\"2026-12-05\",\"end_date\":\"2026-12-07\","
            + "\"days\":3,\"version\":\(version),\"status\":\"active\",\"budget\":{\"status\":\"over\","
            + "\"budget_kzt\":100000,\"total_kzt\":\(total)},\"updated_at\":\"2026-11-21T10:00:00+05:00\"}"
    }
}
#endif
