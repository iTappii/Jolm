import SwiftUI

@main
struct JolApp: App {
    @State private var container = JolApp.makeContainer()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(container)
        }
    }

    private static func makeContainer() -> AppContainer {
        #if DEBUG
        // UI tests: a pre-signed-in session that never touches the Keychain.
        if ProcessInfo.processInfo.arguments.contains("-JolFakeSignedIn") {
            let session = SessionTokens(accessToken: "ui-test-access", refreshToken: "ui-test-refresh")
            return AppContainer(tokens: EphemeralTokenStore(session))
        }
        // UI tests: the API answers from fixtures (places, curated routes), no server needed.
        if UITestSupport.isStubbed {
            return AppContainer(
                tokens: EphemeralTokenStore(nil),
                baseURL: .success(URL(string: "http://localhost:8000")!),
                session: UITestSupport.makeSession()
            )
        }
        #endif
        return AppContainer()
    }
}
