import Foundation
import Observation

/// «I'm here» and «Busy / Normal / Quiet» on the place card (Ш-47, SSOT §7.3). The CURRENT location (when-in-use
/// permission only, one fix, no background tracking) goes to the server, which accepts it only within 200 m of the
/// place. One action at a time; the answer is shown under the buttons.
@MainActor
@Observable
final class CrowdModel {
    enum Action: Equatable {
        case checkIn
        case report(CrowdReportLevel)
    }

    enum Outcome: Equatable {
        case recorded(Action)
        /// The server already has a recent one (`recorded: false`): check-in 30 min, report 2 h.
        case alreadyRecorded(Action)
        /// 422 `too_far_from_place`: the person is more than 200 m from the place.
        case tooFar
        /// 429 with the seconds until the next one is possible, when the server said.
        case rateLimited(retryAfter: Int?)
        case locationDenied
        case locationUnavailable
        case failed
    }

    private(set) var working: Action?
    private(set) var outcome: Outcome?
    private(set) var placeID: UUID?

    @ObservationIgnored private let service: CrowdService
    @ObservationIgnored private let locator: any LocationProviding
    @ObservationIgnored private var task: Task<Void, Never>?

    init(api: APIClient, locator: any LocationProviding) {
        self.service = CrowdService(api: api)
        self.locator = locator
    }

    var isWorking: Bool { working != nil }

    /// A new card: the previous answer does not belong to it.
    func reset(for placeID: UUID?) {
        task?.cancel()
        working = nil
        outcome = nil
        self.placeID = placeID
    }

    func perform(_ action: Action, placeID: UUID) {
        guard working == nil else { return }
        self.placeID = placeID
        outcome = nil
        working = action
        task = Task { [weak self] in
            guard let self else { return }
            let result = await run(action, placeID: placeID)
            guard !Task.isCancelled, self.placeID == placeID else { return }
            working = nil
            outcome = result
        }
    }

    private func run(_ action: Action, placeID: UUID) async -> Outcome {
        switch await locator.currentLocation() {
        case .denied: return .locationDenied
        case .unavailable: return .locationUnavailable
        case .located(let point):
            do {
                let answer: CrowdRecorded
                switch action {
                case .checkIn: answer = try await service.checkIn(placeID: placeID, at: point)
                case .report(let level): answer = try await service.report(placeID: placeID, level: level, at: point)
                }
                return answer.recorded ? .recorded(action) : .alreadyRecorded(action)
            } catch {
                return Self.outcome(for: error)
            }
        }
    }

    nonisolated static func outcome(for error: Error) -> Outcome {
        guard let error = error as? APIError else { return .failed }
        switch error {
        case .server(422, "too_far_from_place", _): return .tooFar
        case .rateLimited(let retryAfter, _): return .rateLimited(retryAfter: retryAfter.map { Int($0.rounded(.up)) })
        default: return .failed
        }
    }
}
