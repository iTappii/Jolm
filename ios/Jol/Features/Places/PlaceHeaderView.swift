import SwiftUI
import UIKit

/// The top of the place card (SSOT §6.1): name with the distance from the person on the side, rating, today's hours,
/// and the exact address (a tap copies it).
struct PlaceHeaderView: View {
    let place: PlaceSummary
    let detail: PlaceDetail?
    @Environment(AppContainer.self) private var container
    @Environment(\.locale) private var locale
    @State private var user: GeoPoint?
    @State private var copied = false

    private var language: String { container.language.code }

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.xxs) {
            AdaptiveStack(spacing: JolSpacing.sm, rowAlignment: .firstTextBaseline) {
                Text(place.name)
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                    .accessibilityIdentifier("place-name")
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: JolSpacing.sm)
                if let meters = distance {
                    Text(verbatim: PlaceFormatting.distanceFromYou(meters: meters, language: language))
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.textSecondary)
                        .accessibilityIdentifier("place-distance")
                }
            }
            if let rating = detail?.rating ?? place.rating, rating.count >= 1 { ratingRow(rating) }
            if let today = detail?.today ?? place.today, let line = PlaceFormatting.todayLine(today) {
                Text(verbatim: PlaceFormatting.text(for: line, language: language))
                    .font(JolFont.callout)
                    .foregroundStyle(color(of: line))
                    .accessibilityIdentifier("place-today")
            }
            if let address = detail?.address ?? place.address, !address.isEmpty { addressButton(address) }
        }
        .task(id: place.id) { await locate() }
    }

    // MARK: - Pieces

    private var distance: Double? {
        user.map { PlaceFormatting.distance(from: $0, to: place.coordinate) }
    }

    private func color(of line: TodayLine) -> Color {
        switch line {
        case .open24h: JolColor.statusOpen
        case .hours(_, _, .open): JolColor.statusOpen
        case .closedToday, .opensAt, .hours(_, _, .closed): JolColor.danger
        case .hours(_, _, .unknown): JolColor.textSecondary
        }
    }

    private func ratingRow(_ rating: PlaceRating) -> some View {
        let average = rating.average.formatted(.number.precision(.fractionLength(1)).locale(locale))
        return HStack(spacing: JolSpacing.xs) {
            HStack(spacing: 1) {
                ForEach(1...5, id: \.self) { star in
                    Image(systemName: Self.symbol(star: star, average: rating.average))
                        .font(.caption)
                        .foregroundStyle(JolColor.brandText)
                }
            }
            .accessibilityHidden(true)
            Text(verbatim: average).font(JolFont.callout.weight(.semibold)).foregroundStyle(JolColor.textPrimary)
            Text("(\(rating.count) reviews)").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text.spoken([Text("Rating \(average) out of 5"), Text("\(rating.count) reviews")]))
        .accessibilityIdentifier("place-rating")
    }

    /// Full / half / empty star for the star number `star` (1…5) of an average.
    static func symbol(star: Int, average: Double) -> String {
        let value = average - Double(star - 1)
        if value >= 0.75 { return "star.fill" }
        if value >= 0.25 { return "star.leadinghalf.filled" }
        return "star"
    }

    private func addressButton(_ address: String) -> some View {
        Button {
            UIPasteboard.general.string = address
            copied = true
            let note = L10n.string("Address copied", language: language)
            UIAccessibility.post(notification: .announcement, argument: note)
            Task {
                try? await Task.sleep(for: .seconds(2))
                copied = false
            }
        } label: {
            Label {
                Text(verbatim: copied ? L10n.string("Address copied", language: language) : address)
                    .font(JolFont.callout)
                    .multilineTextAlignment(.leading)
            } icon: {
                Image(systemName: copied ? "checkmark" : "mappin.and.ellipse").foregroundStyle(JolColor.textSecondary)
            }
            .foregroundStyle(JolColor.textSecondary)
            .frame(minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(verbatim: address))
        .accessibilityHint(Text("Copies the address"))
        .accessibilityIdentifier("place-address")
    }

    /// Only a fix that already exists (access was granted before): the card never asks for permission.
    private func locate() async {
        user = nil
        for _ in 0..<4 {
            if let point = container.locator.knownLocation() {
                user = point
                return
            }
            try? await Task.sleep(for: .seconds(1))
            if Task.isCancelled { return }
        }
    }
}
