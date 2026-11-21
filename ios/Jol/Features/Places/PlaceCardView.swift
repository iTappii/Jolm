import SwiftUI

/// Place card (SSOT §11.3). One view for both states of the sheet: `expanded == false` is the mini card
/// (photo, prices, status, buttons), `true` is the full card (description, weekly hours, address, website).
struct PlaceCardView: View {
    let model: PlacesModel
    let expanded: Bool
    @Environment(\.openURL) private var openURL
    @State private var navigators: [Navigator.App] = [.appleMaps]

    var body: some View {
        Group {
            if let place = model.selected {
                if expanded {
                    ScrollView { content(place).padding(JolSpacing.lg) }
                } else {
                    content(place).padding(.horizontal, JolSpacing.lg).padding(.top, JolSpacing.xl)
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier(expanded ? "place-card-full" : "place-card-mini")
        .onAppear { navigators = Navigator.availableApps() }
    }

    private var detail: PlaceDetail? {
        if case .loaded(let detail) = model.detail { return detail }
        return nil
    }

    private func content(_ place: PlaceSummary) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.md) {
            if expanded {
                PlacePhotoView(photo: detail?.photos.first, category: place.category, height: 190)
                header(place)
            } else {
                HStack(alignment: .top, spacing: JolSpacing.md) {
                    PlacePhotoView(photo: detail?.photos.first, category: place.category, height: 84)
                        .frame(width: 84)
                    header(place)
                }
            }
            if case .failed = model.detail {
                failedRow
            } else if detail == nil {
                ProgressView().accessibilityIdentifier("place-loading")
            }
            if let detail {
                details(detail)
            }
            actions(place)
        }
    }

    private func header(_ place: PlaceSummary) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.xs) {
            Text(place.name)
                .font(expanded ? JolFont.title : JolFont.headline)
                .foregroundStyle(JolColor.textPrimary)
                .lineLimit(expanded ? 4 : 2)
                .accessibilityIdentifier("place-name")
                .accessibilityAddTraits(.isHeader)
            HStack(spacing: JolSpacing.sm) {
                if let name = detail?.category?.name {
                    Text(name).font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
                }
                openChip
            }
            if !expanded, let detail {
                if let today = PlaceFormatting.today(detail.hours) {
                    Text(today).font(JolFont.caption).foregroundStyle(JolColor.textSecondary)
                        .accessibilityIdentifier("place-hours-today")
                }
                priceLines(detail.prices)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private var openChip: some View {
        if let open = detail?.openNow {
            Text(open ? "Open now" : "Closed")
                .font(JolFont.caption.weight(.semibold))
                .foregroundStyle(open ? Color.green : JolColor.danger)
                .accessibilityIdentifier("place-open-now")
        }
    }

    private var failedRow: some View {
        HStack {
            Text("Couldn't load the place").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            Button("Retry") { model.retryDetail() }
                .accessibilityIdentifier("place-retry")
        }
    }

    // MARK: - Details

    @ViewBuilder
    private func details(_ detail: PlaceDetail) -> some View {
        if expanded {
            if let description = detail.description, !description.isEmpty {
                Text(description).font(JolFont.body).foregroundStyle(JolColor.textPrimary)
            }
            if let address = detail.address {
                infoRow("mappin.and.ellipse", Text(address)).accessibilityIdentifier("place-address")
            }
            if !detail.prices.isEmpty {
                VStack(alignment: .leading, spacing: JolSpacing.xs) { priceLines(detail.prices) }
            }
            if let minutes = detail.typicalVisitMin {
                let parts = PlaceFormatting.visitDuration(minutes: minutes)
                infoRow("clock", Text("Typical visit \(parts.hours) h \(parts.minutes) min"))
            }
            hoursTable(detail.hours)
            if let site = detail.website, let url = URL(string: site), url.scheme?.hasPrefix("http") == true {
                Button { openURL(url) } label: {
                    Label(site, systemImage: "safari").lineLimit(1)
                }
                .accessibilityIdentifier("place-website")
            }
        }
    }

    @ViewBuilder
    private func priceLines(_ prices: PlaceDetail.Prices) -> some View {
        if let value = prices.entryPriceKzt {
            priceRow("Entry", value)
        }
        if let value = prices.avgCheckKzt {
            priceRow("Average bill", value)
        }
        if let value = prices.pricePerNightKzt {
            priceRow("Per night", value)
        }
    }

    private func priceRow(_ label: LocalizedStringKey, _ value: Int) -> some View {
        HStack(spacing: JolSpacing.xs) {
            Text(label).foregroundStyle(JolColor.textSecondary)
            Text(PlaceFormatting.tenge(value)).foregroundStyle(JolColor.textPrimary)
        }
        .font(JolFont.caption)
        .accessibilityElement(children: .combine)
    }

    private func infoRow(_ symbol: String, _ text: Text) -> some View {
        Label { text.font(JolFont.callout) } icon: { Image(systemName: symbol).foregroundStyle(JolColor.textSecondary) }
            .foregroundStyle(JolColor.textPrimary)
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

    // MARK: - Buttons

    private func actions(_ place: PlaceSummary) -> some View {
        VStack(spacing: JolSpacing.sm) {
            HStack(spacing: JolSpacing.sm) {
                Button {
                    model.requestDirections(to: place.id)
                } label: {
                    Label("Directions", systemImage: "arrow.triangle.turn.up.right.diamond.fill")
                        .font(JolFont.headline)
                        .foregroundStyle(JolColor.onBrand)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, JolSpacing.md)
                        .background(JolColor.brand, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("place-directions")
                navigatorButton(place)
            }
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
    }

    @ViewBuilder
    private func navigatorButton(_ place: PlaceSummary) -> some View {
        let label = Label("Open in navigator", systemImage: "location.north.line")
            .font(JolFont.headline)
            .foregroundStyle(JolColor.textPrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, JolSpacing.md)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        if navigators.count == 1, let app = navigators.first {
            Button { open(app, place) } label: { label }
                .buttonStyle(.plain)
                .accessibilityIdentifier("place-navigator")
        } else {
            Menu {
                ForEach(navigators) { app in
                    Button(app == .appleMaps ? "Apple Maps" : "2GIS") { open(app, place) }
                }
            } label: { label }
            .accessibilityIdentifier("place-navigator")
        }
    }

    private func open(_ app: Navigator.App, _ place: PlaceSummary) {
        if let url = Navigator.url(for: app, name: place.name, coordinate: place.coordinate) { openURL(url) }
    }
}

/// Photo or a placeholder (the server has no photo URLs until `MEDIA_BASE_URL`, Ш-44).
struct PlacePhotoView: View {
    let photo: PlaceDetail.Photo?
    let category: String?
    let height: CGFloat

    var body: some View {
        let style = PlaceCategoryStyle.style(for: category)
        ZStack {
            if let urlString = photo?.url, let url = URL(string: urlString) {
                AsyncImage(url: url) { image in
                    image.resizable().scaledToFill()
                } placeholder: {
                    placeholder(style)
                }
            } else {
                placeholder(style)
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: height)
        .clipShape(RoundedRectangle(cornerRadius: JolRadius.md))
        .accessibilityHidden(true)
        .accessibilityIdentifier("place-photo")
    }

    private func placeholder(_ style: PlaceCategoryStyle) -> some View {
        ZStack {
            style.color.opacity(0.18)
            Image(systemName: style.symbol)
                .font(.system(size: height * 0.35, weight: .regular))
                .foregroundStyle(style.color)
        }
    }
}
