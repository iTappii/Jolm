import CoreLocation
import Foundation
import os

/// A region of the world Jol works in (SSOT §1, Ш-57): border, time zone, currency, languages, map centre and camera.
/// The shape is the `GET /v1/regions` contract; everything city-specific in the app comes from the current region.
struct Region: Codable, Equatable, Identifiable, Sendable {
    struct Name: Codable, Equatable, Sendable {
        let ru: String
        let en: String
    }

    struct Centre: Codable, Equatable, Sendable {
        let lat: Double
        let lon: Double
    }

    struct Camera: Codable, Equatable, Sendable {
        let zoom: Double
    }

    let id: String
    let name: Name
    let timezone: String
    let currency: String
    let languages: [String]
    let centre: Centre
    let camera: Camera
    /// `[west, south, east, north]`.
    let bbox: [Double]
    let isDefault: Bool

    enum CodingKeys: String, CodingKey {
        case id, name, timezone, currency, languages, centre, camera, bbox
        case isDefault = "is_default"
    }

    var timeZone: TimeZone { TimeZone(identifier: timezone) ?? .current }

    var center: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: centre.lat, longitude: centre.lon) }

    var zoom: Double { camera.zoom }

    /// "₸" for KZT, "$" for USD…; an unknown code is shown as is.
    var currencySymbol: String { Self.symbols[currency.uppercased()] ?? currency.uppercased() }

    /// Inside the region's `bbox`.
    func contains(lat: Double, lon: Double) -> Bool {
        guard bbox.count == 4 else { return true }
        return (bbox[0]...bbox[2]).contains(lon) && (bbox[1]...bbox[3]).contains(lat)
    }

    func displayName(language: String) -> String { language.hasPrefix("ru") ? name.ru : name.en }

    private static let symbols = ["KZT": "₸", "USD": "$", "EUR": "€", "RUB": "₽", "GBP": "£", "CNY": "¥"]

    // MARK: - Current region

    private static let storage = OSAllocatedUnfairLock<Region>(initialState: Region.builtIn)

    /// The region the app works in now. The built-in one until `RegionModel` loads another (offline, old server).
    static var current: Region {
        get { storage.withLock { $0 } }
        set { storage.withLock { $0 = newValue } }
    }
}

/// Parts of the `GET /v1/regions` answer.
struct RegionsResponse: Codable, Equatable, Sendable {
    let regions: [Region]

    /// The region marked `is_default`, else the first one; `nil` for an empty list.
    var preferred: Region? { regions.first { $0.isDefault } ?? regions.first }
}
