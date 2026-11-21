import Foundation
import Observation

private struct FavoritesList: Decodable {
    let items: [PlaceSummary]
}

/// Favorite places (SSOT §11.5, Ш-23b): `GET /v1/me/favorites`, `PUT|DELETE /v1/me/favorites/{place_id}`.
/// Signed-in only; the server answers 401 to guests, so a guest is sent through the registration gate instead.
@MainActor
@Observable
final class FavoritesModel {
    enum ListState: Equatable {
        case idle
        case loading
        case loaded
        case failed
    }

    /// Why the last change was refused (shown once next to the button).
    enum Problem: Equatable {
        case limit
        case failed
    }

    private(set) var items: [PlaceSummary] = []
    private(set) var state = ListState.idle
    private(set) var problem: Problem?
    private(set) var ids: Set<UUID> = []

    @ObservationIgnored private let api: APIClient

    init(api: APIClient) {
        self.api = api
    }

    func isFavorite(_ id: UUID) -> Bool { ids.contains(id) }

    func load() async {
        state = .loading
        do {
            let list: FavoritesList = try await api.send(.get("v1/me/favorites"))
            items = list.items
            ids = Set(list.items.map(\.id))
            state = .loaded
        } catch {
            if case .server(401, _, _)? = error as? APIError {
                clear()
            } else {
                state = .failed
            }
        }
    }

    /// Forget everything (sign-out, account deleted, dead session).
    func clear() {
        items = []
        ids = []
        state = .idle
        problem = nil
    }

    func dismissProblem() { problem = nil }

    /// Adds the place if it is not a favorite yet, removes it otherwise.
    func toggle(_ place: PlaceSummary) async {
        if ids.contains(place.id) { await remove(place) } else { await add(place) }
    }

    /// Optimistic: the heart flips at once and flips back if the server refuses.
    func add(_ place: PlaceSummary) async {
        problem = nil
        let before = (ids, items)
        ids.insert(place.id)
        if !items.contains(where: { $0.id == place.id }) { items.insert(place, at: 0) }
        do {
            try await api.send(Endpoint(.put, "v1/me/favorites/\(place.id.uuidString.lowercased())"))
        } catch {
            (ids, items) = before
            if case .server(409, _, _)? = error as? APIError { problem = .limit } else { problem = .failed }
        }
    }

    func remove(_ place: PlaceSummary) async {
        problem = nil
        let before = (ids, items)
        ids.remove(place.id)
        items.removeAll { $0.id == place.id }
        do {
            try await api.send(.delete("v1/me/favorites/\(place.id.uuidString.lowercased())"))
        } catch {
            (ids, items) = before
            problem = .failed
        }
    }
}
