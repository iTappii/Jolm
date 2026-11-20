import Foundation

/// Build-time configuration read from Info.plist (values come from build settings).
enum AppConfig {
    /// Fallback bundled style, used when JOL_MAP_STYLE_URL is empty.
    static let bundledStyleName = "placeholder-style"

    /// Resolved map style URL. Empty `JOL_MAP_STYLE_URL` → bundled placeholder style.
    static var mapStyleURL: URL {
        resolveStyleURL(
            configured: Bundle.main.object(forInfoDictionaryKey: "JOL_MAP_STYLE_URL") as? String,
            bundle: .main
        )
    }

    static func resolveStyleURL(configured: String?, bundle: Bundle) -> URL {
        let trimmed = configured?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !trimmed.isEmpty, let url = URL(string: trimmed) {
            return url
        }
        guard let url = bundle.url(forResource: bundledStyleName, withExtension: "json") else {
            preconditionFailure("Bundled \(bundledStyleName).json is missing")
        }
        return url
    }
}
