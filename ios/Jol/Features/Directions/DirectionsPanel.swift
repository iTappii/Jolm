import SwiftUI

/// Content of the place sheet while directions are open: origin, ways to get there, "open in navigator".
struct DirectionsPanel: View {
    let model: DirectionsModel
    let place: PlaceSummary
    let mapCenter: () -> GeoPoint?
    @Environment(AppContainer.self) private var container
    @Environment(\.openURL) private var openURL
    @State var slideFrom = Edge.trailing
    @Environment(\.dynamicTypeSize) var typeSize

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.md) {
            header
            originRow
            notice
            content
            NavigatorButton(place: place)
                .padding(.top, JolSpacing.xs)
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("directions-panel")
    }

    var language: String { container.language.code }

    // MARK: - Header and origin

    private var header: some View {
        HStack(spacing: JolSpacing.md) {
            Button { model.reset() } label: {
                Image(systemName: "chevron.left")
                    .font(.body.weight(.semibold))
                    .frame(width: JolTarget.minimum, height: JolTarget.minimum)
                    .fixedSize()
                    .background(JolColor.surface, in: Circle())
                    .foregroundStyle(JolColor.textPrimary)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Back to place"))
            .accessibilityAddTraits(.isButton)
            .accessibilityIdentifier("directions-back")
            VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                Text("Directions").font(JolFont.caption).foregroundStyle(JolColor.textSecondary)
                    .accessibilityAddTraits(.isHeader)
                Text(place.name)
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                    .lineLimit(typeSize.isAccessibilitySize ? nil : 2)
                    .accessibilityIdentifier("directions-title")
            }
            Spacer(minLength: 0)
        }
    }

    private var originRow: some View {
        AdaptiveStack(spacing: JolSpacing.sm) {
            Image(systemName: model.fallback == nil ? "location.fill" : "scope")
                .foregroundStyle(Color(uiColor: UIColor(hex: 0x2563EB)))
                .accessibilityHidden(true)
            Group {
                if model.phase == .locating {
                    Text("Finding your location…")
                } else if model.fallback == nil {
                    Text("From: your location")
                } else {
                    Text("From: map centre")
                }
            }
            .font(JolFont.callout)
            .foregroundStyle(JolColor.textPrimary)
            .accessibilityIdentifier("directions-origin")
            Spacer(minLength: 0)
            if model.phase != .locating {
                if model.fallback == nil {
                    Button { model.useMapCenter(mapCenter()) } label: {
                        Text("From map centre").frame(minHeight: JolTarget.minimum)
                    }
                        .accessibilityIdentifier("directions-use-center")
                } else {
                    Button { model.useCurrentLocation() } label: {
                        Text("From my location").frame(minHeight: JolTarget.minimum)
                    }
                        .accessibilityIdentifier("directions-use-location")
                }
            }
        }
        .font(JolFont.callout)
    }

    /// Why the origin is not the user's location.
    @ViewBuilder
    private var notice: some View {
        switch model.fallback {
        case .denied:
            AdaptiveStack(rowAlignment: .top) {
                Text("Location access is off, so directions start from the map centre. Pan the map to move the start.")
                    .accessibilityIdentifier("directions-notice-denied")
                Spacer(minLength: 0)
                Button {
                    if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
                } label: {
                    Text("Settings").frame(minHeight: JolTarget.minimum)
                }
                .accessibilityIdentifier("directions-settings")
            }
            .noticeStyle()
        case .unavailable:
            Text("Couldn't get your location, so directions start from the map centre.")
                .noticeStyle()
                .accessibilityIdentifier("directions-notice-unavailable")
        case .outsideArea:
            Text("You seem to be outside Almaty, so directions start from the map centre.")
                .noticeStyle()
                .accessibilityIdentifier("directions-notice-outside")
        case .chosen, nil:
            EmptyView()
        }
    }

    // MARK: - Carousel

    @ViewBuilder
    private var content: some View {
        switch model.phase {
        case .idle:
            EmptyView()
        case .locating, .loading:
            HStack { Spacer(); ProgressView(); Spacer() }
                .padding(.vertical, JolSpacing.lg)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Text("Loading"))
                .accessibilityIdentifier("directions-loading")
        case .loaded:
            if model.pages.isEmpty {
                message("No ways to get there from here.", id: "directions-empty")
            } else {
                carousel
            }
        case .failed(let reason):
            failureView(reason)
        }
    }

    @ViewBuilder
    private func failureView(_ failure: DirectionsModel.Failure) -> some View {
        switch failure {
        case .outsideArea:
            message("Directions work inside Almaty only. Move the map there and choose “From map centre”.",
                    id: "directions-outside")
        case .network:
            retryMessage("No connection.")
        case .serviceUnavailable:
            retryMessage("Directions are temporarily unavailable.")
        case .generic:
            retryMessage("Couldn't build the directions.")
        }
    }

    private func retryMessage(_ text: LocalizedStringKey) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            Text(text).font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            Button { model.retry() } label: { Text("Retry").frame(minHeight: JolTarget.minimum) }
                .accessibilityIdentifier("directions-retry")
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("directions-failed")
    }

    private func message(_ text: LocalizedStringKey, id: String) -> some View {
        Text(text)
            .font(JolFont.callout)
            .foregroundStyle(JolColor.textSecondary)
            .accessibilityIdentifier(id)
    }
}

private extension View {
    func noticeStyle() -> some View {
        self
            .font(JolFont.caption)
            .foregroundStyle(JolColor.textSecondary)
            .padding(JolSpacing.sm)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.sm))
    }
}
