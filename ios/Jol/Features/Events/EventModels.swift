import CoreLocation
import Foundation

/// An event (`GET /v1/events`, the `events` of a trip and of a place card). `isAd` / `adLabel` come from the server:
/// whenever `isAd` is true the label («Реклама» / «Ad») must be shown next to the event (SSOT §5.1, §12). The server
/// never marks attractions or state places as ads; the app only renders the flag.
struct EventItem: Decodable, Equatable, Identifiable, Sendable {
    struct Venue: Decodable, Equatable, Sendable {
        let id: UUID
        let name: String
    }

    let id: UUID
    let title: String
    let description: String?
    let startsAt: String?
    let endsAt: String?
    let priceKzt: Int?
    let organizer: String?
    let category: String?
    let lat: Double
    let lon: Double
    let place: Venue?
    let isAd: Bool
    let adLabel: String?

    enum CodingKeys: String, CodingKey {
        case id, title, description, organizer, category, lat, lon, place
        case startsAt = "starts_at"
        case endsAt = "ends_at"
        case priceKzt = "price_kzt"
        case isAd = "is_ad"
        case adLabel = "ad_label"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(UUID.self, forKey: .id)
        title = try values.decodeIfPresent(String.self, forKey: .title) ?? ""
        description = try values.decodeIfPresent(String.self, forKey: .description)
        startsAt = try values.decodeIfPresent(String.self, forKey: .startsAt)
        endsAt = try values.decodeIfPresent(String.self, forKey: .endsAt)
        priceKzt = try values.decodeIfPresent(Int.self, forKey: .priceKzt)
        organizer = try values.decodeIfPresent(String.self, forKey: .organizer)
        category = try values.decodeIfPresent(String.self, forKey: .category)
        lat = try values.decode(Double.self, forKey: .lat)
        lon = try values.decode(Double.self, forKey: .lon)
        place = try? values.decodeIfPresent(Venue.self, forKey: .place)
        isAd = try values.decodeIfPresent(Bool.self, forKey: .isAd) ?? false
        adLabel = try values.decodeIfPresent(String.self, forKey: .adLabel)
    }

    var coordinate: CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: lat, longitude: lon) }

    /// The ad label to show: the server's text, else a default («Ad») when it flagged the event but sent none.
    var visibleAdLabel: String? {
        guard isAd else { return nil }
        if let adLabel, !adLabel.isEmpty { return adLabel }
        return "Ad"
    }

    /// "5 Dec, 19:00" / "5 Dec, 19:00–22:00" in the server's local (region) time.
    func whenText(locale: Locale) -> String? {
        guard let start = startsAt.flatMap(DirectionOption.parseDate) else { return nil }
        let formatter = DateFormatter()
        formatter.locale = locale
        formatter.timeZone = Region.current.timeZone
        formatter.setLocalizedDateFormatFromTemplate("d MMM")
        var text = formatter.string(from: start)
        formatter.setLocalizedDateFormatFromTemplate("HH:mm")
        text += ", " + formatter.string(from: start)
        if let end = endsAt.flatMap(DirectionOption.parseDate), end > start {
            text += "–" + formatter.string(from: end)
        }
        return text
    }
}

struct EventsList: Decodable, Sendable {
    let items: [EventItem]
}
