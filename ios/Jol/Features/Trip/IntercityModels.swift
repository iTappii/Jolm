import CoreLocation
import Foundation

// Wire shapes of the intercity parts of a plan (Ш-62, SSOT §5.4): all optional, old plans decode without them.

/// A city name in both languages (`{"ru": "Туркестан", "en": "Turkestan"}`).
struct CityName: Decodable, Equatable, Sendable {
    let ru: String?
    let en: String?

    /// The name in the app's language, the other one when that is missing.
    func text(language: String) -> String? {
        let first = language == "ru" ? ru : en
        let second = language == "ru" ? en : ru
        return [first, second].compactMap { $0 }.first { !$0.isEmpty }
    }
}

/// Where the night of a day is spent (`overnight` of a plan day, Ш-62).
struct TripOvernight: Decodable, Equatable, Sendable {
    let city: CityName
    let region: String?
    let lat: Double?
    let lon: Double?

    var coordinate: CLLocationCoordinate2D? {
        guard let lat, let lon else { return nil }
        return CLLocationCoordinate2D(latitude: lat, longitude: lon)
    }
}

/// The ways between cities (SSOT §5.4 п. 5).
enum IntercityMode: String, Sendable {
    case plane, train, bus, car, taxi, tour
}

/// `intercity` of a leg: a transfer between two cities (Ш-62). Times are the leg's `travel_s`.
struct IntercityInfo: Decodable, Equatable, Sendable {
    /// What the server sent; `mode` is nil for a way this app version does not know (generic icon).
    let modeRaw: String?
    let fromCity: CityName?
    let toCity: CityName?
    let approximate: Bool
    let priceKztMin: Int?
    let priceKztMax: Int?

    enum CodingKeys: String, CodingKey {
        case approximate
        case modeRaw = "mode"
        case fromCity = "from_city"
        case toCity = "to_city"
        case priceKztMin = "price_kzt_min"
        case priceKztMax = "price_kzt_max"
    }

    init(
        mode: IntercityMode?, fromCity: CityName? = nil, toCity: CityName? = nil, approximate: Bool = false,
        priceKztMin: Int? = nil, priceKztMax: Int? = nil
    ) {
        modeRaw = mode?.rawValue
        self.fromCity = fromCity
        self.toCity = toCity
        self.approximate = approximate
        self.priceKztMin = priceKztMin
        self.priceKztMax = priceKztMax
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        modeRaw = try? values.decodeIfPresent(String.self, forKey: .modeRaw)
        fromCity = try? values.decodeIfPresent(CityName.self, forKey: .fromCity)
        toCity = try? values.decodeIfPresent(CityName.self, forKey: .toCity)
        approximate = (try? values.decodeIfPresent(Bool.self, forKey: .approximate)) ?? false
        priceKztMin = try? values.decodeIfPresent(Int.self, forKey: .priceKztMin)
        priceKztMax = try? values.decodeIfPresent(Int.self, forKey: .priceKztMax)
    }

    var mode: IntercityMode? { modeRaw.flatMap(IntercityMode.init(rawValue:)) }
}
