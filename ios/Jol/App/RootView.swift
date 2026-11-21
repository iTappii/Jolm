import SwiftUI

/// Root of the UI. Applies the app-level language (no restart) and the brand tint.
/// Content is the main screen (`HomeScreen`).
struct RootView: View {
    @Environment(AppContainer.self) private var container

    var body: some View {
        content
            .environment(\.locale, container.language.locale)
            .tint(JolColor.brand)
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
