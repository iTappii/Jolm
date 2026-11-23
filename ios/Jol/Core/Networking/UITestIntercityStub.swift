#if DEBUG
import Foundation

/// Ш-62: the owner's scenario for UI tests and `-JolDemo` — Almaty → Shymbulak → Charyn → Kolsai (night in Saty) →
/// Almaty → Turkestan by plane. The chat turns are recorded SSE (`chat-icity-1…5.sse`; tags `icity1`…`icity5`, in the
/// demo "shymbulak" / "charyn" / "kolsai" / "turkestan" / "build"); this file is the finished plan with its two
/// transfer days and the nights, as the server's `GET /v1/trips/{id}` shows it (field names: SSOT §5.4, Ш-61/62).
enum IntercityStub {
    static let tripID = "99999999-9999-4999-8999-999999999999"

    private struct Stop {
        let id: String, name: String, category: String, lat: Double, lon: Double
    }

    private static let shymbulak = Stop(id: "1b000000-0000-4000-8000-000000000001", name: "Shymbulak",
                                        category: "mountain", lat: 43.1286, lon: 77.0807)
    private static let bazaar = Stop(id: "1a000000-0000-4000-8000-000000000005", name: "Green Bazaar",
                                     category: "market", lat: 43.2627, lon: 76.9535)
    private static let charyn = Stop(id: "1b000000-0000-4000-8000-000000000002", name: "Charyn Canyon",
                                     category: "nature", lat: 43.3500, lon: 79.0750)
    private static let kolsai = Stop(id: "1b000000-0000-4000-8000-000000000003", name: "Kolsai Lakes",
                                     category: "nature", lat: 42.9953, lon: 78.3267)
    private static let kokTobe = Stop(id: "1b000000-0000-4000-8000-000000000006", name: "Kok Tobe",
                                      category: "viewpoint", lat: 43.2336, lon: 76.9740)
    private static let mausoleum = Stop(id: "1b000000-0000-4000-8000-000000000004",
                                        name: "Khoja Ahmed Yasawi Mausoleum", category: "monument",
                                        lat: 43.2972, lon: 68.2706)

    private static func place(_ stop: Stop) -> String {
        "{\"id\":\"\(stop.id)\",\"name\":\"\(stop.name)\",\"name_lang\":\"en\",\"category\":\"\(stop.category)\","
            + "\"category_name\":\"\(stop.category.capitalized)\",\"lat\":\(stop.lat),\"lon\":\(stop.lon),"
            + "\"photo\":null}"
    }

    private static func item(
        _ id: String, _ stop: Stop, day: String, hours: (from: String, until: String), cost: Int
    ) -> String {
        "{\"id\":\"\(id)\",\"ord\":1,\"kind\":\"activity\",\"meal\":null,\"place\":\(place(stop)),"
            + "\"starts_at\":\"\(day)T\(hours.from):00+05:00\",\"ends_at\":\"\(day)T\(hours.until):00+05:00\","
            + "\"visit_min\":120,\"must_have\":true,\"est_cost_kzt\":\(cost),\"cost_assumed\":false,"
            + "\"hours_assumed\":false,\"rain_exposed\":false}"
    }

    private static func city(_ ru: String, _ en: String) -> String { "{\"ru\":\"\(ru)\",\"en\":\"\(en)\"}" }

    private static func overnight(
        _ ru: String, _ en: String, _ region: String, _ lat: Double, _ lon: Double
    ) -> String {
        "{\"city\":\(city(ru, en)),\"region\":\"\(region)\",\"lat\":\(lat),\"lon\":\(lon)}"
    }

    /// An intercity leg: `from` is nil when the transfer leaves from where the night was spent.
    private struct Transfer {
        let id: String
        var from: String?
        let to: String
        let depart: String
        let mode: String
        let seconds: Int
        let cities: (from: String, to: String)
        var approximate = false
        var price: (Int, Int)?
    }

    private static let cityNames = [
        "Almaty": city("Алматы", "Almaty"), "Saty": city("Саты", "Saty"), "Charyn": city("Чарын", "Charyn"),
        "Turkestan": city("Туркестан", "Turkestan"),
    ]

    private static func leg(_ transfer: Transfer) -> String {
        let prices = transfer.price.map { ",\"price_kzt_min\":\($0.0),\"price_kzt_max\":\($0.1)" } ?? ""
        let intercity = "{\"mode\":\"\(transfer.mode)\",\"from_city\":\(cityNames[transfer.cities.from] ?? "null"),"
            + "\"to_city\":\(cityNames[transfer.cities.to] ?? "null"),\"approximate\":\(transfer.approximate)\(prices)}"
        let from = transfer.from.map { "\"\($0)\"" } ?? "null"
        return "{\"id\":\"\(transfer.id)\",\"from_item_id\":\(from),\"to_item_id\":\"\(transfer.to)\","
            + "\"depart_at\":\"\(transfer.depart)\",\"travel_s\":\(transfer.seconds),\"estimated\":true,"
            + "\"chosen_mode\":\"\(transfer.mode)\",\"cost_kzt\":\(transfer.price?.0 ?? 0),\"options\":[],"
            + "\"intercity\":\(intercity)}"
    }

    private static func day(
        _ date: String, kind: String = "regular", items: [String], legs: [String] = [], night: String
    ) -> String {
        "{\"date\":\"\(date)\",\"kind\":\"\(kind)\",\"items\":[\(items.joined(separator: ","))],"
            + "\"legs\":[\(legs.joined(separator: ","))],\"overnight\":\(night)}"
    }

    /// `-JolDemo`: the demo phrase → the turn of this scenario ("shymbulak", "charyn", "kolsai", "turkestan"; "build"
    /// once the scenario is under way).
    static func demoTurn(_ lowered: String, underway: Bool) -> Int? {
        if lowered.contains("shymbulak") { return 1 }
        if lowered.contains("charyn") { return 2 }
        if lowered.contains("kolsai") { return 3 }
        if lowered.contains("turkestan") { return 4 }
        if underway, lowered.contains("build") || lowered.contains("route") || lowered.contains("ready") { return 5 }
        return nil
    }

    static func json(id: String) -> String {
        let almaty = overnight("Алматы", "Almaty", "kz-almaty", 43.2389, 76.8897)
        let days = [
            day("2026-12-05", items: [item("eeeeeeee-eeee-4eee-8eee-eeeeeeeeee01", shymbulak, day: "2026-12-05",
                                           hours: ("10:00", "14:00"), cost: 12000)], night: almaty),
            day("2026-12-06", items: [item("eeeeeeee-eeee-4eee-8eee-eeeeeeeeee02", bazaar, day: "2026-12-06",
                                           hours: ("10:00", "12:00"), cost: 8000)], night: almaty),
            day("2026-12-07", items: [
                item("eeeeeeee-eeee-4eee-8eee-eeeeeeeeee03", charyn, day: "2026-12-07", hours: ("10:00", "12:30"),
                     cost: 3000),
                item("eeeeeeee-eeee-4eee-8eee-eeeeeeeeee04", kolsai, day: "2026-12-07", hours: ("16:00", "18:00"),
                     cost: 2000),
            ], legs: [leg(Transfer(
                id: "dddddddd-dddd-4ddd-8ddd-dddddddddd11", from: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeee03",
                to: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeee04", depart: "2026-12-07T13:00:00+05:00", mode: "car",
                seconds: 12600, cities: (from: "Charyn", to: "Saty")))],
            night: overnight("Саты", "Saty", "kz-almaty", 43.0270, 78.3500)),
            day("2026-12-08", kind: "transfer", items: [
                item("eeeeeeee-eeee-4eee-8eee-eeeeeeeeee05", kokTobe, day: "2026-12-08", hours: ("17:00", "18:30"),
                     cost: 0)
            ], legs: [leg(Transfer(
                id: "dddddddd-dddd-4ddd-8ddd-dddddddddd12", to: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeee05",
                depart: "2026-12-08T09:00:00+05:00", mode: "car", seconds: 18000,
                cities: (from: "Saty", to: "Almaty")))], night: almaty),
            day("2026-12-09", kind: "transfer", items: [
                item("eeeeeeee-eeee-4eee-8eee-eeeeeeeeee06", mausoleum, day: "2026-12-09", hours: ("14:00", "16:30"),
                     cost: 2000)
            ], legs: [leg(Transfer(
                id: "dddddddd-dddd-4ddd-8ddd-dddddddddd13", to: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeee06",
                depart: "2026-12-09T08:00:00+05:00", mode: "plane", seconds: 7200,
                cities: (from: "Almaty", to: "Turkestan"), approximate: true, price: (18000, 35000)))],
            night: overnight("Туркестан", "Turkestan", "kz-turkestan", 43.2973, 68.2518)),
        ]
        return """
        {"id":"\(id)","chat_id":null,"version":1,"status":"active","start_date":"2026-12-05",\
        "end_date":"2026-12-09","budget_kzt":600000,"total_cost_kzt":410000,"budget_choice":null,\
        "weather_checked_at":null,"days":[\(days.joined(separator: ","))],"budget":{"budget_kzt":600000,\
        "status":"ok","total_kzt":410000,"remaining_kzt":190000,"shortfall_kzt":0,"breakdown":{"lodging_kzt":120000,\
        "entries_kzt":27000,"meals_kzt":0,"transport_kzt":263000,"events_kzt":0},"lodging":{"needed":true,\
        "nights":4,"cost_kzt":120000,"price_assumed":true,"options":[]},"variants":null,"choice":null},\
        "warnings":[],"must_have_unmet":[],"events":[]}
        """
    }
}
#endif
