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
            .task(id: container.auth.isSignedIn) { syncChatEvents() }
            .onChange(of: scenePhase) { _, phase in
                syncChatEvents()
                if phase == .active { Task { await container.devices.retryIfNeeded() } }
                // Ш-50: what is queued leaves when the app is put away (and again when it comes back).
                Task { await container.analytics.flush() }
            }
            .task { await container.regions.load() }
            .task {
                container.analytics.trackLaunch()
                await container.analytics.flush()
            }
            // The notification question comes once, when the first trip is on screen.
            .onChange(of: container.chat.tripID) { old, new in
                if old == nil, new != nil, container.auth.isSignedIn {
                    Task { await container.devices.requestPermissionAfterFirstTrip() }
                }
            }
    }

    /// Ш-64: the chat's events stream runs only for a signed-in person while the app is in front.
    private func syncChatEvents() {
        container.chat.setEventsEnabled(container.auth.isSignedIn && scenePhase == .active)
    }

    @ViewBuilder
    private var content: some View {
        #if DEBUG
        Group {
            if ProcessInfo.processInfo.arguments.contains("-JolFeatureGallery") {
                FeatureGalleryScreen()
            } else {
                HomeScreen()
            }
        }
        .preferredColorScheme(UITestSupport.forcedColorScheme)
        #else
        HomeScreen()
        #endif
    }
}
