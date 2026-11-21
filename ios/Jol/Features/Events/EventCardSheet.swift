import SwiftUI

/// The «Ad» / «Реклама» mark of a promoted event (SSOT §5.1, §12). The text is the server's `ad_label`.
struct AdBadge: View {
    let label: String

    var body: some View {
        Text(verbatim: label)
            .font(JolFont.caption.weight(.bold))
            .foregroundStyle(JolColor.onBrand)
            .padding(.horizontal, JolSpacing.sm)
            .padding(.vertical, JolSpacing.xxs)
            .background(JolColor.brand, in: Capsule())
            .accessibilityIdentifier("event-ad-label")
    }
}

/// Sheet with an event (Ш-48): title, when, price, organizer, description, the place it takes place at.
struct EventCardSheet: View {
    let events: EventsModel
    let places: PlacesModel
    @Environment(\.locale) private var locale

    var body: some View {
        Group {
            if let event = events.selected {
                ScrollView { card(event).padding(JolSpacing.lg) }
            }
        }
        .presentationDetents([PlaceCardSheet.cardDetent, .large])
        .presentationBackgroundInteraction(.enabled(upThrough: PlaceCardSheet.cardDetent))
        .presentationDragIndicator(.visible)
        .presentationBackground(JolColor.surfaceElevated)
        .presentationCornerRadius(JolRadius.xl)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("event-card")
    }

    private func card(_ event: EventItem) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            HStack(spacing: JolSpacing.sm) {
                Label("Event", systemImage: "ticket")
                    .font(JolFont.caption.weight(.semibold))
                    .foregroundStyle(JolColor.textSecondary)
                if let label = event.visibleAdLabel { AdBadge(label: label) }
            }
            Text(verbatim: event.title)
                .font(JolFont.headline)
                .foregroundStyle(JolColor.textPrimary)
                .accessibilityIdentifier("event-title")
                .accessibilityAddTraits(.isHeader)
            if let when = event.whenText(locale: locale) {
                Label { Text(verbatim: when) } icon: { Image(systemName: "calendar") }
                    .font(JolFont.callout)
                    .accessibilityIdentifier("event-when")
            }
            if let price = event.priceKzt {
                Label {
                    Text(price == 0 ? "Free entry" : "Tickets from \(PlaceFormatting.tenge(price))")
                } icon: {
                    Image(systemName: "banknote")
                }
                .font(JolFont.callout)
            }
            if let organizer = event.organizer, !organizer.isEmpty {
                Label { Text(verbatim: organizer) } icon: { Image(systemName: "person.2") }
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.textSecondary)
            }
            if let description = event.description, !description.isEmpty {
                Text(verbatim: description).font(JolFont.body)
            }
            if let venue = event.place {
                Button {
                    events.clearSelection()
                    places.select(PlaceSummary(
                        id: venue.id, name: venue.name, category: event.category, kind: "venue", lat: event.lat,
                        lon: event.lon, isPublic: false, isPartner: false, popularity: 50
                    ))
                } label: {
                    Label { Text(verbatim: venue.name) } icon: { Image(systemName: "mappin.and.ellipse") }
                        .font(JolFont.callout.weight(.semibold))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(JolSpacing.md)
                        .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                }
                .buttonStyle(.plain)
                .foregroundStyle(JolColor.textPrimary)
                .accessibilityIdentifier("event-place")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
