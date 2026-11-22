import Foundation

/// Display helpers for the place card.
enum PlaceFormatting {
    /// "≈ 1 500 ₸" (the symbol is the current region's currency).
    static func tenge(_ amount: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = "\u{00A0}"
        formatter.usesGroupingSeparator = true
        let number = formatter.string(from: NSNumber(value: amount)) ?? String(amount)
        return "≈ \(number)\u{00A0}\(Region.current.currencySymbol)"
    }

    /// Monday = 0 … Sunday = 6, in the region's time (the server computes "open now" in that zone too).
    static func weekday(of date: Date = Date()) -> Int {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = Region.current.timeZone
        return (calendar.component(.weekday, from: date) + 5) % 7
    }

    static func intervals(_ day: PlaceDetail.DayHours?) -> String? {
        guard let day, !day.intervals.isEmpty else { return nil }
        return day.intervals.map { "\($0.opens)–\($0.closes)" }.joined(separator: ", ")
    }

    static func today(_ hours: [PlaceDetail.DayHours], now: Date = Date()) -> String? {
        let weekday = weekday(of: now)
        return intervals(hours.first { $0.weekday == weekday })
    }

    static func visitDuration(minutes: Int) -> (hours: Int, minutes: Int) { (minutes / 60, minutes % 60) }
}
