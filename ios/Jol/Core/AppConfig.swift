import Foundation

/// Build-time configuration read from Info.plist (values come from build settings).
enum AppConfig {
    /// Fallback bundled style, used when JOL_MAP_STYLE_URL is empty.
    static let bundledStyleName = "placeholder-style"

    /// Resolved map style URL. Empty `JOL_MAP_STYLE_URL` → bundled placeholder style.
    /// `dark` switches `jol-light.json` to `jol-dark.json` on the same host (maps/style builds both).
    static func mapStyleURL(dark: Bool = false) -> URL {
        #if DEBUG
        if UITestSupport.isStubbed, let url = Bundle.main.url(forResource: "stub-style", withExtension: "json") {
            return url  // UI tests: offline, no tiles server needed
        }
        #endif
        let base = resolveStyleURL(
            configured: Bundle.main.object(forInfoDictionaryKey: "JOL_MAP_STYLE_URL") as? String,
            bundle: .main
        )
        return dark ? darkVariant(of: base) : base
    }

    /// `…/jol-light.json` → `…/jol-dark.json`; any other URL (bundled style, custom name) is returned as is.
    static func darkVariant(of url: URL) -> URL {
        guard !url.isFileURL, url.lastPathComponent.contains("jol-light") else { return url }
        let dark = url.lastPathComponent.replacingOccurrences(of: "jol-light", with: "jol-dark")
        return url.deletingLastPathComponent().appending(path: dark)
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

    /// Resolved API base URL from `JOL_API_BASE_URL`.
    static var apiBaseURL: Result<URL, APIError> {
        resolveAPIBaseURL(configured: Bundle.main.object(forInfoDictionaryKey: "JOL_API_BASE_URL") as? String)
    }

    /// https is always allowed; plain http only for `localhost` in the simulator.
    static func resolveAPIBaseURL(
        configured: String?,
        allowLocalHTTP: Bool = AppConfig.isSimulator
    ) -> Result<URL, APIError> {
        guard let configured, let base = URL(string: configured.trimmingCharacters(in: .whitespacesAndNewlines)),
              let host = base.host, !host.isEmpty else {
            return .failure(.invalidBaseURL)
        }
        let local = allowLocalHTTP && base.scheme == "http" && host == "localhost"
        guard base.scheme == "https" || local else { return .failure(.invalidBaseURL) }
        return .success(base)
    }

    static var isSimulator: Bool {
        #if targetEnvironment(simulator)
        true
        #else
        false
        #endif
    }
}
