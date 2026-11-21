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
            // Fixtures answer the API: the fake tokens must never reach a real server (it would reject them and
            // the session would be cleared).
            return AppContainer(
                tokens: EphemeralTokenStore(session),
                baseURL: .success(URL(string: "http://localhost:8000")!),
                session: UITestSupport.makeSession(),
                locator: StubLocationProvider()
            )
        }
        // UI tests: the API answers from fixtures (places, curated routes), no server needed.
        if UITestSupport.isStubbed {
            // `-JolStubSignedIn`: a signed-in stub user (favorites need a session).
            let session = ProcessInfo.processInfo.arguments.contains("-JolStubSignedIn")
                ? SessionTokens(accessToken: "stub-access", refreshToken: "stub-refresh") : nil
            return AppContainer(
                tokens: EphemeralTokenStore(session),
                baseURL: .success(URL(string: "http://localhost:8000")!),
                session: UITestSupport.makeSession(),
                locator: StubLocationProvider()
            )
        }
        #endif
        return AppContainer()
    }
}
