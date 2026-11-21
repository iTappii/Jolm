import Foundation
import Observation

/// Events on the main map (Ш-48): the next two weeks inside the visible area, loaded like the place pins (debounced,
/// padded area, one request covers small pans). The selected event opens its card.
@MainActor
@Observable
final class EventsModel {
    /// The window of dates the map shows, counted from today (Almaty).
    static let windowDays = 14

    private(set) var items: [EventItem] = []
    /// Bumped whenever `items` changes, so the map can skip a comparison.
    private(set) var version = 0
    private(set) var selected: EventItem?

    @ObservationIgnored private let service: EventsService
    @ObservationIgnored private let debounce: Duration
    @ObservationIgnored private let today: @Sendable () -> Date
    @ObservationIgnored private var loadedBounds: GeoBounds?
    @ObservationIgnored private var task: Task<Void, Never>?

    init(api: APIClient, debounce: Duration = .milliseconds(500), today: @escaping @Sendable () -> Date = { Date() }) {
        self.service = EventsService(api: api)
        self.debounce = debounce
        self.today = today
    }

    /// Called on every camera change. A failed or cancelled request keeps what is on the map.
    func regionChanged(_ bounds: GeoBounds) {
        task?.cancel()
        if let loadedBounds, loadedBounds.contains(bounds) { return }
        task = Task { [weak self, debounce] in
            try? await Task.sleep(for: debounce)
            guard !Task.isCancelled, let self else { return }
            await load(for: bounds)
        }
    }

    private func load(for viewport: GeoBounds) async {
        let area = viewport.padded(by: PlacesModel.padding, maxSpan: PlacesService.maxSpan)
        let start = Self.dateString(today())
        let end = Self.dateString(today().addingTimeInterval(Double(Self.windowDays) * 86_400))
        guard let loaded = try? await service.events(from: start, to: end, bbox: area) else { return }
        guard !Task.isCancelled else { return }
        loadedBounds = area
        if loaded != items {
            items = loaded
            version += 1
        }
        #if DEBUG
        // UI tests: the offline stub style draws no circle layers, so the event pins cannot be tapped there.
        if ProcessInfo.processInfo.arguments.contains("-JolStubSelectEvent"), selected == nil { selected = items.first }
        #endif
    }

    func select(_ id: UUID) {
        selected = items.first { $0.id == id }
    }

    func select(_ event: EventItem) {
        selected = event
    }

    func clearSelection() {
        selected = nil
    }

    /// `YYYY-MM-DD` of the Almaty calendar day.
    static func dateString(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = PlaceFormatting.almaty
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }
}
