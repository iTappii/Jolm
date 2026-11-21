import Foundation

/// Calls of the trips API (Ш-37, Ш-38). Needs a session; the trip belongs to the account.
struct TripService: Sendable {
    let api: APIClient

    private static func path(_ id: UUID) -> String { id.uuidString.lowercased() }

    func list() async throws -> [TripSummary] {
        let query = [URLQueryItem(name: "limit", value: "50")]
        let page: TripSummaries = try await api.send(.get("v1/trips", query: query))
        return page.items
    }

    func trip(id: UUID) async throws -> TripOverview {
        try await api.send(.get("v1/trips/\(Self.path(id))"))
    }

    /// `GET /v1/trips/{id}/offline` (Ш-42). `etag` is the one of the saved copy: unchanged → `.notModified`.
    func offline(id: UUID, etag: String?) async throws -> ConditionalResult<OfflineTrip> {
        var endpoint = Endpoint.get("v1/trips/\(Self.path(id))/offline")
        endpoint.timeout = 30
        return try await api.sendConditional(endpoint, etag: etag)
    }

    func setMode(tripID: UUID, legID: UUID, mode: TransportMode) async throws -> LegModeChange {
        try await api.send(Endpoint.post(
            "v1/trips/\(Self.path(tripID))/legs/\(Self.path(legID))/mode", json: ["mode": mode.rawValue]
        ))
    }

    func chooseBudget(tripID: UUID, choice: String) async throws -> BudgetChoiceResult {
        try await api.send(Endpoint.post("v1/trips/\(Self.path(tripID))/budget-choice", json: ["choice": choice]))
    }

    func remove(tripID: UUID, itemID: UUID, force: Bool) async throws -> ItemRemoval {
        try await api.send(Endpoint.post(
            "v1/trips/\(Self.path(tripID))/items/\(Self.path(itemID))/remove", json: ["force": force]
        ))
    }
}
