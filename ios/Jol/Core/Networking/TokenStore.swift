import Foundation

/// Where the session token pair lives. `SessionStore` (Keychain) is the production implementation.
protocol TokenStore: Sendable {
    func load() throws -> SessionTokens?
    func save(_ tokens: SessionTokens) throws
    func clear() throws
}

extension SessionStore: TokenStore {}

#if DEBUG
/// In-memory store for UI tests (`-JolFakeSignedIn`): the Keychain is not touched.
final class EphemeralTokenStore: TokenStore, @unchecked Sendable {
    private let lock = NSLock()
    private var tokens: SessionTokens?

    init(_ tokens: SessionTokens? = nil) { self.tokens = tokens }

    func load() throws -> SessionTokens? {
        lock.lock(); defer { lock.unlock() }
        return tokens
    }

    func save(_ tokens: SessionTokens) throws {
        lock.lock(); defer { lock.unlock() }
        self.tokens = tokens
    }

    func clear() throws {
        lock.lock(); defer { lock.unlock() }
        tokens = nil
    }
}
#endif
