import Foundation

/// Anonymous per-installation identifier (UUID), generated once and persisted.
///
/// Stored in UserDefaults, not Keychain: it is not a secret, and it should reset on reinstall
/// (privacy-friendly, no cross-reinstall tracking). Used for guest rate limits (Ш-30), device
/// registration (Ш-40) and analytics. Sent as the `X-Install-ID` header.
enum InstallID {
    static let key = "jol.install_id"

    static func current(defaults: UserDefaults = .standard) -> String {
        if let existing = defaults.string(forKey: key), UUID(uuidString: existing) != nil {
            return existing
        }
        let fresh = UUID().uuidString
        defaults.set(fresh, forKey: key)
        return fresh
    }
}
