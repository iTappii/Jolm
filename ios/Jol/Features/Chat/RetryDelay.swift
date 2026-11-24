import Foundation

/// A "try again in …" wait as people read it: seconds under a minute, else minutes, else hours and minutes
/// ("1 h 5 min"), never tens of thousands of seconds. Localized by `locale`.
enum RetryDelay {
    static func text(_ seconds: Int, locale: Locale = .current) -> String {
        let formatter = DateComponentsFormatter()
        formatter.unitsStyle = .abbreviated
        formatter.maximumUnitCount = 2
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = locale
        formatter.calendar = calendar
        if seconds < 60 {
            formatter.allowedUnits = [.second]
            return formatter.string(from: TimeInterval(max(1, seconds))) ?? "\(seconds) s"
        }
        let minutes = (seconds + 59) / 60
        formatter.allowedUnits = minutes < 60 ? [.minute] : [.hour, .minute]
        return formatter.string(from: TimeInterval(minutes * 60)) ?? "\(minutes) min"
    }
}
