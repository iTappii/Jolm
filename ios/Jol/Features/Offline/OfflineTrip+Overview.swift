import Foundation

extension OfflineTrip {
    /// The saved copy in the shape the full route map draws (`GET /v1/trips/{id}`): days, stops with times, and for
    /// every leg one option — the way the plan chose, with its path. Nothing here needs a network. A stop whose place
    /// is missing from `places` is left out rather than shown without a name.
    func overview() -> TripOverview? {
        let dayObjects: [[String: Any]] = days.map { day in
            let items: [[String: Any]] = day.items.compactMap { item in
                guard let place = place(item.placeID) else { return nil }
                return Self.itemObject(item, place: place)
            }
            return ["date": day.date, "items": items, "legs": day.legs.map(Self.legObject)]
        }
        var object: [String: Any] = [
            "id": tripID.uuidString.lowercased(), "version": version,
            "start_date": startDate, "end_date": endDate, "days": dayObjects,
        ]
        object["budget_kzt"] = budgetKzt
        object["total_cost_kzt"] = totalCostKzt
        guard let data = try? JSONSerialization.data(withJSONObject: object) else { return nil }
        return try? JSONDecoder().decode(TripOverview.self, from: data)
    }

    private static func itemObject(_ item: OfflineItem, place: OfflinePlace) -> [String: Any] {
        var placeObject: [String: Any] = [
            "id": item.placeID.uuidString.lowercased(), "name": place.name, "lat": place.lat, "lon": place.lon,
        ]
        placeObject["category"] = place.category
        placeObject["category_name"] = place.categoryName
        var object: [String: Any] = ["id": item.id.uuidString.lowercased(), "kind": item.kind, "place": placeObject]
        object["ord"] = item.ord
        object["meal"] = item.meal
        object["starts_at"] = item.startsAt
        object["ends_at"] = item.endsAt
        object["visit_min"] = item.visitMin
        object["must_have"] = item.mustHave
        object["est_cost_kzt"] = item.estCostKzt
        return object
    }

    private static func legObject(_ leg: OfflineLeg) -> [String: Any] {
        var object: [String: Any] = [
            "id": leg.id.uuidString.lowercased(), "to_item_id": leg.toItemID.uuidString.lowercased(),
        ]
        object["from_item_id"] = leg.fromItemID?.uuidString.lowercased()
        object["depart_at"] = leg.departAt
        object["travel_s"] = leg.travelS
        object["estimated"] = leg.estimated
        object["chosen_mode"] = leg.mode
        object["cost_kzt"] = leg.costKzt
        var options: [[String: Any]] = []
        if let mode = leg.mode {
            let cost = leg.costKzt ?? 0
            options.append([
                "mode": mode, "duration_s": Double(leg.travelS ?? 0), "distance_m": Double(leg.distanceM ?? 0),
                "cost_kzt_min": cost, "cost_kzt_max": cost, "geometry": leg.geometry ?? "",
                "approximate": leg.geometry == nil || leg.estimated == true, "recommended": true,
            ])
        }
        object["options"] = options
        return object
    }
}
