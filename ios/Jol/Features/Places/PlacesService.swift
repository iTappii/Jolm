import Foundation

/// Reads of the public places API (guest-accessible).
struct PlacesService: Sendable {
    /// Server limits: bbox ≤ 2° per axis, `limit` ≤ 1000.
    static let maxSpan = 2.0
    static let pageLimit = 1000

    let api: APIClient

    func places(in bounds: GeoBounds, category: String? = nil) async throws -> [PlaceSummary] {
        var query = [
            URLQueryItem(name: "bbox", value: bounds.queryValue),
            URLQueryItem(name: "limit", value: String(Self.pageLimit)),
        ]
        if let category { query.append(URLQueryItem(name: "category", value: category)) }
        let list: PlacesList = try await api.send(.get("v1/places", query: query))
        return list.items
    }

    func place(id: UUID) async throws -> PlaceDetail {
        try await api.send(.get("v1/places/\(id.uuidString.lowercased())"))
    }

    /// `GET /v1/geocode/reverse` (Ш-23c): public; 422 outside Almaty, 429 over the limit.
    func reverse(_ point: GeoPoint) async throws -> ReverseGeocode {
        let query = [
            URLQueryItem(name: "lat", value: String(format: "%.6f", point.lat)),
            URLQueryItem(name: "lon", value: String(format: "%.6f", point.lon)),
        ]
        return try await api.send(.get("v1/geocode/reverse", query: query))
    }

    func curatedRoutes() async throws -> [CuratedRouteSummary] {
        let list: CuratedRoutesList = try await api.send(.get("v1/curated-routes"))
        return list.items
    }

    func curatedRoute(id: UUID) async throws -> CuratedRouteDetail {
        try await api.send(.get("v1/curated-routes/\(id.uuidString.lowercased())"))
    }
}
