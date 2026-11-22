import CoreLocation
import Foundation

/// A point on the map as sent to / received from the API (`{"lat","lon"}`).
struct GeoPoint: Codable, Equatable, Sendable {
    let lat: Double
    let lon: Double

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    init(lat: Double, lon: Double) {
        self.lat = lat
        self.lon = lon
    }

    init(_ coordinate: CLLocationCoordinate2D) {
        self.init(lat: coordinate.latitude, lon: coordinate.longitude)
    }

    /// The area the server routes in: the current region's box.
    var isInServiceArea: Bool { Region.current.contains(lat: lat, lon: lon) }
}

/// `POST /v1/directions` body (SSOT §6): from the user's point to one place, or (Ш-23c) to a tapped point that is not a
/// place of ours. The server wants exactly one of `to_place_id` and `to`.
struct DirectionsRequest: Encodable, Sendable {
    let from: GeoPoint
    let toPlaceID: UUID?
    let toPoint: GeoPoint?

    init(from: GeoPoint, toPlaceID: UUID) {
        self.from = from
        self.toPlaceID = toPlaceID
        self.toPoint = nil
    }

    init(from: GeoPoint, toPoint: GeoPoint) {
        self.from = from
        self.toPlaceID = nil
        self.toPoint = toPoint
    }

    enum CodingKeys: String, CodingKey {
        case from
        case toPlaceID = "to_place_id"
        case toPoint = "to"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(from, forKey: .from)
        try container.encodeIfPresent(toPlaceID?.uuidString.lowercased(), forKey: .toPlaceID)
        try container.encodeIfPresent(toPoint, forKey: .toPoint)
    }
}

enum TransportMode: String, Decodable, CaseIterable, Sendable {
    case walk, scooter, bus, metro, taxi, car
}

struct DirectionStep: Decodable, Equatable, Sendable {
    let type: String
    let durationS: Double
    let distanceM: Double
    let geometry: String
    let routeRef: String?
    let kind: String?
    let fromName: String?
    let toName: String?

    enum CodingKeys: String, CodingKey {
        case type, geometry, kind
        case durationS = "duration_s"
        case distanceM = "distance_m"
        case routeRef = "route_ref"
        case fromName = "from_name"
        case toName = "to_name"
    }
}

/// One way to get to the place. Unavailable modes are simply not returned by the server.
/// Traffic / crowding on a path. The server has no source yet (`congestion: null`, SSOT §16.14), so this is only
/// decoded when the field is present; assumed shape: `{"level": "low" | "medium" | "high"}`. Anything else → `nil`
/// and the UI shows nothing (never invented data).
enum Congestion: String, Equatable, Sendable {
    case low, medium, high
}

/// One way to get to the place by one mode of transport.
///
/// Wire contract (Ш-22a): a flat list of options, several per mode possible, each with `group`, `variant`,
/// `arrive_at`, `congestion`. Every one of those four is optional here, so today's server (none of them) still works.
struct DirectionOption: Decodable, Equatable, Sendable {
    let mode: TransportMode
    let durationS: Double
    let durationSMin: Double?
    let durationSMax: Double?
    let distanceM: Double
    let costKztMin: Int
    let costKztMax: Int
    let geometry: String
    let steps: [DirectionStep]?
    let approximate: Bool
    let recommended: Bool
    /// Server-computed arrival (`depart_at` + duration). `nil` until Ш-22a: the UI then uses request time + duration.
    let arriveAt: Date?
    let congestion: Congestion?
    /// Carousel page the server put the option on ("transit" for bus and metro); `nil` → derived from the mode.
    let group: String?
    /// 0 = the optimal variant within its group, then 1, 2; `nil` (old server) → 0.
    let variant: Int?

    enum CodingKeys: String, CodingKey {
        case mode, geometry, steps, approximate, recommended, congestion, group, variant
        case durationS = "duration_s"
        case durationSMin = "duration_s_min"
        case durationSMax = "duration_s_max"
        case distanceM = "distance_m"
        case costKztMin = "cost_kzt_min"
        case costKztMax = "cost_kzt_max"
        case arriveAt = "arrive_at"
    }

    static func decode(_ values: KeyedDecodingContainer<CodingKeys>) throws -> Self {
        Self(
            mode: try values.decode(TransportMode.self, forKey: .mode),
            durationS: try values.decode(Double.self, forKey: .durationS),
            durationSMin: try values.decodeIfPresent(Double.self, forKey: .durationSMin),
            durationSMax: try values.decodeIfPresent(Double.self, forKey: .durationSMax),
            distanceM: try values.decode(Double.self, forKey: .distanceM),
            costKztMin: try values.decode(Int.self, forKey: .costKztMin),
            costKztMax: try values.decode(Int.self, forKey: .costKztMax),
            geometry: try values.decode(String.self, forKey: .geometry),
            steps: try values.decodeIfPresent([DirectionStep].self, forKey: .steps),
            approximate: try values.decodeIfPresent(Bool.self, forKey: .approximate) ?? false,
            recommended: try values.decodeIfPresent(Bool.self, forKey: .recommended) ?? false,
            arriveAt: (try? values.decodeIfPresent(String.self, forKey: .arriveAt)).flatMap { $0 }
                .flatMap(Self.parseDate),
            congestion: congestion(values),
            group: try values.decodeIfPresent(String.self, forKey: .group),
            variant: try values.decodeIfPresent(Int.self, forKey: .variant)
        )
    }

    private static func congestion(_ values: KeyedDecodingContainer<CodingKeys>) -> Congestion? {
        struct Body: Decodable { let level: String? }
        guard let body = try? values.decodeIfPresent(Body.self, forKey: .congestion), let level = body.level else {
            return nil
        }
        return Congestion(rawValue: level.lowercased())
    }

    static func parseDate(_ text: String) -> Date? {
        let plain = ISO8601DateFormatter()
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return plain.date(from: text) ?? fractional.date(from: text)
    }

    /// Line to draw (empty if the geometry is malformed).
    var line: [CLLocationCoordinate2D] { Polyline.decode(geometry) }

    /// Route numbers of the transit rides in order ("62 → 1"), shown next to bus / metro.
    var transitRef: String? {
        let refs = (steps ?? []).filter { $0.type == "ride" }.compactMap(\.routeRef).filter { !$0.isEmpty }
        return refs.isEmpty ? nil : refs.joined(separator: " → ")
    }
}

extension DirectionOption {
    // In an extension so the memberwise initializer stays available.
    init(from decoder: Decoder) throws {
        self = try Self.decode(try decoder.container(keyedBy: CodingKeys.self))
    }
}

/// `POST /v1/directions` answer: `{"options": [...]}` (Ш-22a contract) or, as today's server still sends it,
/// a bare array of options.
struct DirectionsPayload: Decodable, Sendable {
    let options: [DirectionOption]

    private enum Keys: String, CodingKey { case options }

    init(from decoder: Decoder) throws {
        if let keyed = try? decoder.container(keyedBy: Keys.self), keyed.contains(.options) {
            options = try keyed.decode([DirectionOption].self, forKey: .options)
        } else {
            options = try [DirectionOption](from: decoder)
        }
    }
}

/// One page of the carousel: every way of one kind of transport (bus and metro share the public transport page).
struct TransportPage: Equatable, Sendable, Identifiable {
    /// Carousel order (SSOT §6.1): walk → public transport → taxi → scooter → own car.
    enum Kind: Int, CaseIterable, Comparable, Sendable {
        case walk, transit, taxi, scooter, car

        static func < (lhs: Self, rhs: Self) -> Bool { lhs.rawValue < rhs.rawValue }

        /// `group` as the server names it; unknown → the mode's own page.
        init(group: String?, mode: TransportMode) {
            switch group {
            case "walk": self = .walk
            case "transit": self = .transit
            case "taxi": self = .taxi
            case "scooter": self = .scooter
            case "car": self = .car
            default: self.init(mode)
            }
        }

        init(_ mode: TransportMode) {
            switch mode {
            case .walk: self = .walk
            case .bus, .metro: self = .transit
            case .taxi: self = .taxi
            case .scooter: self = .scooter
            case .car: self = .car
            }
        }

        var slug: String {
            switch self {
            case .walk: "walk"
            case .transit: "transit"
            case .taxi: "taxi"
            case .scooter: "scooter"
            case .car: "car"
            }
        }
    }

    /// Variants per page the UI shows (the server is expected to send up to 3; transit can have more today).
    static let maxVariants = 4

    let kind: Kind
    /// First = optimal.
    let variants: [DirectionOption]

    var id: Kind { kind }

    /// Groups options into pages in carousel order; groups the server did not return give no page.
    /// Within a page options are ordered by `variant` (0 = optimal; missing → 0), then by duration.
    static func pages(from options: [DirectionOption]) -> [TransportPage] {
        Kind.allCases.compactMap { kind in
            let variants = options.filter { Kind(group: $0.group, mode: $0.mode) == kind }.sorted {
                ($0.variant ?? 0, $0.durationS) < ($1.variant ?? 0, $1.durationS)
            }
            return variants.isEmpty ? nil : TransportPage(kind: kind, variants: Array(variants.prefix(maxVariants)))
        }
    }

    var fastest: DirectionOption? { variants.min { $0.durationS < $1.durationS } }
}

/// A polyline on the map and whether it is the chosen variant.
struct DirectionLine: Equatable {
    let coordinates: [CLLocationCoordinate2D]
    let selected: Bool

    static func == (lhs: Self, rhs: Self) -> Bool {
        lhs.selected == rhs.selected && lhs.coordinates.count == rhs.coordinates.count
            && zip(lhs.coordinates, rhs.coordinates).allSatisfy {
                $0.latitude == $1.latitude && $0.longitude == $1.longitude
            }
    }
}
