import Foundation
import Observation

/// Loads the regions (`GET /v1/regions`, public) and keeps `Region.current` up to date.
/// Order of trust: the fresh answer, the cached last answer, the built-in region.
@MainActor
@Observable
final class RegionModel {
    private(set) var regions: [Region] = [.builtIn]
    private(set) var current: Region = .builtIn

    @ObservationIgnored private let api: APIClient
    @ObservationIgnored private let defaults: UserDefaults
    @ObservationIgnored static let cacheKey = "jol.regions.cache"

    init(api: APIClient, defaults: UserDefaults = .standard) {
        self.api = api
        self.defaults = defaults
        if let data = defaults.data(forKey: Self.cacheKey),
           let cached = try? JSONDecoder().decode(RegionsResponse.self, from: data), let region = cached.preferred {
            apply(cached.regions, current: region)
        } else {
            Region.current = .builtIn
            Region.known = [.builtIn]
        }
    }

    /// A failure (no network, a server without the endpoint) keeps what is already in use.
    func load() async {
        do {
            let answer: RegionsResponse = try await api.send(.get("/v1/regions", authorized: false))
            guard let region = answer.preferred else { return }
            apply(answer.regions, current: region)
            if let data = try? JSONEncoder().encode(answer) { defaults.set(data, forKey: Self.cacheKey) }
        } catch {
            return
        }
    }

    private func apply(_ all: [Region], current region: Region) {
        regions = all
        current = region
        Region.current = region
        Region.known = all
    }
}
