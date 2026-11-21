import Foundation

/// Bookings API (Ш-49): a request goes to the partner through the server; no payment in the app.
struct BookingService: Sendable {
    let api: APIClient

    /// `key` is the `Idempotency-Key`: a repeat of the same form (a retry after a lost answer) returns the first
    /// booking instead of making a second one.
    func create(_ request: BookingRequest, key: String) async throws -> Booking {
        var endpoint = try Endpoint.post("v1/bookings", json: request)
        endpoint.headers["Idempotency-Key"] = key
        return try await api.send(endpoint)
    }

    func booking(id: UUID) async throws -> Booking {
        try await api.send(.get("v1/bookings/\(id.uuidString.lowercased())"))
    }
}
