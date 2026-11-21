import Foundation

/// What the person tapped on the map when it was not a pin (Ш-23c, SSOT §6.1): `GET /v1/geocode/reverse` answers with
/// a place of our base, an address / named building from our own OSM data, or the bare point.
enum ReverseGeocode: Decodable, Equatable, Sendable {
    case place(PlaceSummary)
    case address(street: String?, name: String?, point: GeoPoint)
    case point(GeoPoint)

    private enum CodingKeys: String, CodingKey {
        case kind, place, lat, lon, address, name
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        let lat = try values.decode(Double.self, forKey: .lat)
        let lon = try values.decode(Double.self, forKey: .lon)
        let point = GeoPoint(lat: lat, lon: lon)
        switch try values.decode(String.self, forKey: .kind) {
        case "place":
            self = .place(try values.decode(PlaceSummary.self, forKey: .place))
        case "address":
            self = .address(
                street: try values.decodeIfPresent(String.self, forKey: .address).flatMap(Self.clean),
                name: try values.decodeIfPresent(String.self, forKey: .name).flatMap(Self.clean),
                point: point
            )
        default:
            self = .point(point)
        }
    }

    private static func clean(_ text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}

/// A tapped point that is not a place of ours: the card shows its address (or the coordinates) and «Route», no
/// photos, reviews or favorites.
struct TappedPoint: Equatable, Sendable {
    /// Street and house number, when the data has them.
    let address: String?
    /// The point has neither an address nor a building name: only coordinates.
    let isBare: Bool
}

extension PlaceSummary {
    /// "43.25790, 76.94500": the title of a bare point (language-neutral, also what the navigator link gets).
    static func coordinateTitle(_ point: GeoPoint) -> String {
        String(format: "%.5f, %.5f", point.lat, point.lon)
    }

    /// An address / building / bare point as the "selected place" of the map. The id is made up for the tap: it is
    /// never sent anywhere (directions go by coordinates, see `DirectionsRequest`).
    static func tapped(_ result: ReverseGeocode) -> PlaceSummary? {
        switch result {
        case .place:
            return nil
        case .address(let street, let name, let point):
            let title = name ?? street ?? coordinateTitle(point)
            return PlaceSummary(
                id: UUID(), name: title, category: nil, kind: "address", lat: point.lat, lon: point.lon,
                isPublic: false, isPartner: false, popularity: 0,
                tappedPoint: TappedPoint(address: street, isBare: name == nil && street == nil)
            )
        case .point(let point):
            return PlaceSummary(
                id: UUID(), name: coordinateTitle(point), category: nil, kind: "point", lat: point.lat, lon: point.lon,
                isPublic: false, isPartner: false, popularity: 0,
                tappedPoint: TappedPoint(address: nil, isBare: true)
            )
        }
    }
}
