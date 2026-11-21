#if DEBUG
import SwiftUI

/// Debug-only index of all feature screens (launch argument `-JolFeatureGallery`).
/// Used by UI tests to verify runtime language switching and by hand to see the placeholders.
struct FeatureGalleryScreen: View {
    @Environment(AppContainer.self) private var container
    @State private var status: ServerStatusModel?

    var body: some View {
        NavigationStack {
            List {
                Section { LanguagePicker() }
                Section {
                    link("Chat", systemImage: "bubble.left.and.bubble.right") { ChatScreen() }
                    link("Places", systemImage: "mappin.and.ellipse") { PlacesScreen() }
                    link("Route", systemImage: "arrow.triangle.turn.up.right.diamond") { RouteScreen() }
                    link("Trip", systemImage: "suitcase") { TripScreen() }
                    link("Profile", systemImage: "person.crop.circle") { ProfileScreen() }
                    link("Sidebar", systemImage: "sidebar.left") { SidebarScreen() }
                }
                Section {
                    statusRow
                }
            }
            .navigationTitle(Text("Features"))
        }
        .task {
            let model = ServerStatusModel(api: container.api)
            status = model
            await model.load()
        }
    }

    private func link<Destination: View>(
        _ title: LocalizedStringKey, systemImage: String, @ViewBuilder destination: () -> Destination
    ) -> some View {
        NavigationLink {
            destination()
        } label: {
            Label(title, systemImage: systemImage)
        }
    }

    @ViewBuilder
    private var statusRow: some View {
        switch status?.state ?? .idle {
        case .idle, .loading:
            ProgressView()
        case .loaded(let meta):
            Text("Server \(meta.version)")
                .accessibilityIdentifier("server-status")
        case .failed(let error):
            Text("Server unavailable: \(error.serverMessage)")
                .accessibilityIdentifier("server-status")
        }
    }
}
#endif
