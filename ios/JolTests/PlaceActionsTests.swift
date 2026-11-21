import CoreLocation
@testable import Jol
import XCTest

@MainActor
private final class TestLocator: LocationProviding {
    var result: LocationResult
    private(set) var calls = 0

    init(_ result: LocationResult) { self.result = result }

    func currentLocation() async -> LocationResult {
        calls += 1
        return result
    }
}

/// Ш-47 crowd, Ш-48 events, Ш-49 bookings: decoding of the card fields and the requests the app sends.
@MainActor
final class PlaceActionsTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let placeID = UUID(uuidString: UITestSupport.secondPlaceID)!
    private let here = GeoPoint(lat: 43.248, lon: 76.957)

    private func client() -> APIClient {
        APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r")),
            installID: "install-1", session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
    }

    private func wait(_ timeout: TimeInterval = 3, until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    private func json(_ request: URLRequest) throws -> [String: Any] {
        let data = try XCTUnwrap(request.httpBody)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func reply(_ status: Int, _ body: String, headers: [String: String] = [:]) {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!, status: status, headers: headers), Data(body.utf8))
        }
    }

    // MARK: - Card fields

    private func detail(_ id: String) throws -> PlaceDetail {
        try JSONDecoder().decode(PlaceDetail.self, from: Data(UITestSupport.detailJSON(id: id).utf8))
    }

    func testCardCarriesCrowdBookingAndEventsOnlyWhereTheServerSentThem() throws {
        let cafe = try detail(UITestSupport.secondPlaceID)
        XCTAssertEqual(cafe.crowd?.now?.label, "busy")
        XCTAssertEqual(cafe.crowd?.today.count, 3)
        XCTAssertEqual(cafe.booking?.isAvailable, true)
        XCTAssertEqual(cafe.booking?.supportedKinds, [.table, .ticket])
        XCTAssertEqual(cafe.events?.first?.isAd, true)
        let museum = try detail(UITestSupport.centerPlaceID)
        XCTAssertNil(museum.crowd)
        XCTAssertNil(museum.booking)
    }

    func testAdLabelOnlyWhenFlaggedAndNeverInvented() throws {
        let plain = """
        {"id":"\(UUID().uuidString)","title":"Fair","lat":43.2,"lon":76.9,"is_ad":false,"ad_label":null}
        """
        XCTAssertNil(try JSONDecoder().decode(EventItem.self, from: Data(plain.utf8)).visibleAdLabel)
        let ad = """
        {"id":"\(UUID().uuidString)","title":"Jazz","lat":43.2,"lon":76.9,"is_ad":true,"ad_label":"Реклама"}
        """
        XCTAssertEqual(try JSONDecoder().decode(EventItem.self, from: Data(ad.utf8)).visibleAdLabel, "Реклама")
    }

    // MARK: - Crowd

    func testCheckInSendsTheCurrentLocationAndReportsTheLevel() async throws {
        reply(200, "{\"recorded\":true,\"distance_m\":55}")
        let model = CrowdModel(api: client(), locator: TestLocator(.located(here)))
        model.perform(.checkIn, placeID: placeID)
        await wait { model.outcome != nil }
        XCTAssertEqual(model.outcome, .recorded(.checkIn))
        var request = try XCTUnwrap(StubURLProtocol.requests.last)
        XCTAssertEqual(request.url?.path, "/v1/places/\(placeID.uuidString.lowercased())/checkin")
        XCTAssertEqual(try json(request)["lat"] as? Double, 43.248)
        XCTAssertNil(try json(request)["level"])

        model.perform(.report(.busy), placeID: placeID)
        await wait { model.outcome == .recorded(.report(.busy)) }
        request = try XCTUnwrap(StubURLProtocol.requests.last)
        XCTAssertTrue(request.url?.path.hasSuffix("/crowd") == true)
        XCTAssertEqual(try json(request)["level"] as? String, "busy")
    }

    func testCrowdFailuresAreTold() async {
        let locator = TestLocator(.located(here))
        let model = CrowdModel(api: client(), locator: locator)
        reply(200, "{\"recorded\":false,\"distance_m\":10}")
        model.perform(.checkIn, placeID: placeID)
        await wait { model.outcome != nil }
        XCTAssertEqual(model.outcome, .alreadyRecorded(.checkIn))

        reply(422, "{\"error\":{\"code\":\"too_far_from_place\",\"message\":\"far\"}}")
        model.perform(.checkIn, placeID: placeID)
        await wait { model.outcome == .tooFar }
        XCTAssertEqual(model.outcome, .tooFar)

        reply(429, "{\"error\":{\"code\":\"rate_limited\",\"message\":\"slow\"}}", headers: ["Retry-After": "90"])
        model.perform(.report(.empty), placeID: placeID)
        await wait { model.outcome == .rateLimited(retryAfter: 90) }
        XCTAssertEqual(model.outcome, .rateLimited(retryAfter: 90))

        reply(500, "{}")
        model.perform(.checkIn, placeID: placeID)
        await wait { model.outcome == .failed }
        XCTAssertEqual(model.outcome, .failed)
    }

    func testNoLocationMeansNoRequest() async {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), Data()) }
        let locator = TestLocator(.denied)
        let model = CrowdModel(api: client(), locator: locator)
        model.perform(.checkIn, placeID: placeID)
        await wait { model.outcome != nil }
        XCTAssertEqual(model.outcome, .locationDenied)
        locator.result = .unavailable
        model.perform(.checkIn, placeID: placeID)
        await wait { model.outcome == .locationUnavailable }
        XCTAssertEqual(model.outcome, .locationUnavailable)
        XCTAssertTrue(StubURLProtocol.requests.isEmpty, "the server is not asked without a position")
    }

    // MARK: - Events

    func testEventsAreRequestedForTheNextTwoWeeksInsideTheArea() async throws {
        reply(200, "{\"items\":[\(UITestSupport.eventsItemsJSON)]}")
        let now = Date(timeIntervalSince1970: 1_796_000_000)  // 2026-11-30 in Almaty
        let model = EventsModel(api: client(), debounce: .milliseconds(10), today: { now })
        model.regionChanged(GeoBounds(west: 76.8, south: 43.15, east: 77.0, north: 43.3))
        await wait { !model.items.isEmpty }
        XCTAssertEqual(model.items.count, 2)
        let request = try XCTUnwrap(StubURLProtocol.requests.last)
        let items = URLComponents(url: request.url!, resolvingAgainstBaseURL: false)?.queryItems ?? []
        XCTAssertEqual(items.first { $0.name == "from" }?.value, EventsModel.dateString(now))
        let end = EventsModel.dateString(now.addingTimeInterval(14 * 86_400))
        XCTAssertEqual(items.first { $0.name == "to" }?.value, end)
        XCTAssertNotNil(items.first { $0.name == "bbox" })
        model.select(model.items[0].id)
        XCTAssertEqual(model.selected?.title, "Fixture Jazz Night")
    }

    // MARK: - Bookings

    private func request(_ kind: BookingKind = .table, party: Int = 2) -> BookingRequest {
        BookingRequest(placeID: placeID, kind: kind, partySize: party, startsAt: "2026-12-05T19:00:00+05:00",
                       endsAt: nil, note: nil)
    }

    private let bookingJSON = """
    {"id":"12121212-1212-4212-8212-121212121212","place":{"id":"\(UITestSupport.secondPlaceID)","name":"Fixture Cafe"},\
    "kind":"table","status":"confirmed","party_size":2,"starts_at":"2026-12-05T19:00:00+05:00"}
    """

    func testBookingBodyAndIdempotencyKey() async throws {
        reply(201, bookingJSON)
        let model = BookingModel(api: client())
        model.submit(request())
        await wait { model.booking != nil }
        XCTAssertEqual(model.booking?.status, "confirmed")
        let first = try XCTUnwrap(StubURLProtocol.requests.last)
        XCTAssertEqual(first.url?.path, "/v1/bookings")
        let body = try json(first)
        XCTAssertEqual(body["kind"] as? String, "table")
        XCTAssertEqual(body["party_size"] as? Int, 2)
        XCTAssertEqual(body["starts_at"] as? String, "2026-12-05T19:00:00+05:00")
        XCTAssertEqual(body["place_id"] as? String, placeID.uuidString.lowercased())
        XCTAssertNil(body["ends_at"])
        let key = try XCTUnwrap(first.value(forHTTPHeaderField: "Idempotency-Key"))
        XCTAssertFalse(key.isEmpty)
    }

    func testRetryKeepsTheKeyAChangedFormGetsANewOne() async throws {
        reply(503, "{}")
        let model = BookingModel(api: client())
        model.submit(request())
        await wait { model.state == .failed(.other) }
        model.edit()
        model.submit(request())
        await wait { StubURLProtocol.requests.count == 2 && !model.isSending }
        model.edit()
        model.submit(request(party: 4))
        await wait { StubURLProtocol.requests.count == 3 && !model.isSending }
        let keys = StubURLProtocol.requests.map { $0.value(forHTTPHeaderField: "Idempotency-Key") }
        XCTAssertEqual(keys[0], keys[1], "the same request again is a retry")
        XCTAssertNotEqual(keys[1], keys[2], "a different request is a different booking")
    }

    func testBookingFailureMapping() {
        func failure(_ status: Int, _ code: String) -> BookingModel.Failure {
            BookingModel.failure(for: APIError.server(status: status, code: code, message: ""))
        }
        XCTAssertEqual(failure(422, "booking_not_supported"), .notSupported)
        XCTAssertEqual(failure(409, "booking_unavailable"), .unavailable)
        XCTAssertEqual(failure(422, "validation_error"), .invalid)
        XCTAssertEqual(failure(401, "unauthorized"), .signedOut)
        let limited = APIError.rateLimited(retryAfter: 30, message: "")
        XCTAssertEqual(BookingModel.failure(for: limited), .rateLimited(retryAfter: 30))
        XCTAssertEqual(BookingModel.failure(for: APIError.network(URLError(.timedOut))), .network)
    }

    func testButtonStaysOffWithoutAKnownKind() throws {
        func info(_ json: String) throws -> BookingInfo {
            try JSONDecoder().decode(BookingInfo.self, from: Data(json.utf8))
        }
        let none = try info("{\"available\":true,\"kinds\":[\"spaceship\"]}")
        XCTAssertFalse(none.isAvailable)
        let off = try info("{\"available\":false,\"kinds\":[\"table\"]}")
        XCTAssertFalse(off.isAvailable)
    }
}
