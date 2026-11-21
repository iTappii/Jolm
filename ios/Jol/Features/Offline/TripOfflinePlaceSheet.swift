import SwiftUI

/// What the card of a stop of the saved copy shows: the place as the server sent it for offline use, and when the
/// plan puts the visit.
struct OfflinePlaceCard: Identifiable, Equatable {
    let item: TripDayItem
    let place: OfflinePlace
    /// The day of the visit (`2026-12-05`), for the opening hours of that weekday.
    let dayDate: String

    var id: UUID { item.id }

    /// Opening hours of the visit's weekday as "10:00–18:00, 19:00–22:00"; `nil` when the saved copy has none.
    var hoursText: String? {
        guard let weekday = Self.weekday(of: dayDate),
              let day = place.hours?.first(where: { $0.weekday == weekday }), !day.intervals.isEmpty else { return nil }
        return day.intervals.map { "\($0.opens)–\($0.closes)" }.joined(separator: ", ")
    }

    /// 0 = Monday, as in the server's hours.
    static func weekday(of iso: String) -> Int? {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC") ?? .current
        let parts = iso.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3,
              let date = calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2], hour: 12))
        else { return nil }
        return (calendar.component(.weekday, from: date) + 5) % 7
    }
}

/// The place card without a network (SSOT §7.4): name, category, address, opening hours, the visit's time and cost.
struct TripOfflinePlaceSheet: View {
    let card: OfflinePlaceCard
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: JolSpacing.xs) {
                        Text(verbatim: card.place.name)
                            .font(JolFont.title)
                            .accessibilityIdentifier("offline-place-name")
                        if let category = card.place.categoryName ?? card.place.category {
                            Text(verbatim: category).foregroundStyle(JolColor.textSecondary)
                        }
                    }
                }
                Section {
                    if let time = card.item.startTime {
                        LabeledContent("Visit") {
                            Text(verbatim: card.item.endTime.map { "\(time)–\($0)" } ?? time).monospacedDigit()
                        }
                        .accessibilityIdentifier("offline-place-time")
                    }
                    if let cost = card.item.estCostKzt, cost > 0 {
                        LabeledContent("Estimated cost") { Text(verbatim: TripFormatting.kzt(cost, locale: locale)) }
                    }
                    if let hours = card.hoursText {
                        LabeledContent("Opening hours") { Text(verbatim: hours).monospacedDigit() }
                            .accessibilityIdentifier("offline-place-hours")
                    }
                    if let address = card.place.address, !address.isEmpty {
                        LabeledContent("Address") { Text(verbatim: address).multilineTextAlignment(.trailing) }
                            .accessibilityIdentifier("offline-place-address")
                    }
                }
                Section {
                    Text("Saved on this device. Photos, reviews and booking need a connection.")
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.textSecondary)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("offline-place-done")
                }
            }
        }
        .presentationDetents([.medium, .large])
        .accessibilityIdentifier("offline-place-card")
    }
}
