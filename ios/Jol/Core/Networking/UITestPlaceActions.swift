#if DEBUG
import CoreLocation
import Foundation

/// Stub of the events, check-in / crowd report and booking endpoints for UI tests (`-JolStubAPI`).
/// - `GET /v1/events`: a promoted event and an ordinary one.
/// - `POST /v1/places/{id}/checkin|crowd`: 401 without a session; 422 `too_far_from_place` beyond 200 m of the
///   place; a repeat of the same action for the same place answers `recorded: false`; the report "empty" gets 429.
/// - `POST /v1/bookings`: 201, `confirmed` (a note with "pending" gives `pending`, with "full" a 409);
///   `GET /v1/bookings/{id}`: `confirmed`.
/// - `GET /v1/bookings` (Ш-55): three bookings of the stub user (a table at the cafe, tickets at the museum waiting
///   for the venue, and a table whose date has passed); `POST /v1/bookings/{id}/cancel`: `cancelled`, or 409
///   `not_cancellable` for the passed one and for one already cancelled.
enum UITestPlaceActions {
    struct Answer {
        var status = 200
        var headers: [String: String] = [:]
        var body: String
    }

    private static let lock = NSLock()
    private nonisolated(unsafe) static var recorded: Set<String> = []
    private nonisolated(unsafe) static var cancelled: Set<String> = []

    static let tableBookingID = "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1"
    static let ticketBookingID = "a2a2a2a2-a2a2-4a2a-8a2a-a2a2a2a2a2a2"
    static let pastBookingID = "a3a3a3a3-a3a3-4a3a-8a3a-a3a3a3a3a3a3"

    private struct Seeded {
        let id: String
        let placeID: String
        let placeName: String
        let kind: String
        let status: String
        let party: Int
        let start: String
    }

    private static let seeded = [
        Seeded(id: tableBookingID, placeID: UITestSupport.secondPlaceID, placeName: "Fixture Cafe", kind: "table",
               status: "confirmed", party: 2, start: "2026-12-06T19:00:00+05:00"),
        Seeded(id: ticketBookingID, placeID: UITestSupport.centerPlaceID, placeName: "Fixture Museum", kind: "ticket",
               status: "pending", party: 3, start: "2026-12-07T11:00:00+05:00"),
        Seeded(id: pastBookingID, placeID: UITestSupport.secondPlaceID, placeName: "Fixture Cafe", kind: "table",
               status: "confirmed", party: 4, start: "2026-11-01T20:00:00+05:00"),
    ]

    private static func seededJSON(_ entry: Seeded) -> String {
        let status = cancelled.contains(entry.id) ? "cancelled" : entry.status
        return """
        {"id":"\(entry.id)","place":{"id":"\(entry.placeID)","name":"\(entry.placeName)"},"kind":"\(entry.kind)",\
        "status":"\(status)","party_size":\(entry.party),"starts_at":"\(entry.start)","ends_at":null,\
        "event_id":null,"note":null,"created_at":"2026-11-20T10:00:00+05:00",\
        "updated_at":"2026-11-20T10:00:00+05:00"}
        """
    }

    static func answer(method: String, path: String, payload: [String: Any], signedIn: Bool) -> Answer? {
        if method == "GET", path == "/v1/events" {
            return Answer(body: "{\"items\":[\(UITestSupport.eventsItemsJSON)]}")
        }
        if method == "POST", path.hasPrefix("/v1/places/") {
            let parts = path.split(separator: "/").map(String.init)
            if parts.count == 4, parts[3] == "checkin" || parts[3] == "crowd" {
                return crowd(placeID: parts[2], action: parts[3], payload: payload, signedIn: signedIn)
            }
        }
        if let content = UITestContent.answer(method: method, path: path, payload: payload, signedIn: signedIn) {
            return Answer(status: content.status, headers: content.headers, body: content.body)
        }
        if path == "/v1/bookings" || path.hasPrefix("/v1/bookings/") {
            return bookings(method: method, path: path, payload: payload, signedIn: signedIn)
        }
        return nil
    }

    private static func failure(_ status: Int, _ code: String, headers: [String: String] = [:]) -> Answer {
        Answer(status: status, headers: headers, body: "{\"error\":{\"code\":\"\(code)\",\"message\":\"stub\"}}")
    }

    private static func crowd(placeID: String, action: String, payload: [String: Any], signedIn: Bool) -> Answer {
        guard signedIn else { return failure(401, "unauthorized") }
        let second = placeID == UITestSupport.secondPlaceID
        let target = CLLocation(
            latitude: Region.current.center.latitude + (second ? 0.01 : 0),
            longitude: Region.current.center.longitude + (second ? 0.012 : 0)
        )
        let here = CLLocation(latitude: payload["lat"] as? Double ?? 0, longitude: payload["lon"] as? Double ?? 0)
        let distance = Int(here.distance(from: target))
        guard distance <= 200 else { return failure(422, "too_far_from_place") }
        if (payload["level"] as? String) == "empty" {
            return failure(429, "rate_limited", headers: ["Retry-After": "120"])
        }
        lock.lock(); defer { lock.unlock() }
        let fresh = recorded.insert("\(placeID)/\(action)").inserted
        return Answer(body: "{\"recorded\":\(fresh),\"distance_m\":\(distance)}")
    }

    /// The list, a seeded booking and its cancellation.
    private static func ownBookings(method: String, path: String) -> Answer? {
        let parts = path.split(separator: "/").map(String.init)  // v1 bookings [{id} [cancel]]
        lock.lock(); defer { lock.unlock() }
        if method == "GET", parts.count == 2 {
            let items = seeded.map(seededJSON).joined(separator: ",")
            return Answer(body: "{\"items\":[\(items)],\"next_cursor\":null}")
        }
        guard parts.count >= 3, let entry = seeded.first(where: { $0.id == parts[2] }) else { return nil }
        if method == "GET", parts.count == 3 { return Answer(body: seededJSON(entry)) }
        guard method == "POST", parts.count == 4, parts[3] == "cancel" else { return nil }
        guard entry.id != pastBookingID, !cancelled.contains(entry.id) else { return failure(409, "not_cancellable") }
        cancelled.insert(entry.id)
        return Answer(body: seededJSON(entry))
    }

    private static func bookings(method: String, path: String, payload: [String: Any], signedIn: Bool) -> Answer {
        guard signedIn else { return failure(401, "unauthorized") }
        if let answer = ownBookings(method: method, path: path) { return answer }
        let note = (payload["note"] as? String)?.lowercased() ?? ""
        if method == "POST", note.contains("full") { return failure(409, "booking_unavailable") }
        let status = method == "POST" && note.contains("pending") ? "pending" : "confirmed"
        let kind = (payload["kind"] as? String) ?? "table"
        let party = (payload["party_size"] as? Int) ?? 2
        let start = (payload["starts_at"] as? String).map { "\"\($0)\"" } ?? "null"
        let body = """
        {"id":"12121212-1212-4212-8212-121212121212","place":{"id":"\(UITestSupport.secondPlaceID)",\
        "name":"Fixture Cafe"},"kind":"\(kind)","status":"\(status)","party_size":\(party),"starts_at":\(start),\
        "ends_at":null,"event_id":null,"note":null,"created_at":"2026-11-21T10:00:00+05:00",\
        "updated_at":"2026-11-21T10:00:00+05:00"}
        """
        return Answer(status: method == "POST" ? 201 : 200, body: body)
    }
}
#endif
