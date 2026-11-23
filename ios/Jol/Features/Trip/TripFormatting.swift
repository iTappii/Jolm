import Foundation

/// Display helpers of the full route map.
enum TripFormatting {
    /// "120 000 ₸".
    static func kzt(_ amount: Int, locale: Locale) -> String {
        "\(amount.formatted(.number.locale(locale)))\u{00A0}\(Region.current.currencySymbol)"
    }

    /// "Day 2 · 6 Dec" parts: the date as the server wrote it (`2026-12-06`) in the app's language.
    static func dayDate(_ iso: String, locale: Locale) -> String {
        BriefFormatting.dates(start: iso, end: iso, locale: locale) ?? iso
    }

    /// "12 min" for a number of seconds.
    static func minutes(_ seconds: Int, language: String) -> String {
        DirectionsFormatting.clock(DirectionsFormatting.minutes(Double(seconds)), language: language)
    }
}

/// Texts of the intercity parts of a plan (Ш-62, SSOT §5.4 п. 7): the way, the approximate time, the price range, the
/// transfer day and the overnight line. Pure functions of the plan and a language code, so they are unit-tested.
enum IntercityFormatting {
    /// SF Symbol of a way between cities; an unknown way gets a generic icon.
    static func symbol(_ mode: IntercityMode?) -> String {
        switch mode {
        case .plane: "airplane"
        case .train: "tram.fill"
        case .bus: "bus.fill"
        case .car: "car.fill"
        case .taxi: "figure.wave"
        case .tour: "binoculars.fill"
        case nil: "arrow.left.arrow.right"
        }
    }

    /// «Flight», «Train», … (a String Catalog key), used as a title.
    static func title(_ mode: IntercityMode?, language: String) -> String {
        switch mode {
        case .plane: L10n.string("Flight", language: language)
        case .train: L10n.string("Train", language: language)
        case .bus: L10n.string("Intercity bus", language: language)
        case .car: L10n.string("My car", language: language)
        case .taxi: L10n.string("Taxi", language: language)
        case .tour: L10n.string("Organized tour", language: language)
        case nil: L10n.string("Transfer", language: language)
        }
    }

    /// "~2 h" / "≈ 11 h 30 min": whole transfer time, always approximate, hours from 60 minutes.
    static func duration(seconds: Int, language: String) -> String {
        "~" + TripFormatting.minutes(seconds, language: language)
    }

    /// "~18 000–35 000 ₸", "~18 000 ₸" (one price), `nil` without a price.
    static func priceRange(_ info: IntercityInfo, locale: Locale) -> String? {
        guard let low = info.priceKztMin ?? info.priceKztMax, low > 0 else { return nil }
        let high = max(info.priceKztMax ?? low, low)
        let symbol = Region.current.currencySymbol
        func number(_ value: Int) -> String { value.formatted(.number.locale(locale)) }
        let range = low == high ? number(low) : "\(number(low))–\(number(high))"
        return "~\(range)\u{00A0}\(symbol)"
    }

    /// «Travel to Turkestan» / «Переезд в Туркестан»; `nil` for a regular day or when the city is unknown.
    static func transferTitle(_ day: TripDay, language: String) -> String? {
        guard day.isTransfer else { return nil }
        guard let city = day.destinationCity?.text(language: language) else {
            return L10n.string("Travel day", language: language)
        }
        return String(format: L10n.string("Travel to %@", language: language), city)
    }

    /// «Overnight: Saty» / «Ночёвка: Саты»; `nil` when the plan does not say where the night is spent.
    static func overnightLine(_ day: TripDay, language: String) -> String? {
        guard let city = day.overnight?.city.text(language: language) else { return nil }
        return String(format: L10n.string("Overnight: %@", language: language), city)
    }

    /// What a transfer day's chip adds to «Day 2, 6 Dec»; empty for a regular day.
    static func chipSpoken(_ day: TripDay, language: String) -> String {
        guard day.isTransfer else { return "" }
        return day.intercityLeg.flatMap { spoken($0, language: language) }
            ?? transferTitle(day, language: language) ?? ""
    }

    /// «Flight to Turkestan, about 2 hours» — the spoken form of an intercity leg.
    static func spoken(_ leg: TripLeg, language: String) -> String? {
        guard let info = leg.intercity else { return nil }
        let title = title(info.mode, language: language)
        let city = info.toCity?.text(language: language)
        let head = city.map { String(format: L10n.string("%@ to %@", language: language), title, $0) } ?? title
        var parts = [head]
        if let seconds = leg.travelS {
            let time = LiveRouteFormatting.spokenApproximate(Double(seconds), language: language)
            parts.append(String(format: L10n.string("about %@", language: language), time))
        }
        if let price = priceRange(info, locale: Locale(identifier: language)) { parts.append(price) }
        return parts.joined(separator: ", ")
    }
}
