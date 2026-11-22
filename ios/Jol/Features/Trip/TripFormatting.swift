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
