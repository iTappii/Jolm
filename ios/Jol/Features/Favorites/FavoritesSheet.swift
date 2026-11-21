import SwiftUI

/// Favorites list (opened from the side panel): tap a place → its card on the map.
struct FavoritesSheet: View {
    let model: FavoritesModel
    let onOpen: (PlaceSummary) -> Void
    @Environment(\.dismiss) private var dismiss
    @ScaledMetric(relativeTo: .headline) private var iconSize: CGFloat = 36

    var body: some View {
        NavigationStack {
            content
                .navigationTitle(Text("Favorites"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { dismiss() }.accessibilityIdentifier("favorites-done")
                    }
                }
        }
        .task { await model.load() }
        .accessibilityIdentifier("favorites-sheet")
    }

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .idle, .loading where model.items.isEmpty:
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity).accessibilityLabel(Text("Loading"))
        case .failed:
            VStack(spacing: JolSpacing.md) {
                Text("Couldn't load favorites").foregroundStyle(JolColor.textSecondary)
                Button("Retry") { Task { await model.load() } }
                    .minTapTarget()
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .accessibilityIdentifier("favorites-failed")
        default:
            if model.items.isEmpty {
                VStack(spacing: JolSpacing.sm) {
                    Image(systemName: "heart").font(.largeTitle).foregroundStyle(JolColor.textTertiary)
                        .accessibilityHidden(true)
                    Text("No favorites yet").foregroundStyle(JolColor.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityIdentifier("favorites-empty")
            } else {
                List(model.items) { place in
                    Button {
                        dismiss()
                        onOpen(place)
                    } label: {
                        HStack(spacing: JolSpacing.md) {
                            let style = PlaceCategoryStyle.style(for: place.category)
                            Image(systemName: style.symbol)
                                .frame(width: iconSize, height: iconSize)
                                .background(style.color.opacity(0.18), in: Circle())
                                .foregroundStyle(style.color)
                                .accessibilityHidden(true)
                            Text(place.name)
                                .font(JolFont.headline)
                                .foregroundStyle(JolColor.textPrimary)
                                .multilineTextAlignment(.leading)
                        }
                        .frame(minHeight: 44)
                    }
                    .accessibilityIdentifier("favorite-row")
                }
            }
        }
    }
}
