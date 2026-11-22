import Foundation

/// Dates of a booking: the server writes ISO times with the region's offset; the screen shows them in the region's time.
enum BookingFormatting {
    private static func date(_ iso: String?) -> Date? {
        guard let iso else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: iso)
    }

    private static func format(_ date: Date, template: String, locale: Locale) -> String {
        let formatter = DateFormatter()
        formatter.locale = locale
        formatter.timeZone = Region.current.timeZone
        formatter.setLocalizedDateFormatFromTemplate(template)
        return formatter.string(from: date)
    }

    /// "5 Dec, 19:00" (a room: "5 Dec – 7 Dec"); nil for a food order, which has no time.
    static func when(_ booking: Booking, locale: Locale) -> String? {
        guard let start = date(booking.startsAt) else { return nil }
        if booking.kind == "room" {
            let from = format(start, template: "dMMM", locale: locale)
            guard let end = date(booking.endsAt) else { return from }
            return "\(from) – \(format(end, template: "dMMM", locale: locale))"
        }
        return "\(format(start, template: "dMMM", locale: locale)), \(format(start, template: "Hm", locale: locale))"
    }
}
