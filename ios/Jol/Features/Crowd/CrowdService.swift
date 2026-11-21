import Foundation

/// Check-in and crowd report (Ш-47). Both need a session; the current location is sent for the 200 m check and is
/// not stored by the server.
struct CrowdService: Sendable {
    let api: APIClient

    private static func path(_ id: UUID, _ action: String) -> String {
        "v1/places/\(id.uuidString.lowercased())/\(action)"
    }

    func checkIn(placeID: UUID, at point: GeoPoint) async throws -> CrowdRecorded {
        let body = CrowdBody(lat: point.lat, lon: point.lon, level: nil)
        return try await api.send(Endpoint.post(Self.path(placeID, "checkin"), json: body))
    }

    func report(placeID: UUID, level: CrowdReportLevel, at point: GeoPoint) async throws -> CrowdRecorded {
        try await api.send(Endpoint.post(
            Self.path(placeID, "crowd"), json: CrowdBody(lat: point.lat, lon: point.lon, level: level.rawValue)
        ))
    }
}

private struct CrowdBody: Encodable {
    let lat: Double
    let lon: Double
    let level: String?

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(lat, forKey: .lat)
        try container.encode(lon, forKey: .lon)
        try container.encodeIfPresent(level, forKey: .level)
    }

    enum CodingKeys: String, CodingKey { case lat, lon, level }
}
