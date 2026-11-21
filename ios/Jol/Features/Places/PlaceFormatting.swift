import Foundation

/// Display helpers for the place card.
enum PlaceFormatting {
    static let almaty = TimeZone(identifier: "Asia/Almaty") ?? .current

    /// "≈ 1 500 ₸"
    static func tenge(_ amount: Int) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.groupingSeparator = "\u{00A0}"
        formatter.usesGroupingSeparator = true
        return "≈ \(formatter.string(from: NSNumber(value: amount)) ?? String(amount))\u{00A0}₸"
    }

    /// Monday = 0 … Sunday = 6, in Almaty time (the server computes "open now" in that zone too).
    static func weekday(of date: Date = Date()) -> Int {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = almaty
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
