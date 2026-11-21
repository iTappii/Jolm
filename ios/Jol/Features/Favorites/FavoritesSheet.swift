import SwiftUI

/// Favorites list (opened from the side panel): tap a place → its card on the map.
struct FavoritesSheet: View {
    let model: FavoritesModel
    let onOpen: (PlaceSummary) -> Void
    @Environment(\.dismiss) private var dismiss

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
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed:
            VStack(spacing: JolSpacing.md) {
                Text("Couldn't load favorites").foregroundStyle(JolColor.textSecondary)
                Button("Retry") { Task { await model.load() } }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .accessibilityIdentifier("favorites-failed")
        default:
            if model.items.isEmpty {
                VStack(spacing: JolSpacing.sm) {
                    Image(systemName: "heart").font(.largeTitle).foregroundStyle(JolColor.textTertiary)
                    Text("No favorites yet").foregroundStyle(JolColor.textSecondary)
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
                                .frame(width: 36, height: 36)
                                .background(style.color.opacity(0.18), in: Circle())
                                .foregroundStyle(style.color)
                            Text(place.name).font(JolFont.headline).foregroundStyle(JolColor.textPrimary)
                        }
                    }
                    .accessibilityIdentifier("favorite-row")
                }
            }
        }
    }
}
