import SwiftUI

/// Place card (SSOT §6.1): one sheet — photos on top, name and address, tabs (overview / reviews / photos) — with
/// the «Route» and «Add to favorites» buttons pinned at the bottom. «Route» swaps the scrolling part for the
/// directions carousel (`DirectionsPanel`).
struct PlaceCardView: View {
    let model: PlacesModel
    let directions: DirectionsModel
    @Environment(AppContainer.self) private var container
    @State private var tab = PlaceTab.overview

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
        .onChange(of: model.selected?.id) { _, _ in
            tab = .overview
        }
    }

    var detail: PlaceDetail? {
        if case .loaded(let detail) = model.detail { return detail }
        return nil
    }

    // MARK: - Scrolling part

    private func content(_ place: PlaceSummary) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            PlaceGallery(photos: detail?.photos ?? [], category: place.category)
            VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                Text(place.name)
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                    .lineLimit(3)
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
                ProgressView().frame(maxWidth: .infinity).accessibilityIdentifier("place-loading")
            } else if let detail {
                PlaceTabContent(tab: tab, place: place, detail: detail)
            }
        }
    }

    private var tabBar: some View {
        HStack(spacing: JolSpacing.xs) {
            ForEach(PlaceTab.allCases) { item in
                Button { tab = item } label: {
                    Text(item.title)
                        .font(JolFont.callout.weight(tab == item ? .semibold : .regular))
                        .foregroundStyle(tab == item ? JolColor.onBrand : JolColor.textPrimary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, JolSpacing.sm)
                        .background(tab == item ? JolColor.brand : JolColor.surface, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(tab == item ? .isSelected : [])
                .accessibilityIdentifier("place-tab-\(item.rawValue)")
            }
        }
    }

    private var failedRow: some View {
        HStack {
            Text("Couldn't load the place").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            Button("Retry") { model.retryDetail() }
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
                        .background(JolColor.brand, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("place-directions")
                let isFavorite = container.favorites.isFavorite(place.id)
                Button { favorite(place) } label: {
                    Label(isFavorite ? "In favorites" : "Add to favorites",
                          systemImage: isFavorite ? "heart.fill" : "heart")
                        .font(JolFont.headline)
                        .foregroundStyle(isFavorite ? JolColor.brand : JolColor.textPrimary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, JolSpacing.md)
                        .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(isFavorite ? .isSelected : [])
                .accessibilityIdentifier("place-favorite")
            }
        }
        .padding(.horizontal, JolSpacing.lg)
        .padding(.top, JolSpacing.sm)
        .padding(.bottom, JolSpacing.md)
        .background(JolColor.surfaceElevated)
        .overlay(alignment: .top) { Divider() }
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
