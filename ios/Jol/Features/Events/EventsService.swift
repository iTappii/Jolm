import Foundation

/// `GET /v1/events` (public): events overlapping a date window, optionally inside a bounding box.
struct EventsService: Sendable {
    let api: APIClient

    func events(from: String, to: String, bbox: GeoBounds? = nil) async throws -> [EventItem] {
        var query = [URLQueryItem(name: "from", value: from), URLQueryItem(name: "to", value: to)]
        if let bbox { query.append(URLQueryItem(name: "bbox", value: bbox.queryValue)) }
        let list: EventsList = try await api.send(.get("v1/events", query: query))
        return list.items
    }
}
