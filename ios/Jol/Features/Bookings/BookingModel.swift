import Foundation
import Observation

/// The booking request form of a place (Ш-49, SSOT §9). One request at a time; the form keeps one idempotency key
/// until it is closed, so pressing «Send» again after a network failure cannot book twice.
@MainActor
@Observable
final class BookingModel {
    enum Failure: Equatable {
        /// 422 `booking_not_supported`: the partner does not take this kind.
        case notSupported
        /// 409 `booking_unavailable`: the partner cannot take it (date, party size).
        case unavailable
        /// 422 `validation_error`: e.g. a time in the past.
        case invalid
        case rateLimited(retryAfter: Int?)
        case signedOut
        case network
        case other
    }

    enum State: Equatable {
        case editing
        case sending
        case done(Booking)
        case failed(Failure)
    }

    private(set) var state = State.editing
    @ObservationIgnored private let service: BookingService
    @ObservationIgnored private var key = UUID().uuidString
    @ObservationIgnored private var lastRequest: BookingRequest?
    @ObservationIgnored private var task: Task<Void, Never>?

    init(api: APIClient) {
        self.service = BookingService(api: api)
    }

    var booking: Booking? {
        if case .done(let booking) = state { return booking }
        return nil
    }

    var isSending: Bool { state == .sending }

    /// A fresh form: new idempotency key, no old answer.
    func reset() {
        task?.cancel()
        key = UUID().uuidString
        lastRequest = nil
        state = .editing
    }

    func submit(_ request: BookingRequest) {
        guard !isSending else { return }
        // The same form again (a retry) keeps its key; a changed one is a different booking.
        if let last = lastRequest, last != request { key = UUID().uuidString }
        lastRequest = request
        state = .sending
        let key = key
        task = Task { [weak self] in
            guard let self else { return }
            do {
                let booking = try await service.create(request, key: key)
                guard !Task.isCancelled else { return }
                state = .done(booking)
            } catch {
                guard !Task.isCancelled else { return }
                state = .failed(Self.failure(for: error))
            }
        }
    }

    /// A request the partner has not answered yet: asks the server again.
    func refresh() {
        guard let booking, !isSending else { return }
        let before = state
        task = Task { [weak self] in
            guard let self else { return }
            if let fresh = try? await service.booking(id: booking.id), !Task.isCancelled { state = .done(fresh) } else {
                state = before
            }
        }
    }

    /// Back to the form after a failure, keeping the same key (the request may have reached the server).
    func edit() {
        if case .failed = state { state = .editing }
    }

    nonisolated static func failure(for error: Error) -> Failure {
        guard let error = error as? APIError else { return .other }
        switch error {
        case .server(422, "booking_not_supported", _): return .notSupported
        case .server(409, "booking_unavailable", _): return .unavailable
        case .server(422, _, _): return .invalid
        case .server(401, _, _): return .signedOut
        case .rateLimited(let retryAfter, _): return .rateLimited(retryAfter: retryAfter.map { Int($0.rounded(.up)) })
        case .network: return .network
        default: return .other
        }
    }
}
