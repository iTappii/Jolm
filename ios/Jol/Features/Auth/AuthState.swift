import Observation

/// Whether a session exists. Source of truth is the token store (Keychain); `refresh()` re-reads it
/// (called after sign-in/out and when `APIClient` clears a dead session).
@MainActor
@Observable
final class AuthState {
    private(set) var isSignedIn = false
    @ObservationIgnored private let tokens: any TokenStore

    init(tokens: any TokenStore) {
        self.tokens = tokens
        refresh()
    }

    func refresh() {
        isSignedIn = ((try? tokens.load()) ?? nil) != nil
    }
}
