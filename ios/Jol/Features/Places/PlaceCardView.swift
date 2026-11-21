import SwiftUI

/// Place card (SSOT §6.1): one sheet — photos on top, name and address, tabs (overview / reviews / photos) — with
/// the «Route» and «Add to favorites» buttons pinned at the bottom. «Route» swaps the scrolling part for the
/// directions carousel (`DirectionsPanel`).
struct PlaceCardView: View {
    let model: PlacesModel
    let directions: DirectionsModel
    @Environment(AppContainer.self) private var container
    @State private var tab = PlaceTab.overview
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        Group {
            if let place = model.selected {
                VStack(spacing: 0) {
                    ScrollView {
                        if directions.isActive {
                            DirectionsPanel(model: directions, place: place, mapCenter: { model.mapCenter })
                                .padding(JolSpacing.lg)
                        } else {
                            content(place).padding(JolSpacing.lg)
                        }
                    }
                    pinnedBar(place)
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("place-card")
        .sheet(
            isPresented: Binding(get: { container.gate.isPresenting }, set: { container.gate.isPresenting = $0 }),
            onDismiss: { container.gate.sheetDismissed() },
            content: { AccountGateSheet() }
        )
        .onChange(of: model.selected?.id) { _, id in
            tab = .overview
            container.crowd.reset(for: id)
        }
    }

    var detail: PlaceDetail? {
        if case .loaded(let detail) = model.detail { return detail }
        return nil
    }

    // MARK: - Scrolling part

    @ViewBuilder private func content(_ place: PlaceSummary) -> some View {
        if let point = place.tappedPoint {
            pointContent(place, point)
        } else {
            placeContent(place)
        }
    }

    /// A tapped address or bare point (Ш-23c): what is known about it and nothing else — no photos, tabs or favorites.
    private func pointContent(_ place: PlaceSummary, _ point: TappedPoint) -> some View {
        HStack(alignment: .top, spacing: JolSpacing.md) {
            Image(systemName: point.isBare ? "mappin" : "building.2")
                .font(.title3)
                .foregroundStyle(JolColor.brandText)
                .frame(width: 44, height: 44)
                .background(JolColor.surface, in: Circle())
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                Text(place.name)
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                    .accessibilityIdentifier("place-name")
                    .accessibilityAddTraits(.isHeader)
                if point.isBare {
                    Text("Point on the map")
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.textSecondary)
                        .accessibilityIdentifier("point-kind")
                } else if let address = point.address, address != place.name {
                    Text(address)
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.textSecondary)
                        .accessibilityIdentifier("place-address")
                }
                Text("Not in our places yet: no photos or reviews.")
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.textSecondary)
                    .padding(.top, JolSpacing.xs)
            }
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("point-card")
    }

    private func placeContent(_ place: PlaceSummary) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            // A placeholder tile says nothing; at large text its height is better spent on the content.
            if !(typeSize.isAccessibilitySize && (detail?.photos ?? []).isEmpty) {
                PlaceGallery(photos: detail?.photos ?? [], category: place.category)
            }
            VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                Text(place.name)
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                    .accessibilityIdentifier("place-name")
                    .accessibilityAddTraits(.isHeader)
                if let address = detail?.address, !address.isEmpty {
                    Label { Text(address).font(JolFont.callout) } icon: {
                        Image(systemName: "mappin.and.ellipse").foregroundStyle(JolColor.textSecondary)
                    }
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityIdentifier("place-address")
                }
            }
            tabBar
            if case .failed = model.detail {
                failedRow
            } else if detail == nil {
                ProgressView().frame(maxWidth: .infinity)
                    .accessibilityLabel(Text("Loading"))
                    .accessibilityIdentifier("place-loading")
            } else if let detail {
                PlaceTabContent(tab: tab, place: place, detail: detail)
            }
        }
    }

    /// Three tabs in a row. At accessibility text sizes the words do not fit side by side and stacking them would eat
    /// the card: they become a row that scrolls sideways, one line high.
    private var tabBar: some View {
        Group {
            if typeSize.isAccessibilitySize {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: JolSpacing.xs) { tabButtons(fill: false) }
                }
            } else {
                HStack(spacing: JolSpacing.xs) { tabButtons(fill: true) }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(Text("Sections"))
    }

    private func tabButtons(fill: Bool) -> some View {
        ForEach(PlaceTab.allCases) { item in
            Button { tab = item } label: {
                Text(item.title)
                    .font(JolFont.callout.weight(tab == item ? .semibold : .regular))
                    .foregroundStyle(tab == item ? JolColor.onBrand : JolColor.textPrimary)
                    .lineLimit(1)
                    .padding(.horizontal, fill ? 0 : JolSpacing.lg)
                    .frame(maxWidth: fill ? .infinity : nil, minHeight: 44)
                    .background(tab == item ? JolColor.brand : JolColor.surface, in: Capsule())
            }
            .buttonStyle(.plain)
            .accessibilityAddTraits(tab == item ? .isSelected : [])
            .accessibilityIdentifier("place-tab-\(item.rawValue)")
        }
    }

    private var failedRow: some View {
        HStack {
            Text("Couldn't load the place").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            Button("Retry") { model.retryDetail() }
                .minTapTarget()
                .accessibilityIdentifier("place-retry")
        }
    }

    // MARK: - Pinned buttons

    private func pinnedBar(_ place: PlaceSummary) -> some View {
        VStack(spacing: JolSpacing.xs) {
            if let problem = container.favorites.problem {
                Text(problem == .limit ? "Favorites list is full." : "Couldn't update favorites.")
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.danger)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityIdentifier("place-favorite-problem")
            }
            HStack(spacing: JolSpacing.sm) {
                Button {
                    directions.start(to: place, mapCenter: model.mapCenter)
                } label: {
                    Label("Route", systemImage: "arrow.triangle.turn.up.right.diamond.fill")
                        .font(JolFont.headline)
                        .foregroundStyle(JolColor.onBrand)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, JolSpacing.md)
                        .frame(minHeight: 44)
                        .background(JolColor.brand, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("place-directions")
                if place.tappedPoint == nil { favoriteButton(place) }
            }
        }
        .padding(.horizontal, JolSpacing.lg)
        .padding(.top, JolSpacing.sm)
        .padding(.bottom, JolSpacing.md)
        .background(JolColor.surfaceElevated.ignoresSafeArea())
        .overlay(alignment: .top) { Divider() }
    }

    /// «Add to favorites» only for places of our base: an address has no id on the server (SSOT §11.5).
    private func favoriteButton(_ place: PlaceSummary) -> some View {
        let isFavorite = container.favorites.isFavorite(place.id)
        let title: LocalizedStringKey = isFavorite ? "In favorites" : "Add to favorites"
        let symbol = isFavorite ? "heart.fill" : "heart"
        return Button { favorite(place) } label: {
            // At accessibility text sizes the words would push the pinned bar over the card: only the heart stays,
            // VoiceOver still says what it does.
            Group {
                if typeSize.isAccessibilitySize {
                    Image(systemName: symbol).frame(width: 56, height: 44)
                } else {
                    Label(title, systemImage: symbol).frame(maxWidth: .infinity, minHeight: 44)
                }
            }
            .font(JolFont.headline)
            .foregroundStyle(isFavorite ? JolColor.brandText : JolColor.textPrimary)
            .padding(.vertical, JolSpacing.xs)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(title))
        .accessibilityAddTraits(isFavorite ? .isSelected : [])
        .accessibilityIdentifier("place-favorite")
    }

    /// Signed-in: toggles the favorite. Guest: the sign-in gate first (SSOT §3.2), then the place is added.
    private func favorite(_ place: PlaceSummary) {
        if container.auth.isSignedIn {
            Task { await container.favorites.toggle(place) }
        } else {
            container.gate.requireAccount {
                Task {
                    await container.favorites.load()
                    await container.favorites.add(place)
                }
            }
        }
    }
}

enum PlaceTab: String, CaseIterable, Identifiable {
    case overview, reviews, photos

    var id: String { rawValue }

    var title: LocalizedStringKey {
        switch self {
        case .overview: "Overview"
        case .reviews: "Reviews"
        case .photos: "Photos"
        }
    }
}
