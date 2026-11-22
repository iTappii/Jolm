#if DEBUG
import Foundation

/// `-JolDemo`: the trip built at the end of the live-route demo, made of the same three stops (the first one is the
/// alternative the person chose, if any), laid out over two days, within budget.
enum DemoTrip {
    private struct Stop {
        let id: String, name: String, category: String, lat: Double, lon: Double
    }

    private static let restaurants = [
        Stop(id: "1a000000-0000-4000-8000-000000000001", name: "Lan Zhou Noodle House", category: "restaurant",
             lat: 43.2330, lon: 76.8750),
        Stop(id: "1a000000-0000-4000-8000-000000000002", name: "Dragon Pearl", category: "restaurant",
             lat: 43.2455, lon: 76.8990),
        Stop(id: "1a000000-0000-4000-8000-000000000003", name: "Beijing Garden", category: "restaurant",
             lat: 43.2250, lon: 76.8960),
    ]
    private static let park = Stop(id: "1a000000-0000-4000-8000-000000000004", name: "First President's Park",
                                   category: "park", lat: 43.1849, lon: 76.8857)
    private static let bazaar = Stop(id: "1a000000-0000-4000-8000-000000000005", name: "Green Bazaar",
                                     category: "market", lat: 43.2627, lon: 76.9535)

    private static func place(_ stop: Stop) -> String {
        "{\"id\":\"\(stop.id)\",\"name\":\"\(stop.name)\",\"name_lang\":\"en\",\"category\":\"\(stop.category)\","
            + "\"category_name\":\"\(stop.category.capitalized)\",\"lat\":\(stop.lat),\"lon\":\(stop.lon),"
            + "\"photo\":null}"
    }

    /// When a stop is visited: the day and the start and end time.
    private struct Slot {
        let day: String, from: String, until: String
    }

    private static func item(_ id: String, _ order: Int, _ stop: Stop, _ slot: Slot, cost: Int,
                             meal: String? = nil) -> String {
        "{\"id\":\"\(id)\",\"ord\":\(order),\"kind\":\"\(meal == nil ? "activity" : "meal")\","
            + "\"meal\":\(meal.map { "\"\($0)\"" } ?? "null"),\"place\":\(place(stop)),"
            + "\"starts_at\":\"\(slot.day)T\(slot.from):00+05:00\",\"ends_at\":\"\(slot.day)T\(slot.until):00+05:00\","
            + "\"visit_min\":90,\"must_have\":true,\"est_cost_kzt\":\(cost),\"cost_assumed\":false,"
            + "\"hours_assumed\":false,\"rain_exposed\":false}"
    }

    static func json(id: String) -> String {
        let first = ChatStub.liveChoice(ord: 1).flatMap { chosen in restaurants.first { $0.id == chosen } }
            ?? restaurants[0]
        let lunch = "dddddddd-dddd-4ddd-8ddd-dddddddddd01"
        let walk = "dddddddd-dddd-4ddd-8ddd-dddddddddd02"
        let market = "dddddddd-dddd-4ddd-8ddd-dddddddddd03"
        let option = "{\"mode\":\"bus\",\"duration_s\":1080.0,\"distance_m\":8600.0,\"cost_kzt_min\":200,"
            + "\"cost_kzt_max\":200,\"geometry\":\"\",\"approximate\":true,\"recommended\":true}"
        let leg = "{\"id\":\"dddddddd-dddd-4ddd-8ddd-ddddddddd101\",\"from_item_id\":\"\(lunch)\","
            + "\"to_item_id\":\"\(walk)\",\"depart_at\":\"2026-12-05T14:00:00+05:00\",\"travel_s\":1080,"
            + "\"estimated\":true,\"chosen_mode\":\"bus\",\"cost_kzt\":200,\"options\":[\(option)]}"
        let lunchItem = item(lunch, 1, first, Slot(day: "2026-12-05", from: "12:30", until: "14:00"), cost: 6000,
                             meal: "lunch")
        let parkItem = item(walk, 2, park, Slot(day: "2026-12-05", from: "14:20", until: "16:30"), cost: 0)
        let bazaarItem = item(market, 1, bazaar, Slot(day: "2026-12-06", from: "10:00", until: "12:00"), cost: 8000)
        let days = """
        [{"date":"2026-12-05","items":[\(lunchItem),\(parkItem)],"legs":[\(leg)]},\
        {"date":"2026-12-06","items":[\(bazaarItem)],"legs":[]}]
        """
        return """
        {"id":"\(id)","chat_id":null,"version":1,"status":"active","start_date":"2026-12-05",\
        "end_date":"2026-12-06","budget_kzt":200000,"total_cost_kzt":14200,"budget_choice":null,\
        "weather_checked_at":null,"days":\(days),"budget":{"budget_kzt":200000,"status":"ok","total_kzt":14200,\
        "remaining_kzt":185800,"shortfall_kzt":0,"breakdown":{"lodging_kzt":0,"entries_kzt":0,"meals_kzt":14000,\
        "transport_kzt":200,"events_kzt":0},"lodging":{"needed":false,"nights":0,"cost_kzt":0,\
        "price_assumed":false,"options":[]},"variants":null,"choice":null},"warnings":[],"must_have_unmet":[],\
        "events":[]}
        """
    }
}
#endif
