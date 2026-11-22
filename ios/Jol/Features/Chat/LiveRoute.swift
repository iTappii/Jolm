import CoreLocation
import Foundation

// The live route of a chat (Ш-54, SSOT §11.1): stops that appear on the map while the tourist is still talking,
// the alternatives the server found for each wish, and the straight legs between consecutive stops.

/// A place of the live route (a stop or one of its alternatives).
struct LivePlace: Decodable, Equatable, Identifiable, Sendable {
    let id: UUID
    let name: String
    let category: String?
    let lat: Double
    let lon: Double

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    /// The place card works on `PlaceSummary`.
    var summary: PlaceSummary {
        PlaceSummary(
            id: id, name: name, category: category, kind: "venue", lat: lat, lon: lon,
            isPublic: true, isPartner: false, popularity: 50
        )
    }
}

struct LiveStop: Decodable, Equatable, Identifiable, Sendable {
    let ord: Int
    let wish: String?
    let place: LivePlace
    let alternatives: [LivePlace]

    var id: Int { ord }

    enum CodingKeys: String, CodingKey { case ord, wish, place, alternatives }

    init(ord: Int, wish: String? = nil, place: LivePlace, alternatives: [LivePlace] = []) {
        self.ord = ord
        self.wish = wish
        self.place = place
        self.alternatives = alternatives
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        ord = try values.decode(Int.self, forKey: .ord)
        wish = try values.decodeIfPresent(String.self, forKey: .wish)
        place = try values.decode(LivePlace.self, forKey: .place)
        alternatives = try values.decodeIfPresent([LivePlace].self, forKey: .alternatives) ?? []
    }
}

enum LiveMode: String, Sendable {
    case walk, transit, car
}

struct LiveLeg: Decodable, Equatable, Sendable {
    let fromOrd: Int
    let toOrd: Int
    /// `nil` for a mode this app version does not know: the leg is still drawn, without a label.
    let mode: LiveMode?
    let durationS: Double
    let distanceM: Double?

    enum CodingKeys: String, CodingKey {
        case mode
        case fromOrd = "from_ord"
        case toOrd = "to_ord"
        case durationS = "duration_s"
        case distanceM = "distance_m"
    }

    init(fromOrd: Int, toOrd: Int, mode: LiveMode?, durationS: Double, distanceM: Double? = nil) {
        self.fromOrd = fromOrd
        self.toOrd = toOrd
        self.mode = mode
        self.durationS = durationS
        self.distanceM = distanceM
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        fromOrd = try values.decode(Int.self, forKey: .fromOrd)
        toOrd = try values.decode(Int.self, forKey: .toOrd)
        mode = (try values.decodeIfPresent(String.self, forKey: .mode)).flatMap(LiveMode.init(rawValue:))
        durationS = try values.decodeIfPresent(Double.self, forKey: .durationS) ?? 0
        distanceM = try values.decodeIfPresent(Double.self, forKey: .distanceM)
    }
}

/// The whole live route, always sent complete (SSE `live_route`, `GET /v1/chats/{id}`, the choose answer).
struct LiveRoute: Decodable, Equatable, Sendable {
    let stops: [LiveStop]
    let legs: [LiveLeg]

    init(stops: [LiveStop], legs: [LiveLeg]) {
        self.stops = stops.sorted { $0.ord < $1.ord }
        self.legs = legs
    }

    enum CodingKeys: String, CodingKey { case stops, legs }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        self.init(
            stops: try values.decodeIfPresent([LiveStop].self, forKey: .stops) ?? [],
            legs: try values.decodeIfPresent([LiveLeg].self, forKey: .legs) ?? []
        )
    }

    var isEmpty: Bool { stops.isEmpty }

    func stop(ord: Int) -> LiveStop? { stops.first { $0.ord == ord } }

    /// What the camera has to show: every stop and every alternative.
    var coordinates: [CLLocationCoordinate2D] {
        stops.flatMap { [$0.place.coordinate] + $0.alternatives.map(\.coordinate) }
    }

    /// 1-based number shown on the pin (the order of the stops on the route, not the server's `ord`).
    func number(of stop: LiveStop) -> Int {
        (stops.firstIndex { $0.ord == stop.ord } ?? 0) + 1
    }

    /// The legs between two stops that are both on the route, as drawable edges.
    var edges: [LiveEdge] {
        legs.compactMap { leg in
            guard let from = stop(ord: leg.fromOrd), let to = stop(ord: leg.toOrd) else { return nil }
            return LiveEdge(
                leg: leg, from: from.place.coordinate, to: to.place.coordinate,
                fromNumber: number(of: from), toNumber: number(of: to)
            )
        }
    }
}

struct LiveEdge: Equatable, Identifiable {
    let leg: LiveLeg
    let from: CLLocationCoordinate2D
    let to: CLLocationCoordinate2D
    let fromNumber: Int
    let toNumber: Int

    var id: String { "\(leg.fromOrd)-\(leg.toOrd)" }

    static func == (lhs: LiveEdge, rhs: LiveEdge) -> Bool {
        lhs.leg == rhs.leg && lhs.fromNumber == rhs.fromNumber && lhs.toNumber == rhs.toNumber
    }
}

// MARK: - Geometry

enum LiveRouteGeometry {
    /// Where the duration capsule of an edge sits (screen points): the middle of the edge, pushed `offset` points to
    /// the side that points up, so the capsule rides above the line and not on top of it. A vertical edge pushes right.
    static func labelCenter(from: CGPoint, to: CGPoint, offset: CGFloat) -> CGPoint {
        let middle = CGPoint(x: (from.x + to.x) / 2, y: (from.y + to.y) / 2)
        let dx = to.x - from.x
        let dy = to.y - from.y
        let length = hypot(dx, dy)
        guard length > 0.5 else { return CGPoint(x: middle.x, y: middle.y - offset) }
        // Unit normal; pick the one with the smaller y (up on the screen), right on a vertical edge.
        var nx = -dy / length
        var ny = dx / length
        if ny > 0 || (abs(ny) < 0.001 && nx < 0) {
            nx = -nx
            ny = -ny
        }
        return CGPoint(x: middle.x + nx * offset, y: middle.y + ny * offset)
    }
}

// MARK: - Text

enum LiveRouteFormatting {
    static func symbol(_ mode: LiveMode) -> String {
        switch mode {
        case .walk: "figure.walk"
        case .transit: "bus.fill"
        case .car: "car.fill"
        }
    }

    /// "12 min", "1 h 5 min" (minutes rounded, never below 1).
    static func duration(_ seconds: Double, language: String) -> String {
        DirectionsFormatting.clock(DirectionsFormatting.minutes(seconds), language: language)
    }

    /// Spoken «18 минут» / «1 hour, 5 minutes».
    static func spokenDuration(_ seconds: Double, language: String) -> String {
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Locale(identifier: language)
        let formatter = DateComponentsFormatter()
        formatter.calendar = calendar
        formatter.unitsStyle = .full
        formatter.allowedUnits = [.hour, .minute]
        formatter.zeroFormattingBehavior = .dropAll
        let minutes = DirectionsFormatting.minutes(seconds)
        return formatter.string(from: TimeInterval(minutes * 60)) ?? "\(minutes)"
    }

    static func modePhrase(_ mode: LiveMode?, language: String) -> String {
        switch mode {
        case .walk: L10n.string("on foot", language: language)
        case .transit: L10n.string("by public transport", language: language)
        case .car: L10n.string("by car", language: language)
        case nil: ""
        }
    }

    /// «От 1 до 2: на транспорте 18 минут».
    static func spokenEdge(_ edge: LiveEdge, language: String) -> String {
        let format = L10n.string("From %lld to %lld: %@ %@", language: language)
        let text = String(
            format: format, edge.fromNumber, edge.toNumber,
            modePhrase(edge.leg.mode, language: language),
            spokenDuration(edge.leg.durationS, language: language)
        )
        return text.trimmingCharacters(in: .whitespaces)
    }

    static func spokenStop(number: Int, name: String, language: String) -> String {
        String(format: L10n.string("Stop %lld: %@", language: language), number, name)
    }

    static func spokenAlternative(name: String, language: String) -> String {
        String(format: L10n.string("Alternative: %@", language: language), name)
    }
}
