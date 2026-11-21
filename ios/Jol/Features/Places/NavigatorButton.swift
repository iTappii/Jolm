import SwiftUI

/// "Open in navigator": Apple Maps always, 2GIS when installed (a menu if there are two). Links only (SSOT §13).
struct NavigatorButton: View {
    let place: PlaceSummary
    /// The way the person chose in the directions carousel, when there is one (analytics, Ш-50). A closure read at
    /// the tap: the surrounding panel must not observe the carousel's state just for this.
    var mode: () -> TransportMode? = { nil }
    @Environment(\.openURL) private var openURL
    @Environment(AppContainer.self) private var container
    @State private var navigators: [Navigator.App] = [.appleMaps]

    var body: some View {
        let label = Label("Open in navigator", systemImage: "location.north.line")
            .font(JolFont.headline)
            .foregroundStyle(JolColor.textPrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, JolSpacing.md)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        Group {
            if navigators.count == 1, let app = navigators.first {
                Button { open(app) } label: { label }
                    .buttonStyle(.plain)
            } else {
                Menu {
                    ForEach(navigators) { app in
                        Button(app == .appleMaps ? "Apple Maps" : "2GIS") { open(app) }
                    }
                } label: { label }
            }
        }
        .accessibilityIdentifier("place-navigator")
        .onAppear { navigators = Navigator.availableApps() }
    }

    private func open(_ app: Navigator.App) {
        container.analytics.trackDirectionsStart(placeID: place.id, mode: mode())
        if let url = Navigator.url(for: app, name: place.name, coordinate: place.coordinate) { openURL(url) }
    }
}
