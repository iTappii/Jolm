import CoreLocation
import Foundation

/// What the line under the place name says about today's hours (Ш-70, SSOT §6.1).
enum TodayLine: Equatable {
    enum State: Equatable { case open, closed, unknown }

    case open24h
    case closedToday
    case hours(opens: String, closes: String, state: State)
    /// Closed right now but opens later today.
    case opensAt(String)
}

extension PlaceFormatting {
    /// Minutes since midnight of `time` ("HH:mm"); `nil` if it is not a time.
    static func minutes(of time: String) -> Int? {
        let parts = time.split(separator: ":")
        guard parts.count >= 2, let hour = Int(parts[0]), let minute = Int(parts[1]),
              (0...24).contains(hour), (0..<60).contains(minute) else { return nil }
        return hour * 60 + minute
    }

    static func minutesNow(_ now: Date, timeZone: TimeZone = Region.current.timeZone) -> Int {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        return calendar.component(.hour, from: now) * 60 + calendar.component(.minute, from: now)
    }

    /// The server decides "open now"; the device only picks the wording. A place closed before its opening time says
    /// when it opens; after closing (or past midnight, `closes` < `opens`) it shows the hours and «closed».
    static func todayLine(_ today: PlaceToday, now: Date = Date(), timeZone: TimeZone = Region.current.timeZone)
        -> TodayLine? {
        if today.closedToday { return .closedToday }
        if today.open24h { return .open24h }
        guard let opens = today.opens, let closes = today.closes else { return nil }
        if today.openNow == false, let start = minutes(of: opens), minutesNow(now, timeZone: timeZone) < start {
            return .opensAt(opens)
        }
        let state: TodayLine.State = today.openNow.map { $0 ? .open : .closed } ?? .unknown
        return .hours(opens: opens, closes: closes, state: state)
    }

    /// Localized text of the line (outside SwiftUI, so it can be tested per language).
    static func text(for line: TodayLine, language: String) -> String {
        func tr(_ key: String, _ arguments: CVarArg...) -> String {
            String(format: L10n.string(key, language: language), arguments: arguments)
        }
        switch line {
        case .open24h: return tr("Open 24 hours")
        case .closedToday: return tr("Closed today")
        case .opensAt(let time): return tr("Closed · opens at %@", time)
        case .hours(let opens, let closes, let state):
            switch state {
            case .open: return tr("Today %@–%@ · Open", opens, closes)
            case .closed: return tr("Today %@–%@ · Closed", opens, closes)
            case .unknown: return tr("Today %@–%@", opens, closes)
            }
        }
    }

    // MARK: - Distance

    /// Straight-line distance from the person to the place, in metres.
    static func distance(from user: GeoPoint, to place: CLLocationCoordinate2D) -> Double {
        CLLocation(latitude: user.lat, longitude: user.lon)
            .distance(from: CLLocation(latitude: place.latitude, longitude: place.longitude))
    }

    /// «850 m» / «1.2 km» / «14 km»; metres are rounded to ten.
    static func distanceText(meters: Double, language: String) -> String {
        let locale = Locale(identifier: language)
        func number(_ value: Double, fraction: Int) -> String {
            value.formatted(.number.precision(.fractionLength(fraction)).grouping(.never).locale(locale))
        }
        if meters < 1000 {
            let rounded = max(10, (meters / 10).rounded() * 10)
            if rounded < 1000 {
                return String(format: L10n.string("%@ m", language: language), number(rounded, fraction: 0))
            }
        }
        let km = meters / 1000
        return String(format: L10n.string("%@ km", language: language), number(km, fraction: km < 10 ? 1 : 0))
    }

    static func distanceFromYou(meters: Double, language: String) -> String {
        String(format: L10n.string("%@ from you", language: language), distanceText(meters: meters, language: language))
    }
}

/// When the pins of ordinary places appear on the home map (Ш-70). Below `streetZoom` the map shows only the main
/// sights (Ш-69, from zoom ~12) — no circles, no clusters, no pins.
enum PlacePinVisibility {
    static let streetZoom = 15.0

    static func showsPins(atZoom zoom: Double) -> Bool { zoom >= streetZoom }
}
