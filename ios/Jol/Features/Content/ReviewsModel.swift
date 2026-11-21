import Foundation
import Observation

/// Reviews of the place on the card, «Отзывы» tab (Ш-44, SSOT §10.1): `GET /v1/places/{id}/reviews`, public, paged
/// by an opaque cursor. Only one place is open at a time, so one model serves the card.
@MainActor
@Observable
final class ReviewsModel {
    enum Phase: Equatable {
        case idle, loading, loaded, failed
    }

    private(set) var placeID: UUID?
    private(set) var phase = Phase.idle
    private(set) var items: [PlaceReview] = []
    private(set) var summary: ReviewsSummary?
    private(set) var nextCursor: String?
    private(set) var isLoadingMore = false
    private(set) var moreFailed = false

    @ObservationIgnored private let service: ContentService
    @ObservationIgnored private var generation = 0

    init(api: APIClient) {
        self.service = ContentService(api: api)
    }

    /// Opens a place: a different one starts from scratch, the same one keeps what is shown and refreshes it.
    func load(placeID: UUID) async {
        if self.placeID != placeID {
            self.placeID = placeID
            phase = .idle
            items = []
            summary = nil
            nextCursor = nil
            moreFailed = false
        }
        generation += 1
        let mine = generation
        if phase != .loaded { phase = .loading }
        do {
            let page = try await service.reviews(placeID: placeID, cursor: nil)
            guard mine == generation, self.placeID == placeID else { return }
            items = page.items
            summary = page.summary
            nextCursor = page.nextCursor
            moreFailed = false
            phase = .loaded
        } catch {
            guard mine == generation, self.placeID == placeID, !(error is CancellationError) else { return }
            if phase != .loaded { phase = .failed }
        }
    }

    func reload() async {
        if let placeID { await load(placeID: placeID) }
    }

    func loadMore() async {
        guard let placeID, let cursor = nextCursor, !isLoadingMore else { return }
        isLoadingMore = true
        moreFailed = false
        defer { isLoadingMore = false }
        let mine = generation
        do {
            let page = try await service.reviews(placeID: placeID, cursor: cursor)
            guard mine == generation, self.placeID == placeID else { return }
            let known = Set(items.map(\.id))
            items += page.items.filter { !known.contains($0.id) }
            nextCursor = page.nextCursor
        } catch {
            if mine == generation { moreFailed = true }
        }
    }
}
