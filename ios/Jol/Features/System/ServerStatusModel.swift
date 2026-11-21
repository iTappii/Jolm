import Observation

/// Loads `GET /v1/meta`. Example of the feature-model pattern: `@Observable`, `@MainActor`,
/// dependencies injected from `AppContainer`.
@MainActor
@Observable
final class ServerStatusModel {
    enum State: Equatable {
        case idle
        case loading
        case loaded(ServerMeta)
        case failed(APIError)
    }

    private(set) var state: State = .idle
    @ObservationIgnored private let api: APIClient

    init(api: APIClient) {
        self.api = api
    }

    func load() async {
        state = .loading
        do {
            state = .loaded(try await api.meta())
        } catch is CancellationError {
            state = .idle
        } catch let error as APIError {
            state = .failed(error)
        } catch {
            state = .failed(.invalidResponse)
        }
    }
}
