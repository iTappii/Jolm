import Foundation

/// Lookup of strings outside SwiftUI views (view code uses `Text("key")` + `.environment(\.locale, ...)`).
enum L10n {
    /// Localized string from the String Catalog for an explicit language code (`ru`/`en`).
    static func string(_ key: String, table: String? = nil, language: String, bundle: Bundle = .main) -> String {
        guard let path = bundle.path(forResource: language, ofType: "lproj"),
              let localized = Bundle(path: path) else {
            return bundle.localizedString(forKey: key, value: nil, table: table)
        }
        return localized.localizedString(forKey: key, value: nil, table: table)
    }
}
