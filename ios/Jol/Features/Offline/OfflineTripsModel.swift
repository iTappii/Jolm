import Foundation
import Observation

/// Trips downloaded to the device (SSOT §7.4, Ш-42): "Download route" on the full map and in "My trips", and the
/// saved copies the map falls back to when there is no network. The server answers `GET /v1/trips/{id}/offline` with
/// an `ETag`; asking again with `If-None-Match` costs nothing when the plan has not changed (`304`).
@MainActor
@Observable
final class OfflineTripsModel {
    enum State: Equatable {
        case none, downloading, saved
    }

    enum Problem: Equatable {
        case network
        case server(String)
    }

    private(set) var savedIDs: Set<UUID> = []
    private(set) var downloading: Set<UUID> = []
    /// Why the last explicit download failed (shown once, then dismissed).
    private(set) var problem: Problem?

    @ObservationIgnored private let service: TripService
    @ObservationIgnored private let store: OfflineTripStore

    init(api: APIClient, store: OfflineTripStore = OfflineTripStore()) {
        self.service = TripService(api: api)
        self.store = store
        reload()
    }

    func state(for id: UUID) -> State {
        if downloading.contains(id) { return .downloading }
        return savedIDs.contains(id) ? .saved : .none
    }

    func reload() {
        savedIDs = Set(store.all().map(\.trip.tripID))
    }

    func saved(_ id: UUID) -> SavedTrip? {
        savedIDs.contains(id) ? store.load(id) : nil
    }

    /// The saved trips as list rows for "My trips" when the server cannot be reached.
    func summaries() -> [TripSummary] {
        store.all().map { saved in
            let trip = saved.trip
            return TripSummary(
                id: trip.tripID, startDate: trip.startDate, endDate: trip.endDate, days: trip.days.count,
                budget: TripSummaryBudget(status: nil, budgetKzt: trip.budgetKzt, totalKzt: trip.totalCostKzt),
                updatedAt: nil
            )
        }
    }

    /// Downloads (or brings up to date) one trip. Returns `true` when the device holds the current copy afterwards.
    /// `silent`: a background refresh of an already saved trip, a failure is not reported.
    @discardableResult
    func download(tripID: UUID, silent: Bool = false) async -> Bool {
        guard !downloading.contains(tripID) else { return false }
        downloading.insert(tripID)
        if !silent { problem = nil }
        defer { downloading.remove(tripID) }
        let known = store.load(tripID)
        do {
            switch try await service.offline(id: tripID, etag: known?.meta.etag) {
            case .notModified:
                return known != nil
            case .fresh(let trip, let etag):
                try store.save(trip, etag: etag)
                savedIDs.insert(tripID)
                return true
            }
        } catch {
            if !silent { problem = Self.problem(for: error) }
            return false
        }
    }

    /// After a trip was read or edited online: a saved copy follows the plan (conditional request, no body when
    /// nothing changed).
    func syncIfSaved(tripID: UUID) async {
        guard savedIDs.contains(tripID) else { return }
        await download(tripID: tripID, silent: true)
    }

    func remove(tripID: UUID) {
        store.remove(tripID)
        savedIDs.remove(tripID)
    }

    /// Sign-out or account deletion: a saved plan is personal data of that account.
    func removeAll() {
        store.removeAll()
        savedIDs = []
        downloading = []
        problem = nil
    }

    func dismissProblem() {
        problem = nil
    }

    nonisolated static func problem(for error: Error) -> Problem {
        switch error as? APIError {
        case .server(_, _, let message)? where !message.isEmpty: .server(message)
        case .rateLimited(_, let message)? where !message.isEmpty: .server(message)
        default: .network
        }
    }
}
