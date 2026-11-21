import Foundation
import Observation

/// App-level language choice. `.system` follows the device language.
enum AppLanguage: String, CaseIterable, Identifiable, Sendable {
    case system
    case russian = "ru"
    case english = "en"

    var id: String { rawValue }

    /// Languages the app is localized into (String Catalog).
    static let supported = ["ru", "en"]

    /// Native names are not translated on purpose: a user must find their language.
    var nativeName: String? {
        switch self {
        case .system: nil
        case .russian: "Русский"
        case .english: "English"
        }
    }

    /// The `ru`/`en` code actually in effect (for `.system`: best match of the device languages, `en` fallback).
    func resolvedCode(preferred: [String] = Locale.preferredLanguages) -> String {
        if self != .system { return rawValue }
        let match = Bundle.preferredLocalizations(from: Self.supported, forPreferences: preferred)
        return match.first ?? "en"
    }
}

/// Stores the language override and publishes the locale the UI applies with
/// `.environment(\.locale, settings.locale)` — no restart needed.
@MainActor
@Observable
final class LanguageSettings {
    nonisolated static let defaultsKey = "jol.language"

    private let defaults: UserDefaults

    var selection: AppLanguage {
        didSet { defaults.set(selection.rawValue, forKey: Self.defaultsKey) }
    }

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        self.selection = defaults.string(forKey: Self.defaultsKey).flatMap(AppLanguage.init(rawValue:)) ?? .system
    }

    /// Resolved code: `ru` or `en`.
    var code: String { selection.resolvedCode() }

    var locale: Locale { Locale(identifier: code) }

    /// Value for the `Accept-Language` header.
    nonisolated static func acceptLanguage(defaults: UserDefaults = .standard) -> String {
        let stored = defaults.string(forKey: defaultsKey).flatMap(AppLanguage.init(rawValue:)) ?? .system
        return stored.resolvedCode()
    }
}
