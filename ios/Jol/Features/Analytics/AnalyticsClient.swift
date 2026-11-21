import Foundation

/// Sends the few events the server cannot see itself (Ш-50, `POST /v1/analytics/events`): the first launch, every
/// launch, a route started in a navigator. Events go to a queue on disk first, then leave in batches of up to 50:
///
/// - `X-Install-ID` always (the API client adds it), the bearer token when signed in (the server links the install to
///   the account; a stale token is ignored there, so analytics never fails over a session);
/// - the event `id` is made once, so a batch that is sent twice because the answer was lost does not count twice;
/// - an event older than 7 days is dropped (the server refuses it anyway); the queue holds at most `maxQueued`;
/// - 429, no network and 5xx keep the events and back off (the server's `Retry-After` when it sends one, otherwise
///   1, 2, 4 … minutes up to an hour); another 4xx means the batch itself is bad, so it is dropped, not repeated.
@MainActor
final class AnalyticsClient {
    static let installedKey = "jol.analytics_installed"
    static let maxAge: TimeInterval = 7 * 24 * 3600
    static let maxQueued = 500
    static let baseBackoff: TimeInterval = 60
    static let maxBackoff: TimeInterval = 3600

    private let api: APIClient
    private let store: AnalyticsQueueStore
    private let defaults: UserDefaults
    private let now: () -> Date
    private let flushDelay: TimeInterval
    private let appVersion: String
    private let language: () -> String

    private(set) var queue: [AnalyticsEvent]
    /// No attempt before this moment (a `429` or another failure told us to wait).
    private(set) var retryNotBefore: Date?
    private var backoff = AnalyticsClient.baseBackoff
    private var isFlushing = false
    private var timer: Task<Void, Never>?

    init(
        api: APIClient, store: AnalyticsQueueStore = AnalyticsQueueStore(), defaults: UserDefaults = .standard,
        language: @escaping () -> String = { "en" }, now: @escaping () -> Date = Date.init,
        flushDelay: TimeInterval = 10,
        appVersion: String = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
    ) {
        self.api = api
        self.store = store
        self.defaults = defaults
        self.language = language
        self.now = now
        self.flushDelay = flushDelay
        self.appVersion = appVersion
        self.queue = store.load()
    }

    // MARK: - Events

    /// Once per launch: `app_install` the very first time, then `app_launch`.
    func trackLaunch() {
        var props = ["locale": language()]
        if !appVersion.isEmpty { props["app_version"] = appVersion }
        if !defaults.bool(forKey: Self.installedKey) {
            defaults.set(true, forKey: Self.installedKey)
            enqueue(AnalyticsEvent(name: AnalyticsName.install, ts: now(), props: props))
        }
        enqueue(AnalyticsEvent(name: AnalyticsName.launch, ts: now(), props: props))
    }

    /// A route was started in a navigator. `placeID` when the target is a place; `mode` when the person picked one.
    func trackDirectionsStart(placeID: UUID?, mode: TransportMode?) {
        let props = mode.map { ["mode": $0.rawValue] } ?? [:]
        enqueue(AnalyticsEvent(name: AnalyticsName.directionsStart, ts: now(), placeID: placeID, props: props))
    }

    private func enqueue(_ event: AnalyticsEvent) {
        queue.append(event)
        if queue.count > Self.maxQueued { queue.removeFirst(queue.count - Self.maxQueued) }
        store.save(queue)
        if queue.count >= AnalyticsBatch.maxEvents {
            Task { await flush() }
        } else {
            schedule(after: flushDelay)
        }
    }

    // MARK: - Sending

    /// Sends what is queued, a batch at a time, until the queue is empty or a failure says to wait.
    func flush(force: Bool = false) async {
        guard !isFlushing else { return }
        isFlushing = true
        defer { isFlushing = false }
        while true {
            dropOld()
            if !force, let wait = retryNotBefore, wait > now() { return schedule(after: wait.timeIntervalSince(now())) }
            let batch = Array(queue.prefix(AnalyticsBatch.maxEvents))
            guard !batch.isEmpty else { return }
            if await send(batch) == false { return }
        }
    }

    /// `true` when the batch is gone from the queue (delivered or dropped), `false` when it stays and we back off.
    private func send(_ batch: [AnalyticsEvent]) async -> Bool {
        do {
            let body = AnalyticsBatch(sentAt: now(), events: batch)
            try await api.send(Endpoint.post("v1/analytics/events", json: body))
            remove(batch)
            backoff = Self.baseBackoff
            retryNotBefore = nil
            return true
        } catch let error as APIError {
            switch error {
            case .rateLimited(let retryAfter, _):
                wait(atLeast: retryAfter)
                return false
            case .server(let status, _, _) where (400..<500).contains(status) && status != 401 && status != 408:
                remove(batch) // the batch itself is refused; repeating it would never help
                return true
            default:
                wait(atLeast: nil)
                return false
            }
        } catch {
            wait(atLeast: nil)
            return false
        }
    }

    private func wait(atLeast retryAfter: TimeInterval?) {
        let delay = max(retryAfter ?? 0, backoff)
        backoff = min(backoff * 2, Self.maxBackoff)
        retryNotBefore = now().addingTimeInterval(delay)
        schedule(after: delay)
    }

    private func remove(_ batch: [AnalyticsEvent]) {
        let sent = Set(batch.map(\.id))
        queue.removeAll { sent.contains($0.id) }
        store.save(queue)
    }

    private func dropOld() {
        let limit = now().addingTimeInterval(-Self.maxAge)
        let kept = queue.filter { $0.ts >= limit }
        if kept.count != queue.count {
            queue = kept
            store.save(queue)
        }
    }

    private func schedule(after delay: TimeInterval) {
        timer?.cancel()
        guard flushDelay > 0 else { return }
        timer = Task { [weak self] in
            try? await Task.sleep(for: .seconds(max(delay, 1)))
            guard !Task.isCancelled else { return }
            await self?.flush()
        }
    }
}
