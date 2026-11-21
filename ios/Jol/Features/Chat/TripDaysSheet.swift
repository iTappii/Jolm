import SwiftUI

/// Placeholder for the full-map screen (Ш-37): the days of the ready route as a plain list, read from
/// `GET /v1/trips/{id}`. «Open full map» in the chat opens it; the map behind already shows the route's places.
struct TripDaysSheet: View {
    let model: ChatModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale

    var body: some View {
        NavigationStack {
            content
                .navigationTitle(Text("Your route"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { dismiss() }
                            .accessibilityIdentifier("trip-days-done")
                    }
                }
        }
        .accessibilityIdentifier("trip-days")
        .task { if model.trip == .idle || model.trip == .failed { model.loadTrip() } }
    }

    @ViewBuilder private var content: some View {
        switch model.trip {
        case .idle, .loading:
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed:
            VStack(spacing: JolSpacing.md) {
                Text("Couldn't load the route.")
                    .foregroundStyle(JolColor.textSecondary)
                Button("Try again") { model.loadTrip() }
                    .accessibilityIdentifier("trip-days-retry")
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        case .loaded(let trip):
            List {
                ForEach(trip.days) { day in
                    Section {
                        if day.items.isEmpty {
                            Text("Free day").foregroundStyle(JolColor.textSecondary)
                        }
                        ForEach(day.items) { item in
                            HStack(spacing: JolSpacing.md) {
                                Text(verbatim: item.startTime ?? "")
                                    .font(JolFont.callout.monospacedDigit())
                                    .foregroundStyle(JolColor.textSecondary)
                                    .frame(width: 48, alignment: .leading)
                                Text(verbatim: item.place.name)
                                    .accessibilityIdentifier("trip-day-item")
                            }
                        }
                    } header: {
                        Text(verbatim: BriefFormatting.dates(start: day.date, end: day.date, locale: locale)
                            ?? day.date)
                    }
                }
            }
            .accessibilityIdentifier("trip-days-list")
        }
    }
}
