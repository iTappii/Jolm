import CoreLocation
import Foundation
import Observation
import UIKit

/// A numbered stop of the shown day, as the map draws it.
struct TripMapStop {
    let placeID: UUID
    let number: Int
    let coordinate: CLLocationCoordinate2D
}

/// One leg of the shown day. `approximate`: no route geometry, a straight line between the stops.
struct TripMapLine {
    let legID: UUID
    let coordinates: [CLLocationCoordinate2D]
    let approximate: Bool
}

/// The full route map (SSOT §11.3, Ш-37): one trip, a day at a time. Edits go to the server (mode of a leg,
/// budget choice, removal of a stop) and the plan is re-read afterwards, so the screen shows what is stored.
@MainActor
@Observable
final class TripMapModel {
    enum Phase: Equatable {
        case idle, loading, loaded, failed
    }

    /// What went wrong with the last edit; shown as a banner.
    enum Problem: Equatable {
        case network
        case server(String)
        /// The plan changed under us (409/404): it was reloaded.
        case outdated
    }

    /// A removal the server wants confirmed (the stop is a must-have of the brief, 409 `must_have`).
    struct PendingRemoval: Equatable {
        let itemID: UUID
        let name: String
    }

    /// Colours of the days, in order, then again.
    static let dayColors: [UInt32] = [0xFF7A00, 0x2563EB, 0x16A34A, 0x9333EA, 0xDB2777, 0x0891B2, 0xCA8A04]

    static func dayColor(_ index: Int) -> UIColor {
        UIColor(hex: dayColors[((index % dayColors.count) + dayColors.count) % dayColors.count])
    }

    private(set) var isOpen = false
    private(set) var phase = Phase.idle
    private(set) var trip: TripOverview?
    private(set) var dayIndex = 0
    private(set) var events: [EventItem] = []
    /// Bumped when the drawn stops / lines change, and when the camera should fit them again.
    private(set) var drawVersion = 0
    private(set) var fitVersion = 0
    /// Bumped after every edit that changed the plan (the chat refreshes its pins from it).
    private(set) var editRevision = 0
    private(set) var isWorking = false
    private(set) var problem: Problem?
    private(set) var pendingRemoval: PendingRemoval?
    /// The leg whose transport options are open (tap on a leg of the map or of the day's list).
    private(set) var selectedLegID: UUID?
    /// Seconds a chosen mode arrives after the next stop starts (`late_by_s`), by leg.
    private(set) var lateBy: [UUID: Int] = [:]
    /// Saved trips for the side panel.
    private(set) var summaries: ChatModel.Load<[TripSummary]> = .idle
    /// The plan on screen comes from the copy saved on the device (no connection): read-only (Ш-42).
    private(set) var isSavedCopy = false
    /// Cards of the places of the saved copy (address, hours), by place id.
    private(set) var savedPlaces: [UUID: OfflinePlace] = [:]

    @ObservationIgnored private let service: TripService
    @ObservationIgnored private let eventsService: EventsService
    @ObservationIgnored private let offline: OfflineTripsModel?
    @ObservationIgnored private var task: Task<Void, Never>?
    @ObservationIgnored private var listTask: Task<Void, Never>?
    @ObservationIgnored private var generation = 0

    init(api: APIClient, offline: OfflineTripsModel? = nil) {
        self.offline = offline
        self.service = TripService(api: api)
        self.eventsService = EventsService(api: api)
    }

    var tripID: UUID? { trip?.id }
    var days: [TripDay] { trip?.days ?? [] }
    var day: TripDay? { days.indices.contains(dayIndex) ? days[dayIndex] : nil }
    var dayColor: UIColor { Self.dayColor(dayIndex) }

    // MARK: - Open / close

    /// Opens the full map for a trip: the camera goes to the first day that has stops.
    func open(tripID: UUID) {
        isOpen = true
        if trip?.id != tripID {
            trip = nil
            isSavedCopy = false
            savedPlaces = [:]
            events = []
            lateBy = [:]
            dayIndex = 0
            drawVersion += 1
        }
        problem = nil
        pendingRemoval = nil
        load(tripID: tripID, initial: true)
    }

    func close() {
        isOpen = false
        selectedLegID = nil
        generation += 1
        task?.cancel()
        problem = nil
        pendingRemoval = nil
        isWorking = false
    }

    func retry() {
        guard let id = trip?.id ?? lastTripID else { return }
        load(tripID: id, initial: trip == nil)
    }

    @ObservationIgnored private var lastTripID: UUID?

    private func load(tripID: UUID, initial: Bool) {
        lastTripID = tripID
        task?.cancel()
        generation += 1
        let generation = generation
        if trip == nil { phase = .loading }
        task = Task { [weak self] in
            guard let self else { return }
            do {
                let loaded = try await service.trip(id: tripID)
                guard generation == self.generation, !Task.isCancelled else { return }
                apply(loaded, initial: initial)
                await loadEvents(for: loaded, generation: generation)
                await offline?.syncIfSaved(tripID: tripID)
            } catch {
                guard generation == self.generation, !Task.isCancelled else { return }
                if openSavedCopy(tripID, after: error, initial: initial) { return }
                if trip == nil { phase = .failed } else { problem = Self.problem(for: error) }
            }
        }
    }

    /// No connection: the copy downloaded earlier (SSOT §7.4) opens in its place, read-only.
    private func openSavedCopy(_ tripID: UUID, after error: Error, initial: Bool) -> Bool {
        guard case APIError.network = error, trip == nil || initial,
              let saved = offline?.saved(tripID), let overview = saved.trip.overview() else { return false }
        apply(overview, initial: initial)
        isSavedCopy = true
        savedPlaces = Dictionary(uniqueKeysWithValues: saved.trip.places.compactMap { key, place in
            UUID(uuidString: key).map { ($0, place) }
        })
        events = []
        problem = nil
        return true
    }

    private func apply(_ loaded: TripOverview, initial: Bool) {
        isSavedCopy = false
        savedPlaces = [:]
        trip = loaded
        phase = .loaded
        if initial || !days.indices.contains(dayIndex) {
            dayIndex = loaded.days.firstIndex { !$0.items.isEmpty } ?? 0
            fitVersion += 1
        }
        drawVersion += 1
    }

    /// Events of the trip dates; if the call fails, the ones the trip itself carries.
    private func loadEvents(for loaded: TripOverview, generation: Int) async {
        let list = (try? await eventsService.events(from: loaded.startDate, to: loaded.endDate)) ?? loaded.events
        guard generation == self.generation, !Task.isCancelled else { return }
        events = list
    }

    // MARK: - Days

    func selectDay(_ index: Int) {
        guard days.indices.contains(index), index != dayIndex else { return }
        dayIndex = index
        drawVersion += 1
        fitVersion += 1
    }

    // MARK: - Drawing

    var stops: [TripMapStop] {
        (day?.items ?? []).enumerated().map { index, item in
            TripMapStop(placeID: item.place.id, number: index + 1, coordinate: item.place.coordinate)
        }
    }

    var lines: [TripMapLine] {
        guard let day else { return [] }
        let byID = Dictionary(day.items.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        return day.legs.compactMap { leg in
            guard let from = leg.fromItemID.flatMap({ byID[$0] }), let to = byID[leg.toItemID] else { return nil }
            if let option = leg.activeOption {
                let line = option.line
                if line.count >= 2 { return TripMapLine(legID: leg.id, coordinates: line, approximate: false) }
            }
            return TripMapLine(
                legID: leg.id, coordinates: [from.place.coordinate, to.place.coordinate], approximate: true
            )
        }
    }

    func stop(placeID: UUID) -> TripPlace? {
        days.flatMap(\.items).first { $0.place.id == placeID }?.place
    }

    func leg(id: UUID) -> TripLeg? {
        days.flatMap(\.legs).first { $0.id == id }
    }

    /// The stop a leg arrives at and the one it leaves, for the sheet's title.
    func endpoints(of leg: TripLeg) -> (from: TripDayItem?, to: TripDayItem?) {
        let items = days.flatMap(\.items)
        return (items.first { $0.id == leg.fromItemID }, items.first { $0.id == leg.toItemID })
    }

    func selectLeg(_ id: UUID) {
        guard leg(id: id) != nil, !isSavedCopy else { return }
        selectedLegID = id
    }

    func clearLeg() {
        selectedLegID = nil
    }

}

// MARK: - Edits

extension TripMapModel {

    /// Chooses how to travel a leg; the answer says how late the next stop gets (`late_by_s`).
    func chooseMode(leg: TripLeg, mode: TransportMode) {
        guard let tripID, !isWorking, !isSavedCopy, leg.chosenMode != mode else { return }
        run { [self] in
            let change = try await service.setMode(tripID: tripID, legID: leg.id, mode: mode)
            replace(leg: change.leg)
            if let late = change.lateByS, late > 0 { lateBy[leg.id] = late } else { lateBy[leg.id] = nil }
            if let budget = change.budget { trip?.budget = budget; trip?.totalCostKzt = budget.totalKzt }
            trip?.version = change.version
            drawVersion += 1
            editRevision += 1
            try await refresh(tripID)
        }
    }

    private func replace(leg: TripLeg) {
        guard var current = trip else { return }
        for dayIndex in current.days.indices {
            if let index = current.days[dayIndex].legs.firstIndex(where: { $0.id == leg.id }) {
                current.days[dayIndex].legs[index] = leg
            }
        }
        trip = current
    }

    /// Makes one of the two variants (or the plan as it is, `keep`) the plan.
    func choose(budget choice: String) {
        guard let tripID, !isWorking, !isSavedCopy else { return }
        run { [self] in
            _ = try await service.chooseBudget(tripID: tripID, choice: choice)
            lateBy = [:]
            editRevision += 1
            try await refresh(tripID)
            fitVersion += 1
        }
    }

    /// Removes a stop. A must-have is not removed without `force`: the server answers 409 and the person confirms.
    func remove(_ item: TripDayItem, force: Bool = false) {
        guard let tripID, !isWorking, !isSavedCopy else { return }
        pendingRemoval = nil
        run { [self] in
            do {
                _ = try await service.remove(tripID: tripID, itemID: item.id, force: force)
            } catch APIError.server(409, "must_have", _) where !force {
                pendingRemoval = PendingRemoval(itemID: item.id, name: item.place.name)
                return
            }
            lateBy = [:]
            editRevision += 1
            try await refresh(tripID)
        }
    }

    func confirmRemoval() {
        guard let pending = pendingRemoval, let item = days.flatMap(\.items).first(where: { $0.id == pending.itemID })
        else { return }
        remove(item, force: true)
    }

    func cancelRemoval() {
        pendingRemoval = nil
    }

    func dismissProblem() {
        problem = nil
    }

    /// Runs an edit with the working flag; an error becomes a banner, and a stale plan is reloaded.
    private func run(_ work: @escaping @MainActor () async throws -> Void) {
        isWorking = true
        problem = nil
        let generation = generation
        Task { [weak self] in
            guard let self else { return }
            do {
                try await work()
            } catch {
                guard generation == self.generation else { return }
                let reason = Self.problem(for: error)
                problem = reason
                if reason == .outdated, let id = tripID { try? await refresh(id) }
            }
            if generation == self.generation { isWorking = false }
        }
    }

    private func refresh(_ tripID: UUID) async throws {
        let loaded = try await service.trip(id: tripID)
        guard trip?.id == loaded.id, isOpen else { return }
        apply(loaded, initial: false)
        events = (try? await eventsService.events(from: loaded.startDate, to: loaded.endDate)) ?? events
        await offline?.syncIfSaved(tripID: tripID)
    }

    nonisolated static func problem(for error: Error) -> Problem {
        guard let error = error as? APIError else { return .network }
        switch error {
        case .network: return .network
        case .server(404, _, _), .server(409, _, _): return .outdated
        case .server(_, _, let message) where !message.isEmpty: return .server(message)
        case .rateLimited(_, let message) where !message.isEmpty: return .server(message)
        default: return .network
        }
    }

    // MARK: - Saved trips (side panel)

    func loadSummaries() {
        listTask?.cancel()
        summaries = .loading
        listTask = Task { [weak self] in
            guard let self else { return }
            do {
                let items = try await service.list()
                guard !Task.isCancelled else { return }
                summaries = .loaded(items)
            } catch {
                guard !Task.isCancelled else { return }
                // No connection: the trips downloaded to the device are still there.
                if case APIError.network = error, let saved = offline?.summaries(), !saved.isEmpty {
                    summaries = .loaded(saved)
                } else {
                    summaries = .failed
                }
            }
        }
    }

    func clearSummaries() {
        listTask?.cancel()
        summaries = .idle
    }
}
