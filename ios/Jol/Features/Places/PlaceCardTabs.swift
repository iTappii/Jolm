import SwiftUI

/// Body of the selected tab: overview (category, hours, prices, …), reviews (empty until Ф14), photos grid.
struct PlaceTabContent: View {
    let tab: PlaceTab
    let place: PlaceSummary
    let detail: PlaceDetail
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.md) {
            switch tab {
            case .overview: overview
            case .reviews: reviews
            case .photos: photos
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("place-tab-content-\(tab.rawValue)")
    }

    // MARK: - Overview

    @ViewBuilder
    private var overview: some View {
        HStack(spacing: JolSpacing.sm) {
            if let name = detail.category?.name {
                Text(name).font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            }
            if let open = detail.openNow {
                Text(open ? "Open now" : "Closed")
                    .font(JolFont.caption.weight(.semibold))
                    .foregroundStyle(open ? Color.green : JolColor.danger)
                    .accessibilityIdentifier("place-open-now")
            }
        }
        if let today = PlaceFormatting.today(detail.hours) {
            Text(today).font(JolFont.caption).foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("place-hours-today")
        }
        priceLines(detail.prices)
        if let description = detail.description, !description.isEmpty {
            Text(description).font(JolFont.body).foregroundStyle(JolColor.textPrimary)
        }
        if let minutes = detail.typicalVisitMin {
            let parts = PlaceFormatting.visitDuration(minutes: minutes)
            Label { Text("Typical visit \(parts.hours) h \(parts.minutes) min").font(JolFont.callout) } icon: {
                Image(systemName: "clock").foregroundStyle(JolColor.textSecondary)
            }
        }
        hoursTable(detail.hours)
        if let site = detail.website, let url = URL(string: site), url.scheme?.hasPrefix("http") == true {
            Button { openURL(url) } label: { Label(site, systemImage: "safari").lineLimit(1) }
                .accessibilityIdentifier("place-website")
        }
        NavigatorButton(place: place)
        Button {} label: {
            Label("Book — coming soon", systemImage: "calendar.badge.plus")
                .font(JolFont.callout)
                .frame(maxWidth: .infinity)
                .padding(.vertical, JolSpacing.sm)
                .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        }
        .buttonStyle(.plain)
        .disabled(true)
        .opacity(0.5)
        .accessibilityIdentifier("place-book")
    }

    @ViewBuilder
    private func priceLines(_ prices: PlaceDetail.Prices) -> some View {
        if let value = prices.entryPriceKzt { priceRow("Entry", value) }
        if let value = prices.avgCheckKzt { priceRow("Average bill", value) }
        if let value = prices.pricePerNightKzt { priceRow("Per night", value) }
    }

    private func priceRow(_ label: LocalizedStringKey, _ value: Int) -> some View {
        HStack(spacing: JolSpacing.xs) {
            Text(label).foregroundStyle(JolColor.textSecondary)
            Text(PlaceFormatting.tenge(value)).foregroundStyle(JolColor.textPrimary)
        }
        .font(JolFont.caption)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func hoursTable(_ hours: [PlaceDetail.DayHours]) -> some View {
        if !hours.isEmpty {
            let today = PlaceFormatting.weekday()
            VStack(alignment: .leading, spacing: JolSpacing.xs) {
                Text("Opening hours").font(JolFont.headline)
                ForEach(0..<7, id: \.self) { day in
                    HStack {
                        Text(Self.weekdayNames[day])
                        Spacer()
                        if let text = PlaceFormatting.intervals(hours.first { $0.weekday == day }) {
                            Text(text)
                        } else {
                            Text("Closed").foregroundStyle(JolColor.textSecondary)
                        }
                    }
                    .font(JolFont.callout.weight(day == today ? .semibold : .regular))
                    .foregroundStyle(JolColor.textPrimary)
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("place-hours")
        }
    }

    private static let weekdayNames: [LocalizedStringKey] = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    ]

    // MARK: - Reviews and photos

    private var reviews: some View {
        VStack(spacing: JolSpacing.sm) {
            Image(systemName: "text.bubble").font(.largeTitle).foregroundStyle(JolColor.textTertiary)
            Text("No reviews yet").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, JolSpacing.xl)
        .accessibilityIdentifier("place-reviews-empty")
    }

    @ViewBuilder
    private var photos: some View {
        if detail.photos.isEmpty {
            // Photo URLs come with `MEDIA_BASE_URL` (Ш-44); until then a placeholder tile says so.
            LazyVGrid(columns: Self.columns, spacing: JolSpacing.sm) {
                PlacePhotoView(photo: nil, category: place.category, height: 100)
            }
            Text("No photos yet").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("place-photos-empty")
        } else {
            LazyVGrid(columns: Self.columns, spacing: JolSpacing.sm) {
                ForEach(detail.photos) { photo in
                    PlacePhotoView(photo: photo, category: place.category, height: 100)
                }
            }
            .accessibilityIdentifier("place-photos-grid")
        }
    }

    private static let columns = Array(repeating: GridItem(.flexible(), spacing: JolSpacing.sm), count: 3)
}

/// Horizontal gallery at the top of the card; a single placeholder while there are no photo URLs.
struct PlaceGallery: View {
    let photos: [PlaceDetail.Photo]
    let category: String?

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: JolSpacing.sm) {
                if photos.isEmpty {
                    PlacePhotoView(photo: nil, category: category, height: 90)
                        .frame(width: 220)
                } else {
                    ForEach(photos) { photo in
                        PlacePhotoView(photo: photo, category: category, height: 90).frame(width: 200)
                    }
                }
            }
        }
        .accessibilityIdentifier("place-gallery")
    }
}
