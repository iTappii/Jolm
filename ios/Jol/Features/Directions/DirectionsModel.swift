import CoreLocation
import Foundation
import Observation

/// "Как добраться" (Ш-23, SSOT §6, §5.3): origin → `POST /v1/directions` → options → the chosen line on the map.
/// Works for a guest. The origin is the user's location; without one (denied, no fix, outside Almaty)
/// it falls back to the map centre and says so (`fallback`), so the user is never left without an answer.
@MainActor
@Observable
final class DirectionsModel {
    enum Phase: Equatable {
        case idle
        case locating
        case loading
        case loaded
        case failed(Failure)
    }

    enum Failure: Equatable {
        /// Origin or destination outside the area the server routes in (Almaty).
        case outsideArea
        case network
        case serviceUnavailable
        case generic
    }

    /// Why the origin is the map centre instead of the user's location.
    enum Fallback: Equatable {
        case denied
        case unavailable
        case outsideArea
        /// The user picked it.
        case chosen
    }

    private(set) var phase = Phase.idle
    private(set) var target: PlaceSummary?
    /// Carousel pages in SSOT §6.1 order; modes the server did not return are absent.
    private(set) var pages: [TransportPage] = []
    /// Current carousel page (the carousel is circular: see `showNext` / `showPrevious`).
    private(set) var pageIndex = 0
    /// Chosen variant per page (0 = the optimal one).
    private(set) var variantIndex: [TransportPage.Kind: Int] = [:]
    /// When the answer arrived: the departure moment the arrival times are computed from (no `arrive_at` yet).
    private(set) var answeredAt = Date()
    private(set) var origin: GeoPoint?
    /// `nil` → the origin is the user's location.
    private(set) var fallback: Fallback?
    /// Bumped whenever the drawn lines change, so the map applies them exactly once.
    private(set) var lineVersion = 0
    /// Bumped when the camera should fit the lines (new answer, another page).
    private(set) var fitVersion = 0

    @ObservationIgnored private let api: APIClient
    @ObservationIgnored private let locator: any LocationProviding
    @ObservationIgnored private var mapCenter: GeoPoint?
    @ObservationIgnored private var task: Task<Void, Never>?

    init(api: APIClient, locator: any LocationProviding) {
        self.api = api
        self.locator = locator
    }

    var isActive: Bool { phase != .idle }

    var currentPage: TransportPage? { pages.indices.contains(pageIndex) ? pages[pageIndex] : nil }

    func selectedVariant(of page: TransportPage) -> Int {
        min(variantIndex[page.kind] ?? 0, max(0, page.variants.count - 1))
    }

    /// Every variant of the current page; the chosen one is flagged (the map highlights it).
    var lines: [DirectionLine] {
        guard let page = currentPage else { return [] }
        let chosen = selectedVariant(of: page)
        return page.variants.enumerated().map { DirectionLine(coordinates: $1.line, selected: $0 == chosen) }
    }

    // MARK: - Flow

    /// Starts from the user's location. `mapCenter` is the fallback origin.
    func start(to place: PlaceSummary, mapCenter: GeoPoint?) {
        self.mapCenter = mapCenter
        target = place
        begin { await self.resolveFromLocation() }
    }

    /// The user chose the map centre as the origin (explicitly, e.g. to plan a trip from another area).
    func useMapCenter(_ center: GeoPoint?) {
        guard target != nil else { return }
        mapCenter = center ?? mapCenter
        begin(.loading) { await self.requestFromMapCenter(reason: .chosen) }
    }

    func useCurrentLocation() {
        guard target != nil else { return }
        begin { await self.resolveFromLocation() }
    }

    func retry() {
        guard target != nil else { return }
        if let reason = fallback {
            begin(.loading) { await self.requestFromMapCenter(reason: reason) }
        } else {
            useCurrentLocation()
        }
    }

    /// Circular: after the last page comes the first.
    func showNext() { showPage(pages.isEmpty ? 0 : (pageIndex + 1) % pages.count) }

    func showPrevious() { showPage(pages.isEmpty ? 0 : (pageIndex - 1 + pages.count) % pages.count) }

    func showPage(_ index: Int) {
        guard pages.indices.contains(index), index != pageIndex else { return }
        pageIndex = index
        lineVersion += 1
        fitVersion += 1
    }

    /// Picks a variant on the current page (the map highlights its line).
    func selectVariant(_ index: Int) {
        guard let page = currentPage, page.variants.indices.contains(index),
              selectedVariant(of: page) != index else { return }
        variantIndex[page.kind] = index
        lineVersion += 1
    }

    func reset() {
        task?.cancel()
        task = nil
        phase = .idle
        target = nil
        pages = []
        pageIndex = 0
        variantIndex = [:]
        origin = nil
        fallback = nil
        lineVersion += 1
        fitVersion += 1
    }

    // MARK: - Internals

    private func begin(_ initial: Phase = .locating, _ work: @escaping @MainActor () async -> Void) {
        task?.cancel()
        pages = []
        pageIndex = 0
        variantIndex = [:]
        lineVersion += 1
        phase = initial
        task = Task {
            guard !Task.isCancelled else { return }
            await work()
        }
    }

    private func resolveFromLocation() async {
        let result = await locator.currentLocation()
        guard !Task.isCancelled else { return }
        switch result {
        case .located(let point) where point.isInServiceArea:
            fallback = nil
            await request(from: point)
        case .located:
            await requestFromMapCenter(reason: .outsideArea)
        case .denied:
            await requestFromMapCenter(reason: .denied)
        case .unavailable:
            await requestFromMapCenter(reason: .unavailable)
        }
    }

    private func requestFromMapCenter(reason: Fallback) async {
        fallback = reason
        guard let center = mapCenter else {
            origin = nil
            phase = .failed(.generic)
            return
        }
        guard center.isInServiceArea else {
            origin = center
            phase = .failed(.outsideArea)
            return
        }
        await request(from: center)
    }

    private func request(from point: GeoPoint) async {
        guard let target else { return }
        origin = point
        phase = .loading
        do {
            var endpoint = try Endpoint.post(
                "v1/directions", json: DirectionsRequest(from: point, toPlaceID: target.id), authorized: false
            )
            endpoint.timeout = 25
            let payload: DirectionsPayload = try await api.send(endpoint)
            guard !Task.isCancelled, self.target?.id == target.id, origin == point else { return }
            pages = TransportPage.pages(from: payload.options)
            // Open on the page with the server's recommendation (else the first page).
            pageIndex = pages.firstIndex { $0.variants.contains { $0.recommended } } ?? 0
            variantIndex = [:]
            answeredAt = Date()
            lineVersion += 1
            fitVersion += 1
            phase = .loaded
        } catch is CancellationError {
            return
        } catch {
            guard !Task.isCancelled else { return }
            phase = .failed(Self.failure(for: error))
        }
    }

    private static func failure(for error: Error) -> Failure {
        switch error as? APIError {
        case .server(let status, _, _) where status == 422: .outsideArea
        case .server(let status, _, _) where status >= 500: .serviceUnavailable
        case .network: .network
        default: .generic
        }
    }
}
