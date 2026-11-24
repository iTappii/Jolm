import CoreLocation
import Foundation

/// A main sight of a city (`GET /v1/landmarks`, Ш-69, SSOT §13): a few per city, shown on the home map only once the
/// person zooms in to `minZoom`. `id` is the place's id, so it opens the usual place card.
struct Landmark: Decodable, Equatable, Identifiable, Sendable {
    let id: UUID
    let name: String
    let category: String?
    /// Key of the line drawing (`mosque`, `tv_tower`, …); unknown or missing → the category's pin.
    let icon: String?
    let lat: Double
    let lon: Double
    let minZoom: Double
    let rank: Int
    let region: String?

    enum CodingKeys: String, CodingKey {
        case id, name, category, icon, lat, lon, rank, region
        case minZoom = "min_zoom"
    }

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    /// The card and the map work on `PlaceSummary`; a landmark is a public sight.
    var summary: PlaceSummary {
        PlaceSummary(
            id: id, name: name, category: category, kind: "venue", lat: lat, lon: lon,
            isPublic: true, isPartner: false, popularity: 100
        )
    }

    /// A sight is drawn from its `minZoom` up; the city overview (below it) stays clean.
    func isVisible(atZoom zoom: Double) -> Bool { zoom >= minZoom }
}

struct LandmarksList: Decodable, Sendable {
    let landmarks: [Landmark]
}

/// `GET /v1/landmarks` (public, localized by `Accept-Language`).
struct LandmarksService: Sendable {
    let api: APIClient

    func landmarks() async throws -> [Landmark] {
        let list: LandmarksList = try await api.send(.get("v1/landmarks", authorized: false))
        return list.landmarks
    }
}
