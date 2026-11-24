import Foundation
import Observation

/// The list of main sights (Ш-69): fetched once per app session and again when the language changes, kept in memory.
/// A failure leaves the list as it was (empty at first): the map just has no such layer, no error is shown.
@MainActor
@Observable
final class LandmarksModel {
    private(set) var items: [Landmark] = []
    /// Language of `items`; `nil` until a load succeeded.
    private(set) var loadedLanguage: String?

    @ObservationIgnored private let fetch: @Sendable () async throws -> [Landmark]
    @ObservationIgnored private var loading: String?

    init(api: APIClient) {
        let service = LandmarksService(api: api)
        self.fetch = { try await service.landmarks() }
    }

    init(fetch: @escaping @Sendable () async throws -> [Landmark]) {
        self.fetch = fetch
    }

    /// Loads the list for `language` unless it is already there (or being loaded).
    func load(language: String) async {
        guard loadedLanguage != language, loading != language else { return }
        loading = language
        defer { if loading == language { loading = nil } }
        guard let loaded = try? await fetch(), !Task.isCancelled else { return }
        items = loaded
        loadedLanguage = language
    }
}
