import Foundation
import SwiftUI

/// Display helpers for the directions list: icon, time, price.
enum DirectionsFormatting {
    static func symbol(_ mode: TransportMode) -> String {
        switch mode {
        case .walk: "figure.walk"
        case .scooter: "scooter"
        case .bus: "bus.fill"
        case .metro: "tram.fill"
        case .taxi: "car.side.fill"
        case .car: "car.fill"
        }
    }

    static func title(_ mode: TransportMode) -> LocalizedStringKey {
        switch mode {
        case .walk: "Walk"
        case .scooter: "Scooter"
        case .bus: "Bus"
        case .metro: "Metro"
        case .taxi: "Taxi"
        case .car: "My car"
        }
    }

    /// Whole minutes, never below 1 ("1 min" for a 20-second hop).
    static func minutes(_ seconds: Double) -> Int { max(1, Int((seconds / 60).rounded())) }

    /// "18 min", "1 h 05 min", "12–20 min" for a range. Units come from the String Catalog.
    static func duration(_ option: DirectionOption, language: String) -> String {
        let low = option.durationSMin.map(minutes)
        let high = option.durationSMax.map(minutes)
        let base: String
        if let low, let high, high > low {
            base = "\(low)–\(clock(high, language: language))"
        } else {
            base = clock(minutes(option.durationS), language: language)
        }
        return option.approximate ? "≈ \(base)" : base
    }

    static func clock(_ totalMinutes: Int, language: String) -> String {
        let hourUnit = L10n.string("h", language: language)
        let minuteUnit = L10n.string("min", language: language)
        if totalMinutes >= 60 {
            let rest = totalMinutes % 60
            let hours = "\(totalMinutes / 60) \(hourUnit)"
            return rest == 0 ? hours : "\(hours) \(rest) \(minuteUnit)"
        }
        return "\(totalMinutes) \(minuteUnit)"
    }

    /// "Free", "≈ 400 ₸" or "800–1 400 ₸".
    static func price(_ option: DirectionOption, language: String) -> String {
        let low = option.costKztMin
        let high = max(option.costKztMax, low)
        if high == 0 { return L10n.string("Free", language: language) }
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = "\u{00A0}"
        func number(_ value: Int) -> String { formatter.string(from: NSNumber(value: value)) ?? String(value) }
        if low == high { return "≈ \(number(low))\u{00A0}₸" }
        return "\(number(low))–\(number(high))\u{00A0}₸"
    }

    /// "650 m" / "5.2 km".
    static func distance(_ meters: Double, language: String) -> String {
        if meters < 1000 { return "\(Int((meters / 10).rounded()) * 10) \(L10n.string("m", language: language))" }
        return String(format: "%.1f %@", meters / 1000, L10n.string("km", language: language))
    }

    static func pageTitle(_ kind: TransportPage.Kind) -> LocalizedStringKey {
        switch kind {
        case .walk: "Walk"
        case .transit: "Public transport"
        case .taxi: "Taxi"
        case .scooter: "Scooter"
        case .car: "My car"
        }
    }

    /// Arrival clock time in Almaty ("14:35"): the server's `arrive_at`, else departure + duration.
    static func arrival(_ option: DirectionOption, departedAt: Date) -> String {
        let date = option.arriveAt ?? departedAt.addingTimeInterval(option.durationS)
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = PlaceFormatting.almaty
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }

    /// Traffic (roads) or crowding (transit); `nil` when the server sent none or the mode has no such notion.
    static func congestion(_ option: DirectionOption) -> LocalizedStringKey? {
        guard let level = option.congestion else { return nil }
        switch option.mode {
        case .taxi, .car:
            switch level {
            case .low: return "Light traffic"
            case .medium: return "Moderate traffic"
            case .high: return "Heavy traffic"
            }
        case .bus, .metro:
            switch level {
            case .low: return "Not crowded"
            case .medium: return "Fairly busy"
            case .high: return "Crowded"
            }
        case .walk, .scooter:
            return nil
        }
    }
}
