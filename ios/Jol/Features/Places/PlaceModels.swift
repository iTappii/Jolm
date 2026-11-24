import CoreLocation
import Foundation

/// Pin on the map / item of a list (`GET /v1/places`, curated route items).
struct PlaceSummary: Decodable, Identifiable, Equatable, Sendable {
    let id: UUID
    let name: String
    let category: String?
    let kind: String
    let lat: Double
    let lon: Double
    let isPublic: Bool
    let isPartner: Bool
    let popularity: Int
    /// Logo of the venue (Ш-70): from a partner or the team, so mostly `nil`; the map then draws the category pin.
    var logoURL: String?
    /// Also in every item of the map list (Ш-70), so the card can show them before its detail loads.
    var rating: PlaceRating?
    var today: PlaceToday?
    var address: String?
    /// Set when this is a tapped address / point, not a place of ours (Ш-23c). Not part of the wire format.
    var tappedPoint: TappedPoint?

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    enum CodingKeys: String, CodingKey {
        case id, name, category, kind, lat, lon, popularity
        case isPublic = "is_public"
        case isPartner = "is_partner"
        case logoURL = "logo_url"
        case rating, today, address
    }
}

/// Average of the reviews that passed the automatic filter (Ш-70); `nil` on the card when there are none.
struct PlaceRating: Decodable, Equatable, Sendable {
    let average: Double
    let count: Int
}

/// Opening hours of the place for today in the region's time zone (Ш-70); `nil` when the hours are unknown.
struct PlaceToday: Decodable, Equatable, Sendable {
    let opens: String?
    let closes: String?
    let openNow: Bool?
    let open24h: Bool
    let closedToday: Bool

    enum CodingKeys: String, CodingKey {
        case opens, closes
        case openNow = "open_now"
        case open24h = "open_24h"
        case closedToday = "closed_today"
    }

    init(opens: String? = nil, closes: String? = nil, openNow: Bool? = nil, open24h: Bool = false,
         closedToday: Bool = false) {
        self.opens = opens
        self.closes = closes
        self.openNow = openNow
        self.open24h = open24h
        self.closedToday = closedToday
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        opens = try values.decodeIfPresent(String.self, forKey: .opens)
        closes = try values.decodeIfPresent(String.self, forKey: .closes)
        openNow = try values.decodeIfPresent(Bool.self, forKey: .openNow)
        open24h = try values.decodeIfPresent(Bool.self, forKey: .open24h) ?? false
        closedToday = try values.decodeIfPresent(Bool.self, forKey: .closedToday) ?? false
    }
}

struct PlacesList: Decodable, Sendable {
    let items: [PlaceSummary]
}

struct PlacePrices: Decodable, Equatable, Sendable {
    let entryPriceKzt: Int?
    let avgCheckKzt: Int?
    let pricePerNightKzt: Int?

    enum CodingKeys: String, CodingKey {
        case entryPriceKzt = "entry_price_kzt"
        case avgCheckKzt = "avg_check_kzt"
        case pricePerNightKzt = "price_per_night_kzt"
    }

    var isEmpty: Bool { entryPriceKzt == nil && avgCheckKzt == nil && pricePerNightKzt == nil }
}

struct PlacePhoto: Decodable, Equatable, Sendable, Identifiable {
    let id: UUID
    let storageKey: String
    /// Not sent by the server yet (`MEDIA_BASE_URL` is planned with Ш-44); used as soon as it appears.
    let url: String?

    enum CodingKeys: String, CodingKey {
        case id, url
        case storageKey = "storage_key"
    }
}

/// Card data (`GET /v1/places/{id}`). Only the fields the card shows are decoded.
struct PlaceDetail: Decodable, Identifiable, Equatable, Sendable {
    struct CategoryRef: Decodable, Equatable, Sendable {
        let slug: String
        let name: String
    }

    typealias Prices = PlacePrices
    struct Interval: Decodable, Equatable, Sendable {
        let opens: String
        let closes: String
    }

    struct DayHours: Decodable, Equatable, Sendable {
        let weekday: Int  // 0 = Monday … 6 = Sunday
        let intervals: [Interval]
    }

    typealias Photo = PlacePhoto

    let id: UUID
    let name: String
    let description: String?
    let category: CategoryRef?
    let kind: String
    let lat: Double
    let lon: Double
    let address: String?
    let website: String?
    let prices: Prices
    let typicalVisitMin: Int?
    let isPublic: Bool
    let isPartner: Bool
    let photos: [Photo]
    let hours: [DayHours]
    let openNow: Bool?
    /// `nil` while the place has fewer than five reports (Ш-47): the card then shows no crowd statistics.
    let crowd: CrowdBlock?
    /// Events at the place in the next 30 days (Ш-48).
    let events: [EventItem]?
    /// Partner booking (Ш-49): `nil` when the place has no partner — the booking button stays off.
    let booking: BookingInfo?
    /// Ш-70, all optional on the wire: older servers do not send them.
    let rating: PlaceRating?
    let today: PlaceToday?
    let logoURL: String?

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    enum CodingKeys: String, CodingKey {
        case id, name, description, category, kind, lat, lon, address, website, prices, photos, hours
        case crowd, events, booking, rating, today
        case logoURL = "logo_url"
        case typicalVisitMin = "typical_visit_min"
        case isPublic = "is_public"
        case isPartner = "is_partner"
        case openNow = "open_now"
    }
}

struct CuratedRouteSummary: Decodable, Identifiable, Equatable, Sendable {
    let id: UUID
    let title: String
    let description: String?
    let placesCount: Int

    enum CodingKeys: String, CodingKey {
        case id, title, description
        case placesCount = "places_count"
    }
}

struct CuratedRoutesList: Decodable, Sendable {
    let items: [CuratedRouteSummary]
}

struct CuratedRouteStop: Decodable, Identifiable, Equatable, Sendable {
    let place: PlaceSummary
    let ord: Int
    var id: UUID { place.id }

    init(from decoder: Decoder) throws {
        place = try PlaceSummary(from: decoder)
        ord = try decoder.container(keyedBy: CodingKeys.self).decode(Int.self, forKey: .ord)
    }

    enum CodingKeys: String, CodingKey { case ord }
}

struct CuratedRouteDetail: Decodable, Identifiable, Equatable, Sendable {
    let id: UUID
    let title: String
    let description: String?
    let items: [CuratedRouteStop]

    var stops: [PlaceSummary] { items.sorted { $0.ord < $1.ord }.map(\.place) }
}

/// Visible area in degrees. Server format: `west,south,east,north`.
struct GeoBounds: Equatable, Sendable {
    var west: Double
    var south: Double
    var east: Double
    var north: Double

    var queryValue: String { String(format: "%.5f,%.5f,%.5f,%.5f", west, south, east, north) }
    var width: Double { east - west }
    var height: Double { north - south }

    func contains(_ other: GeoBounds) -> Bool {
        other.west >= west && other.east <= east && other.south >= south && other.north <= north
    }

    func contains(lat: Double, lon: Double) -> Bool {
        lon >= west && lon <= east && lat >= south && lat <= north
    }

    /// Grows each side by `factor` of the size, clamped so neither axis exceeds `maxSpan` (the server limit is 2°).
    func padded(by factor: Double, maxSpan: Double) -> GeoBounds {
        let dx = width * factor
        let dy = height * factor
        var result = GeoBounds(west: west - dx, south: south - dy, east: east + dx, north: north + dy)
        if result.width > maxSpan {
            let mid = (west + east) / 2
            result.west = mid - maxSpan / 2
            result.east = mid + maxSpan / 2
        }
        if result.height > maxSpan {
            let mid = (south + north) / 2
            result.south = mid - maxSpan / 2
            result.north = mid + maxSpan / 2
        }
        return result
    }
}
