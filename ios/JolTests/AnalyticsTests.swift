@testable import Jol
import XCTest

/// Ш-50: the local queue, batches, retries and back-off of the analytics client.
@MainActor
final class AnalyticsTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let installID = "6F9619FF-8B86-4011-B42D-00C04FC964FF"
    private var defaults: UserDefaults!
    private var suite: String!
    private var file: URL!
    private var clock = Date(timeIntervalSince1970: 1_800_000_000)

    override func setUp() async throws {
        try await super.setUp()
        suite = "jol-analytics-\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suite)
        file = FileManager.default.temporaryDirectory.appending(path: "jol-analytics-\(UUID().uuidString).json")
        clock = Date(timeIntervalSince1970: 1_800_000_000)
    }

    override func tearDown() async throws {
        defaults.removePersistentDomain(forName: suite)
        try? FileManager.default.removeItem(at: file)
        try await super.tearDown()
    }

    private func make(signedIn: Bool = false) -> AnalyticsClient {
        let store = MemoryTokenStore(signedIn ? SessionTokens(accessToken: "access-1", refreshToken: "refresh-1") : nil)
        let client = APIClient(
            baseURL: .success(base), tokens: store, installID: installID,
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return AnalyticsClient(
            api: client, store: AnalyticsQueueStore(url: file), defaults: defaults, language: { "ru" },
            now: { [unowned self] in clock }, flushDelay: 0, appVersion: "0.1.0"
        )
    }

    private func okAnswer() {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!), Data("{\"accepted\":1,\"duplicates\":0,\"rejected\":0}".utf8))
        }
    }

    private func body(_ request: URLRequest) throws -> [String: Any] {
        let data = try XCTUnwrap(request.httpBody)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func events(_ request: URLRequest) throws -> [[String: Any]] {
        try XCTUnwrap(try body(request)["events"] as? [[String: Any]])
    }

    // MARK: - Events

    func testFirstLaunchQueuesInstallThenLaunchAndLaterLaunchesOnlyLaunch() throws {
        let analytics = make()
        analytics.trackLaunch()
        XCTAssertEqual(analytics.queue.map(\.name), ["app_install", "app_launch"])
        XCTAssertEqual(analytics.queue[0].props, ["locale": "ru", "app_version": "0.1.0"])

        let again = make() // the next launch: the queue on disk is still there
        XCTAssertEqual(again.queue.count, 2, "the queue survives a restart")
        again.trackLaunch()
        XCTAssertEqual(again.queue.map(\.name), ["app_install", "app_launch", "app_launch"])
    }

    func testDirectionsStartCarriesPlaceAndModeAndNothingElse() async throws {
        okAnswer()
        let analytics = make()
        let place = UUID()
        analytics.trackDirectionsStart(placeID: place, mode: .scooter)
        analytics.trackDirectionsStart(placeID: nil, mode: nil)
        await analytics.flush()

        let sent = try events(try XCTUnwrap(StubURLProtocol.requests.first))
        XCTAssertEqual(sent.count, 2)
        XCTAssertEqual(sent[0]["name"] as? String, "directions_start")
        XCTAssertEqual(sent[0]["place_id"] as? String, place.uuidString.lowercased())
        XCTAssertEqual((sent[0]["props"] as? [String: String]), ["mode": "scooter"])
        XCTAssertNil(sent[1]["place_id"])
        XCTAssertNil(sent[1]["props"])
        let allowed: Set<String> = ["id", "name", "ts", "place_id", "props"]
        for event in sent { XCTAssertTrue(Set(event.keys).isSubset(of: allowed), "\(event.keys)") }
    }

    // MARK: - The request

    func testBatchShapeHeadersAndTheBearer() async throws {
        okAnswer()
        let analytics = make(signedIn: true)
        analytics.trackLaunch()
        await analytics.flush()

        let request = try XCTUnwrap(StubURLProtocol.requests.first)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/v1/analytics/events")
        XCTAssertEqual(request.value(forHTTPHeaderField: "X-Install-ID"), installID)
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer access-1")
        let json = try body(request)
        XCTAssertEqual(Set(json.keys), ["sent_at", "events"])
        let sentAt = try XCTUnwrap(json["sent_at"] as? String)
        XCTAssertNotNil(ISO8601DateFormatter().date(from: sentAt), sentAt)
        let first = try XCTUnwrap(try events(request).first)
        XCTAssertNotNil(UUID(uuidString: try XCTUnwrap(first["id"] as? String)))
        XCTAssertNotNil(ISO8601DateFormatter().date(from: try XCTUnwrap(first["ts"] as? String)))
        XCTAssertTrue(analytics.queue.isEmpty, "delivered events leave the queue")
    }

    func testAGuestSendsNoBearer() async throws {
        okAnswer()
        let analytics = make()
        analytics.trackLaunch()
        await analytics.flush()
        XCTAssertNil(StubURLProtocol.requests[0].value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(StubURLProtocol.requests[0].value(forHTTPHeaderField: "X-Install-ID"), installID)
    }

    func testMoreThanFiftyEventsGoInBatchesOfFifty() async throws {
        okAnswer()
        let analytics = make()
        for _ in 0..<120 { analytics.trackDirectionsStart(placeID: nil, mode: .walk) }
        await analytics.flush()
        let sizes = try StubURLProtocol.requests.map { try events($0).count }
        XCTAssertEqual(sizes, [50, 50, 20])
        XCTAssertTrue(analytics.queue.isEmpty)
    }

    // MARK: - Failures

    func testARetryKeepsTheSameEventIDs() async throws {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let analytics = make()
        analytics.trackLaunch()
        await analytics.flush()
        XCTAssertEqual(analytics.queue.count, 2, "no network: the events stay")
        let firstIDs = try events(StubURLProtocol.requests[0]).compactMap { $0["id"] as? String }

        okAnswer()
        clock = clock.addingTimeInterval(120)
        await analytics.flush()
        let retried = try events(StubURLProtocol.requests[0]).compactMap { $0["id"] as? String }
        XCTAssertEqual(retried, firstIDs, "a retry is the same events with the same ids, so the server dedupes")
        XCTAssertTrue(analytics.queue.isEmpty)
    }

    func testRateLimitBacksOffForRetryAfterAndThenSends() async throws {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!, status: 429, headers: ["Retry-After": "600"]),
             Data("{\"error\":{\"code\":\"rate_limited\",\"message\":\"slow\"}}".utf8))
        }
        let analytics = make()
        analytics.trackLaunch()
        await analytics.flush()
        XCTAssertEqual(StubURLProtocol.requests.count, 1)
        XCTAssertEqual(analytics.retryNotBefore, clock.addingTimeInterval(600))
        XCTAssertEqual(analytics.queue.count, 2)

        await analytics.flush() // too early: nothing is sent
        XCTAssertEqual(StubURLProtocol.requests.count, 1)

        okAnswer()
        clock = clock.addingTimeInterval(601)
        await analytics.flush()
        XCTAssertEqual(StubURLProtocol.requests.count, 1)
        XCTAssertTrue(analytics.queue.isEmpty)
        XCTAssertNil(analytics.retryNotBefore)
    }

    func testBackoffGrowsWithoutRetryAfterAndIsCapped() async throws {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!, status: 503), Data("{}".utf8))
        }
        let analytics = make()
        analytics.trackLaunch()
        var waits: [TimeInterval] = []
        for _ in 0..<9 {
            await analytics.flush(force: true)
            waits.append(try XCTUnwrap(analytics.retryNotBefore).timeIntervalSince(clock))
        }
        XCTAssertEqual(waits, [60, 120, 240, 480, 960, 1920, 3600, 3600, 3600])
        XCTAssertEqual(analytics.queue.count, 2)
    }

    func testARefusedBatchIsDroppedNotRepeated() async throws {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!, status: 422),
             Data("{\"error\":{\"code\":\"validation_error\",\"message\":\"bad\"}}".utf8))
        }
        let analytics = make()
        analytics.trackLaunch()
        await analytics.flush()
        XCTAssertTrue(analytics.queue.isEmpty)
        XCTAssertNil(analytics.retryNotBefore)
        await analytics.flush()
        XCTAssertEqual(StubURLProtocol.requests.count, 1)
    }

    func testEventsOlderThanSevenDaysAreDroppedBeforeSending() async throws {
        okAnswer()
        let analytics = make()
        analytics.trackDirectionsStart(placeID: nil, mode: .walk) // happens now
        clock = clock.addingTimeInterval(6 * 24 * 3600)
        analytics.trackDirectionsStart(placeID: nil, mode: .bus)
        clock = clock.addingTimeInterval(2 * 24 * 3600) // the first is 8 days old, the second 2
        await analytics.flush()
        let sent = try events(StubURLProtocol.requests[0])
        XCTAssertEqual(sent.count, 1)
        XCTAssertEqual((sent[0]["props"] as? [String: String])?["mode"], "bus")
    }

    func testAnOnlyStaleQueueSendsNothing() async throws {
        okAnswer()
        let analytics = make()
        analytics.trackLaunch()
        clock = clock.addingTimeInterval(8 * 24 * 3600)
        await analytics.flush()
        XCTAssertTrue(StubURLProtocol.requests.isEmpty)
        XCTAssertTrue(analytics.queue.isEmpty)
    }

    func testTheQueueIsCapped() throws {
        let analytics = make()
        for _ in 0..<(AnalyticsClient.maxQueued + 25) { analytics.trackDirectionsStart(placeID: nil, mode: .walk) }
        XCTAssertEqual(analytics.queue.count, AnalyticsClient.maxQueued)
    }
}
