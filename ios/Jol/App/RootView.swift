import SwiftUI

/// Root of the UI. Applies the app-level language (no restart) and the brand tint.
/// Content is the main screen (`HomeScreen`).
struct RootView: View {
    @Environment(AppContainer.self) private var container
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        content
            .environment(\.locale, container.language.locale)
            .tint(JolColor.brand)
            // Ш-40: the server learns about this device at launch and whenever the account or the language changes.
            .task(id: container.auth.isSignedIn) {
                await container.devices.register()
                await container.devices.refreshTokenAtLaunch()
            }
            .onChange(of: container.language.code) { _, _ in
                Task { await container.devices.register() }
            }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await container.devices.retryIfNeeded() } }
            }
            // The notification question comes once, when the first trip is on screen.
            .onChange(of: container.chat.tripID) { old, new in
                if old == nil, new != nil, container.auth.isSignedIn {
                    Task { await container.devices.requestPermissionAfterFirstTrip() }
                }
            }
    }

    @ViewBuilder
    private var content: some View {
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("-JolFeatureGallery") {
            FeatureGalleryScreen()
        } else {
            HomeScreen()
        }
        #else
        HomeScreen()
        #endif
    }
}
