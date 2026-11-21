import Foundation
import Observation

/// Balance and history of the bonus account (SSOT §10.3, Ш-46): the profile menu row and the bonus screen. A signed-in
/// user only; the server answers 401 to a guest and the model then stays empty.
@MainActor
@Observable
final class BonusModel {
    enum Phase: Equatable {
        case idle, loading, loaded, failed
    }

    private(set) var phase = Phase.idle
    private(set) var balance: Int?
    private(set) var tengePerBonus = 1
    private(set) var items: [BonusEntry] = []
    private(set) var nextCursor: String?
    private(set) var isLoadingMore = false
    /// The next page could not be loaded (the first page is on screen).
    private(set) var moreFailed = false

    @ObservationIgnored private let service: BonusService
    @ObservationIgnored private let auth: AuthState

    init(api: APIClient, auth: AuthState) {
        self.service = BonusService(api: api)
        self.auth = auth
    }

    /// Value of the balance in tenge ("≈ 240 ₸").
    var balanceKzt: Int? { balance.map { $0 * tengePerBonus } }

    /// Loads (or reloads) the first page. A failure keeps what is on screen.
    func load() async {
        guard auth.isSignedIn else { return }
        if balance == nil { phase = .loading }
        do {
            let page = try await service.page(cursor: nil)
            balance = page.balance
            tengePerBonus = max(1, page.tengePerBonus)
            items = page.items
            nextCursor = page.nextCursor
            moreFailed = false
            phase = .loaded
        } catch {
            if balance == nil { phase = .failed }
        }
    }

    func loadMore() async {
        guard let cursor = nextCursor, !isLoadingMore, auth.isSignedIn else { return }
        isLoadingMore = true
        moreFailed = false
        defer { isLoadingMore = false }
        do {
            let page = try await service.page(cursor: cursor)
            let known = Set(items.map(\.id))
            items += page.items.filter { !known.contains($0.id) }
            balance = page.balance
            nextCursor = page.nextCursor
        } catch {
            moreFailed = true
        }
    }
}
