import CoreLocation
import Foundation
import Observation

/// State of the places layer on the map, the selected place (mini / full card) and curated routes (Ш-19).
@MainActor
@Observable
final class PlacesModel {
    enum DetailState: Equatable {
        case idle
        case loading
        case loaded(PlaceDetail)
        case failed
    }

    enum ListState<Value: Equatable>: Equatable {
        case idle
        case loading
        case loaded(Value)
        case failed
    }

    /// Hard limit on pins kept in memory; pins outside the current area are dropped first.
    static let cap = 3000
    /// Relative growth of the requested area around the viewport, so small pans need no request.
    static let padding = 0.25

    // MARK: - Pins

    private(set) var pins: [PlaceSummary] = []
    /// Bumped whenever `pins` changes — lets the map skip a comparison of thousands of items.
    private(set) var pinsVersion = 0
    private(set) var pinsFailed = false

    // MARK: - Selection

    private(set) var selected: PlaceSummary?
    private(set) var detail: DetailState = .idle

    // MARK: - Curated routes

    private(set) var routes: ListState<[CuratedRouteSummary]> = .idle
    private(set) var activeRoute: CuratedRouteDetail?
    private(set) var routeLoading = false
    private(set) var routeFailed = false

    @ObservationIgnored private let service: PlacesService
    @ObservationIgnored private let debounce: Duration
    @ObservationIgnored private var byID: [UUID: PlaceSummary] = [:]
    @ObservationIgnored private var loadedBounds: GeoBounds?
    @ObservationIgnored private var loadedTruncated = false
    @ObservationIgnored private var currentBounds: GeoBounds?
    @ObservationIgnored private var pinsTask: Task<Void, Never>?
    @ObservationIgnored private var detailTask: Task<Void, Never>?
    @ObservationIgnored private var routeTask: Task<Void, Never>?

    init(api: APIClient, debounce: Duration = .milliseconds(350)) {
        self.service = PlacesService(api: api)
        self.debounce = debounce
    }

    var routeStops: [PlaceSummary] { activeRoute?.stops ?? [] }

    /// Centre of the visible map (fallback origin for directions when the user's location is unknown).
    var mapCenter: GeoPoint? {
        currentBounds.map { GeoPoint(lat: ($0.south + $0.north) / 2, lon: ($0.west + $0.east) / 2) }
    }

    // MARK: - Pins loading

    /// Called on every camera change. Debounced; a newer call cancels the pending/in-flight request.
    func regionChanged(_ bounds: GeoBounds) {
        currentBounds = bounds
        pinsTask?.cancel()
        guard activeRoute == nil else { return }
        if let loaded = loadedBounds, !loadedTruncated, loaded.contains(bounds) { return }
        pinsTask = Task { [weak self, debounce] in
            try? await Task.sleep(for: debounce)
            guard !Task.isCancelled, let self else { return }
            await self.loadPins(for: bounds)
            // One automatic retry after a failure (server restarting, flaky network).
            if self.pinsFailed {
                try? await Task.sleep(for: .seconds(3))
                guard !Task.isCancelled else { return }
                await self.loadPins(for: bounds)
            }
        }
    }

    private func loadPins(for viewport: GeoBounds) async {
        let area = viewport.padded(by: Self.padding, maxSpan: PlacesService.maxSpan)
        do {
            let items = try await service.places(in: area)
            guard !Task.isCancelled else { return }
            merge(items, area: area, viewport: viewport)
            pinsFailed = false
        } catch is CancellationError {
            return
        } catch {
            guard !Task.isCancelled else { return }
            pinsFailed = true
        }
    }

    private func merge(_ items: [PlaceSummary], area: GeoBounds, viewport: GeoBounds) {
        var changed = false
        for item in items where byID[item.id] != item {
            byID[item.id] = item
            changed = true
        }
        var evicted = false
        if byID.count > Self.cap {
            let keep = byID.filter { viewport.contains(lat: $0.value.lat, lon: $0.value.lon) }
            let outside = byID.values.filter { !viewport.contains(lat: $0.lat, lon: $0.lon) }
                .sorted { $0.popularity > $1.popularity }
                .prefix(max(0, Self.cap - keep.count))
            byID = keep
            for place in outside { byID[place.id] = place }
            evicted = true
            changed = true
        }
        // The freshly requested area is fully loaded (up to the page limit), unless eviction dropped part of it.
        loadedBounds = evicted ? nil : area
        loadedTruncated = items.count >= PlacesService.pageLimit
        if changed {
            pins = byID.values.sorted { $0.popularity > $1.popularity }
            pinsVersion += 1
        }
    }

    // MARK: - Selection

    func select(_ id: UUID) {
        let summary = byID[id] ?? routeStops.first { $0.id == id }
        guard let summary else { return }
        select(summary)
    }

    func select(_ summary: PlaceSummary) {
        if selected?.id == summary.id, detail != .failed { return }
        selected = summary
        loadDetail(id: summary.id)
    }

    func retryDetail() {
        guard let selected else { return }
        loadDetail(id: selected.id)
    }

    func clearSelection() {
        detailTask?.cancel()
        selected = nil
        detail = .idle
    }

    private func loadDetail(id: UUID) {
        detailTask?.cancel()
        detail = .loading
        detailTask = Task { [weak self] in
            guard let self else { return }
            do {
                let place = try await service.place(id: id)
                guard !Task.isCancelled, selected?.id == id else { return }
                detail = .loaded(place)
            } catch {
                guard !Task.isCancelled, selected?.id == id else { return }
                detail = .failed
            }
        }
    }

    // MARK: - Curated routes

    func loadRoutes() async {
        if case .loading = routes { return }
        routes = .loading
        do {
            routes = .loaded(try await service.curatedRoutes())
        } catch {
            routes = .failed
        }
    }

    func openRoute(id: UUID) {
        routeTask?.cancel()
        routeLoading = true
        routeFailed = false
        routeTask = Task { [weak self] in
            guard let self else { return }
            do {
                let route = try await service.curatedRoute(id: id)
                guard !Task.isCancelled else { return }
                clearSelection()
                activeRoute = route
                routeLoading = false
            } catch {
                guard !Task.isCancelled else { return }
                routeLoading = false
                routeFailed = true
            }
        }
    }

    func closeRoute() {
        routeTask?.cancel()
        routeLoading = false
        activeRoute = nil
        clearSelection()
        if let currentBounds { regionChanged(currentBounds) }
    }
}
