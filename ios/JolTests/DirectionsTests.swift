import CoreLocation
@testable import Jol
import UIKit
import XCTest

@MainActor
private final class FakeLocator: LocationProviding {
    var result: LocationResult
    private(set) var calls = 0

    init(_ result: LocationResult) { self.result = result }

    func currentLocation() async -> LocationResult {
        calls += 1
        return result
    }
}

@MainActor
final class DirectionsTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let almaty = GeoPoint(lat: 43.231, lon: 76.935)
    private let place = PlaceSummary(
        id: UUID(uuidString: UITestSupport.centerPlaceID)!, name: "Fixture Museum", category: "museum", kind: "venue",
        lat: 43.238, lon: 76.945, isPublic: true, isPartner: false, popularity: 50
    )

    private func makeModel(_ locator: FakeLocator) -> DirectionsModel {
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(), installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return DirectionsModel(api: client, locator: locator)
    }

    private func wait(_ timeout: TimeInterval = 3, until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    private func requestBody() throws -> [String: Any] {
        let request = try XCTUnwrap(StubURLProtocol.requests.last { $0.url?.path == "/v1/directions" })
        let data = try XCTUnwrap(request.httpBody)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    // MARK: - Polyline

    func testPolylineDecodesGoogleReferenceVector() {
        // Reference vector from the Google polyline documentation (precision 5).
        let points = Polyline.decode("_p~iF~ps|U_ulLnnqC_mqNvxq`@", precision: 5)
        XCTAssertEqual(points.count, 3)
        XCTAssertEqual(points[0].latitude, 38.5, accuracy: 1e-9)
        XCTAssertEqual(points[0].longitude, -120.2, accuracy: 1e-9)
        XCTAssertEqual(points[1].latitude, 40.7, accuracy: 1e-9)
        XCTAssertEqual(points[1].longitude, -120.95, accuracy: 1e-9)
        XCTAssertEqual(points[2].latitude, 43.252, accuracy: 1e-9)
        XCTAssertEqual(points[2].longitude, -126.453, accuracy: 1e-9)
    }

    func testPolyline6DecodesServerExample() {
        // From docs/reviews/Ш-22.md: the server's walking example, Almaty, precision 6.
        let points = Polyline.decode("_f`nqA_m`wqCozDowH")
        XCTAssertEqual(points.count, 2)
        XCTAssertEqual(points[0].latitude, 43.238, accuracy: 1e-6)
        XCTAssertEqual(points[0].longitude, 76.94, accuracy: 1e-6)
        XCTAssertEqual(points[1].latitude, 43.241, accuracy: 1e-6)
        XCTAssertEqual(points[1].longitude, 76.945, accuracy: 1e-6)
    }

    func testPolylineHandlesEmptyAndTruncatedInput() {
        XCTAssertTrue(Polyline.decode("").isEmpty)
        // Cut in the middle of the second value: only complete pairs survive.
        XCTAssertEqual(Polyline.decode("_f`nqA_m`wqCozD").count, 1)
        XCTAssertTrue(Polyline.decode("\u{1}\u{2}!!").isEmpty)
    }

    // MARK: - Decoding and formatting

    private func payload(_ json: String = UITestSupport.directionsJSON) throws -> [DirectionOption] {
        try JSONDecoder().decode(DirectionsPayload.self, from: Data(json.utf8)).options
    }

    func testDecodesContractGroupsVariantsArrivalAndCongestion() throws {
        let options = try payload()
        XCTAssertEqual(options.map(\.mode), [.walk, .walk, .bus, .metro, .taxi])
        XCTAssertEqual(options.map(\.variant), [0, 1, 0, 1, 0])
        XCTAssertEqual(options[2].group, "transit")
        XCTAssertEqual(options[2].transitRef, "92")
        XCTAssertEqual(options[4].durationSMax, 660)
        XCTAssertEqual(options[0].line.count, 4)
        XCTAssertNil(options[0].congestion, "null → nothing")
        XCTAssertEqual(options[3].congestion, .medium)
        XCTAssertNotNil(options[2].arriveAt)
        XCTAssertEqual(DirectionsFormatting.arrival(options[2], departedAt: Date()), "14:35")
    }

    func testPagesFollowCarouselOrderAndMergeBusWithMetro() throws {
        let pages = TransportPage.pages(from: try payload())
        XCTAssertEqual(pages.map(\.kind), [.walk, .transit, .taxi], "scooter and car were not returned → no pages")
        XCTAssertEqual(pages[0].variants.count, 2)
        XCTAssertEqual(pages[1].variants.map(\.mode), [.bus, .metro])
    }

    func testOldServerShapeStillWorks() throws {
        // Today's server: a bare array, no group / variant / arrive_at / congestion, several buses.
        func item(_ mode: String, _ seconds: Int) -> String {
            "{\"mode\":\"\(mode)\",\"duration_s\":\(seconds),\"distance_m\":1000,\"cost_kzt_min\":0,"
                + "\"cost_kzt_max\":0,\"geometry\":\"_f`nqA_m`wqCozDowH\"}"
        }
        let json = "[\(item("car", 400)),\(item("bus", 2000)),\(item("walk", 900)),\(item("metro", 1500)),"
            + "\(item("taxi", 400)),\(item("scooter", 600))]"
        let options = try payload(json)
        XCTAssertFalse(options[0].recommended)
        XCTAssertNil(options[0].arriveAt)
        let pages = TransportPage.pages(from: options)
        XCTAssertEqual(pages.map(\.kind), [.walk, .transit, .taxi, .scooter, .car])
        XCTAssertEqual(pages[1].variants.map(\.mode), [.metro, .bus], "no variant field → fastest first")
        // Without `arrive_at` the arrival is departure + duration.
        let start = Date(timeIntervalSince1970: 1_800_000_000)
        // 1_800_000_000 = 2027-01-15 08:00 UTC = 13:00 in Almaty; the walk takes 900 s.
        XCTAssertEqual(DirectionsFormatting.arrival(options[2], departedAt: start), "13:15")
    }

    func testTransferShowsAllRouteNumbers() throws {
        let rides = ["62", "1"].map {
            "{\"type\":\"ride\",\"duration_s\":60,\"distance_m\":500,\"geometry\":\"\",\"route_ref\":\"\($0)\"}"
        }.joined(separator: ",")
        let json = "[{\"mode\":\"bus\",\"duration_s\":600,\"distance_m\":5000,\"cost_kzt_min\":100,"
            + "\"cost_kzt_max\":100,\"geometry\":\"\",\"approximate\":true,\"steps\":[\(rides)]}]"
        XCTAssertEqual(try payload(json)[0].transitRef, "62 → 1")
    }

    func testUnknownCongestionShapeIsIgnored() throws {
        let json = UITestSupport.directionsJSON.replacingOccurrences(
            of: "{\"level\":\"medium\"}", with: "{\"jam\":7}")
        XCTAssertNil(try payload(json)[3].congestion)
        XCTAssertNil(DirectionsFormatting.congestion(try payload()[0]), "walking has no congestion text")
        XCTAssertNotNil(DirectionsFormatting.congestion(try payload()[3]))
    }

    func testFormatting() throws {
        let options = try payload()
        XCTAssertEqual(DirectionsFormatting.duration(options[0], language: "en"), "21 min")
        XCTAssertEqual(DirectionsFormatting.duration(options[2], language: "en"), "≈ 13 min")
        XCTAssertEqual(DirectionsFormatting.duration(options[4], language: "ru"), "7–11 мин")
        XCTAssertEqual(DirectionsFormatting.price(options[0], language: "en"), "Free")
        XCTAssertEqual(DirectionsFormatting.price(options[0], language: "ru"), "Бесплатно")
        XCTAssertEqual(DirectionsFormatting.price(options[2], language: "en"), "≈ 120\u{00A0}₸")
        XCTAssertEqual(DirectionsFormatting.price(options[4], language: "en"), "900–1\u{00A0}500\u{00A0}₸")
        XCTAssertEqual(DirectionsFormatting.clock(65, language: "en"), "1 h 5 min")
        XCTAssertEqual(DirectionsFormatting.clock(120, language: "ru"), "2 ч")
        XCTAssertEqual(DirectionsFormatting.distance(650, language: "en"), "650 m")
        XCTAssertEqual(DirectionsFormatting.distance(5200, language: "en"), "5.2 km")
    }

    func testEveryModeHasSymbol() {
        for mode in TransportMode.allCases {
            XCTAssertNotNil(UIImage(systemName: DirectionsFormatting.symbol(mode)), mode.rawValue)
        }
    }

    // MARK: - Flow

    func testLocatedUserRequestsFromLocationAndOpensOnTheWalkPage() async throws {
        StubURLProtocol.install { okDirections($0) }
        let model = makeModel(FakeLocator(.located(almaty)))
        model.start(to: place, mapCenter: GeoPoint(lat: 43.2, lon: 76.9))
        await wait { model.phase == .loaded }
        XCTAssertEqual(model.phase, .loaded)
        XCTAssertNil(model.fallback)
        XCTAssertEqual(model.pages.map(\.kind), [.walk, .transit, .taxi])
        XCTAssertEqual(model.currentPage?.kind, .walk, "always opens on walking, not on the recommended page")
        XCTAssertEqual(model.lines.count, 2, "every variant of the page is drawn")
        XCTAssertEqual(model.lines.map(\.selected), [true, false])
        XCTAssertEqual(model.origin, almaty)

        let body = try requestBody()
        let from = try XCTUnwrap(body["from"] as? [String: Double])
        XCTAssertEqual(from["lat"], 43.231)
        XCTAssertEqual(from["lon"], 76.935)
        XCTAssertEqual(body["to_place_id"] as? String, UITestSupport.centerPlaceID)
        XCTAssertNil(body["to"])
        let request = try XCTUnwrap(StubURLProtocol.requests.last)
        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"), "works for a guest")
    }

    func testCarouselIsCircular() async {
        StubURLProtocol.install { okDirections($0) }
        let model = makeModel(FakeLocator(.located(almaty)))
        model.start(to: place, mapCenter: nil)
        await wait { model.phase == .loaded }
        var visited = [model.currentPage?.kind]
        for _ in 0..<3 {
            model.showNext()
            visited.append(model.currentPage?.kind)
        }
        XCTAssertEqual(visited, [.walk, .transit, .taxi, .walk], "starts on walk; after the last page comes the first")
        model.showPrevious()
        XCTAssertEqual(model.currentPage?.kind, .taxi, "and before the first comes the last")
        model.showPage(9)  // out of range → ignored
        XCTAssertEqual(model.currentPage?.kind, .taxi)
    }

    func testSelectingAVariantHighlightsItsLineAndKeepsCamera() async {
        StubURLProtocol.install { okDirections($0) }
        let model = makeModel(FakeLocator(.located(almaty)))
        model.start(to: place, mapCenter: nil)
        await wait { model.phase == .loaded }
        let version = model.lineVersion
        let fit = model.fitVersion
        model.selectVariant(1)
        XCTAssertEqual(model.lines.map(\.selected), [false, true])
        XCTAssertGreaterThan(model.lineVersion, version)
        XCTAssertEqual(model.fitVersion, fit, "choosing a variant does not move the camera")
        model.selectVariant(7)  // out of range → ignored
        XCTAssertEqual(model.lines.map(\.selected), [false, true])
        model.showNext()
        XCTAssertGreaterThan(model.fitVersion, fit, "turning the page refits the camera")
        model.showPrevious()
        XCTAssertEqual(model.lines.map(\.selected), [false, true], "the choice is remembered per page")
    }

    func testDeniedLocationFallsBackToMapCenter() async throws {
        StubURLProtocol.install { okDirections($0) }
        let center = GeoPoint(lat: 43.25, lon: 76.92)
        let model = makeModel(FakeLocator(.denied))
        model.start(to: place, mapCenter: center)
        await wait { model.phase == .loaded }
        XCTAssertEqual(model.fallback, .denied)
        XCTAssertEqual(model.origin, center)
        let from = try XCTUnwrap(requestBody()["from"] as? [String: Double])
        XCTAssertEqual(from["lat"], 43.25)
    }

    func testLocationOutsideAlmatyFallsBackWithoutAskingServerFromThere() async throws {
        StubURLProtocol.install { okDirections($0) }
        let model = makeModel(FakeLocator(.located(GeoPoint(lat: 37.33, lon: -122.03))))
        model.start(to: place, mapCenter: GeoPoint(lat: 43.24, lon: 76.94))
        await wait { model.phase == .loaded }
        XCTAssertEqual(model.fallback, .outsideArea)
        let from = try XCTUnwrap(requestBody()["from"] as? [String: Double])
        XCTAssertEqual(from["lat"], 43.24)
        XCTAssertEqual(StubURLProtocol.requests.filter { $0.url?.path == "/v1/directions" }.count, 1)
    }

    func testMapCenterOutsideEveryRegionFailsLocally() async {
        StubURLProtocol.install { okDirections($0) }
        let model = makeModel(FakeLocator(.unavailable))
        model.start(to: place, mapCenter: GeoPoint(lat: 55.75, lon: 37.62)) // Moscow: outside every region (Ш-59)
        await wait { model.phase != .locating }
        XCTAssertEqual(model.phase, .failed(.outsideArea))
        XCTAssertTrue(StubURLProtocol.requests.filter { $0.url?.path == "/v1/directions" }.isEmpty)
    }

    func testChoosingMapCenterAndBackToLocation() async {
        StubURLProtocol.install { okDirections($0) }
        let locator = FakeLocator(.located(almaty))
        let model = makeModel(locator)
        model.start(to: place, mapCenter: nil)
        await wait { model.phase == .loaded }
        model.useMapCenter(GeoPoint(lat: 43.26, lon: 76.95))
        await wait { model.fallback == .chosen && model.phase == .loaded }
        XCTAssertEqual(model.origin, GeoPoint(lat: 43.26, lon: 76.95))
        model.useCurrentLocation()
        await wait { model.fallback == nil && model.phase == .loaded }
        XCTAssertEqual(model.origin, almaty)
        XCTAssertEqual(locator.calls, 2)
    }

    func testServerErrorsMapToFailuresAndRetryWorks() async {
        let failing = Counter()
        StubURLProtocol.install { request in
            if failing.next() == 0 {
                let body = Data("{\"error\":{\"code\":\"routing_unavailable\",\"message\":\"x\"}}".utf8)
                return (StubURLProtocol.response(request.url!, status: 503), body)
            }
            return okDirections(request)
        }
        let model = makeModel(FakeLocator(.located(almaty)))
        model.start(to: place, mapCenter: nil)
        await wait { model.phase == .failed(.serviceUnavailable) }
        XCTAssertEqual(model.phase, .failed(.serviceUnavailable))
        model.retry()
        await wait { model.phase == .loaded }
        XCTAssertEqual(model.phase, .loaded)
    }

    func testEmptyAnswerIsLoadedWithNoOptions() async {
        StubURLProtocol.install { (StubURLProtocol.response($0.url!), Data("[]".utf8)) }
        let model = makeModel(FakeLocator(.located(almaty)))
        model.start(to: place, mapCenter: nil)
        await wait { model.phase == .loaded }
        XCTAssertTrue(model.pages.isEmpty)
        XCTAssertTrue(model.lines.isEmpty)
    }

    func testResetClearsEverythingAndDropsLateAnswer() async {
        StubURLProtocol.install { okDirections($0) }
        let model = makeModel(FakeLocator(.located(almaty)))
        model.start(to: place, mapCenter: nil)
        model.reset()
        try? await Task.sleep(for: .milliseconds(150))
        XCTAssertEqual(model.phase, .idle)
        XCTAssertTrue(model.pages.isEmpty)
        XCTAssertFalse(model.isActive)
    }
}

extension DirectionsTests {
    func testWithoutAWalkPageItOpensOnTheNextAvailableOne() async {
        // No walking option for this pair of points: the first page in carousel order is public transport.
        StubURLProtocol.install { request in
            let body = "[{\"mode\":\"taxi\",\"duration_s\":420,\"distance_m\":5000,\"cost_kzt_min\":900,"
                + "\"cost_kzt_max\":1500,\"geometry\":\"oprmqAotvvqC_|BozD\",\"approximate\":false,"
                + "\"recommended\":true},{\"mode\":\"bus\",\"duration_s\":900,\"distance_m\":5200,"
                + "\"cost_kzt_min\":120,\"cost_kzt_max\":120,\"geometry\":\"oprmqAotvvqC_|BozD\","
                + "\"approximate\":true,\"recommended\":false}]"
            return (StubURLProtocol.response(request.url!), Data(body.utf8))
        }
        let model = makeModel(FakeLocator(.located(almaty)))
        model.start(to: place, mapCenter: nil)
        await wait { model.phase == .loaded }
        XCTAssertEqual(model.pages.map(\.kind), [.transit, .taxi])
        XCTAssertEqual(model.currentPage?.kind, .transit, "walk missing: next page in order")
    }
}

private func okDirections(_ request: URLRequest) -> (HTTPURLResponse, Data) {
    (StubURLProtocol.response(request.url!), Data(UITestSupport.directionsJSON.utf8))
}

private final class Counter: @unchecked Sendable {
    private let lock = NSLock()
    private var value = -1

    func next() -> Int {
        lock.lock(); defer { lock.unlock() }
        value += 1
        return value
    }
}

/// Ш-59: an intercity taxi (3 h 41 min – 4 h 37 min) shows both ends in hours, not "221–4 h 37 min".
final class LongTripFormattingTests: XCTestCase {
    func testLongRangeShowsHoursOnBothEnds() throws {
        let json = UITestSupport.directionsJSON.replacingOccurrences(
            of: "\"duration_s_min\":420,\"duration_s_max\":660",
            with: "\"duration_s_min\":13260,\"duration_s_max\":16620")
        let options = try JSONDecoder().decode(DirectionsPayload.self, from: Data(json.utf8)).options
        XCTAssertEqual(DirectionsFormatting.duration(options[4], language: "en"), "3 h 41 min – 4 h 37 min")
    }
}
