import Foundation
import Observation

/// «My bookings» (Ш-49, Ш-55): the signed-in person's requests, newest first, and cancelling one. The list and the
/// detail screen read the same array, so a cancelled booking changes in both.
@MainActor
@Observable
final class MyBookingsModel {
    enum Phase: Equatable {
        case idle, loading, loaded, failed
    }

    /// What went wrong with a cancellation.
    enum CancelProblem: Equatable {
        /// 409 `not_cancellable`: already cancelled, declined or over.
        case notCancellable
        case network
        case other
    }

    private(set) var phase = Phase.idle
    private(set) var items: [Booking] = []
    private(set) var nextCursor: String?
    private(set) var isLoadingMore = false
    private(set) var moreFailed = false
    /// The booking being cancelled right now.
    private(set) var cancellingID: UUID?
    private(set) var cancelProblem: CancelProblem?

    @ObservationIgnored private let service: BookingService
    @ObservationIgnored private let auth: AuthState

    init(api: APIClient, auth: AuthState) {
        self.service = BookingService(api: api)
        self.auth = auth
    }

    func booking(id: UUID) -> Booking? { items.first { $0.id == id } }

    /// Loads (or reloads) the first page. A failure keeps what is on screen.
    func load() async {
        guard auth.isSignedIn else { return }
        if items.isEmpty { phase = .loading }
        do {
            let page = try await service.list(cursor: nil)
            items = page.items
            nextCursor = page.nextCursor
            moreFailed = false
            phase = .loaded
        } catch {
            if items.isEmpty { phase = .failed }
        }
    }

    func loadMore() async {
        guard let cursor = nextCursor, !isLoadingMore, auth.isSignedIn else { return }
        isLoadingMore = true
        moreFailed = false
        defer { isLoadingMore = false }
        do {
            let page = try await service.list(cursor: cursor)
            let known = Set(items.map(\.id))
            items += page.items.filter { !known.contains($0.id) }
            nextCursor = page.nextCursor
        } catch {
            moreFailed = true
        }
    }

    /// Asks the server to cancel. Returns `true` when the booking is cancelled. After a 409 the booking is read again,
    /// so the screen shows the status that made it impossible.
    @discardableResult
    func cancel(_ id: UUID) async -> Bool {
        guard cancellingID == nil else { return false }
        cancellingID = id
        cancelProblem = nil
        defer { cancellingID = nil }
        do {
            replace(try await service.cancel(id: id))
            return true
        } catch APIError.server(409, "not_cancellable", _) {
            cancelProblem = .notCancellable
            if let fresh = try? await service.booking(id: id) { replace(fresh) }
        } catch APIError.network {
            cancelProblem = .network
        } catch {
            cancelProblem = .other
        }
        return false
    }

    func dismissCancelProblem() {
        cancelProblem = nil
    }

    private func replace(_ booking: Booking) {
        if let index = items.firstIndex(where: { $0.id == booking.id }) { items[index] = booking }
    }
}
