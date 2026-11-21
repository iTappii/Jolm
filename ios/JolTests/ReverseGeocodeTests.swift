@testable import Jol
import XCTest

private func reply(_ text: String, status: Int = 200, _ request: URLRequest) -> (HTTPURLResponse, Data) {
    (StubURLProtocol.response(request.url!, status: status), Data(text.utf8))
}

private let addressJSON = """
{"kind":"address","address":"улица Панфилова 98","name":null,"lat":43.25797,"lon":76.94506,"distance_m":9}
"""

/// Ш-23c: a tap on the map that hit no pin → `GET /v1/geocode/reverse` → the card of a place, an address or a point.
@MainActor
final class ReverseGeocodeTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let almaty = GeoPoint(lat: 43.2579, lon: 76.9450)

    private func makeModel() -> PlacesModel {
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(), installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return PlacesModel(api: client, debounce: .milliseconds(30))
    }

    private func wait(_ timeout: TimeInterval = 3, until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    private func geocodeRequests() -> [URLRequest] {
        StubURLProtocol.requests.filter { $0.url?.path == "/v1/geocode/reverse" }
    }

    // MARK: - Decoding

    func testDecodesPlaceAddressBuildingAndPoint() throws {
        let decoder = JSONDecoder()
        let museum = UITestSupport.summary(UITestSupport.centerPlaceID, "Fixture Museum", "museum", 43.2, 76.9)
        let place = try decoder.decode(ReverseGeocode.self, from: Data(
            "{\"kind\":\"place\",\"place\":\(museum),\"lat\":43.2,\"lon\":76.9,\"distance_m\":3}".utf8))
        guard case .place(let summary) = place else { return XCTFail("a place") }
        XCTAssertEqual(summary.name, "Fixture Museum")
        XCTAssertNil(summary.tappedPoint, "a place of ours is not a tapped point")

        let address = try decoder.decode(ReverseGeocode.self, from: Data(addressJSON.utf8))
        XCTAssertEqual(
            address, .address(street: "улица Панфилова 98", name: nil, point: GeoPoint(lat: 43.25797, lon: 76.94506))
        )

        let buildingJSON = """
        {"kind":"address","address":null,"name":"La Tartine","lat":43.2,"lon":76.9,"distance_m":4}
        """
        let building = try decoder.decode(ReverseGeocode.self, from: Data(buildingJSON.utf8))
        XCTAssertEqual(building, .address(street: nil, name: "La Tartine", point: GeoPoint(lat: 43.2, lon: 76.9)))

        let pointJSON = "{\"kind\":\"point\",\"lat\":43.3,\"lon\":77.1}"
        let point = try decoder.decode(ReverseGeocode.self, from: Data(pointJSON.utf8))
        XCTAssertEqual(point, .point(GeoPoint(lat: 43.3, lon: 77.1)))
    }

    func testBlankAddressCountsAsNone() throws {
        let value = try JSONDecoder().decode(ReverseGeocode.self, from: Data(
            "{\"kind\":\"address\",\"address\":\"  \",\"name\":\"\",\"lat\":43.2,\"lon\":76.9}".utf8))
        let summary = try XCTUnwrap(PlaceSummary.tapped(value))
        XCTAssertEqual(summary.tappedPoint?.isBare, true)
        XCTAssertEqual(summary.name, "43.20000, 76.90000")
    }

    func testTappedSummaryTitles() throws {
        let street = try XCTUnwrap(PlaceSummary.tapped(.address(street: "Abay 1", name: nil, point: almaty)))
        XCTAssertEqual(street.name, "Abay 1")
        XCTAssertEqual(street.tappedPoint, TappedPoint(address: "Abay 1", isBare: false))

        let building = try XCTUnwrap(
            PlaceSummary.tapped(.address(street: "Abay 1", name: "La Tartine", point: almaty))
        )
        XCTAssertEqual(building.name, "La Tartine", "the building's name is the title, the street goes under it")
        XCTAssertEqual(building.tappedPoint?.address, "Abay 1")

        let bare = try XCTUnwrap(PlaceSummary.tapped(.point(almaty)))
        XCTAssertEqual(bare.name, "43.25790, 76.94500")
        XCTAssertEqual(bare.tappedPoint?.isBare, true)
        XCTAssertNotEqual(bare.id, try XCTUnwrap(PlaceSummary.tapped(.point(almaty))).id, "an id per tap")
    }

    // MARK: - The model

    func testTapOnAnAddressOpensItWithoutLoadingPlaceDetail() async throws {
        StubURLProtocol.install { reply(addressJSON, $0) }
        let model = makeModel()
        model.tapPoint(almaty)
        await wait { model.selected != nil }

        let selected = try XCTUnwrap(model.selected)
        XCTAssertEqual(selected.name, "улица Панфилова 98")
        XCTAssertNotNil(selected.tappedPoint)
        XCTAssertEqual(selected.lat, 43.25797, accuracy: 1e-9, "the building point, a sound routing target")
        XCTAssertEqual(model.detail, .idle)
        try? await Task.sleep(for: .milliseconds(100))
        XCTAssertTrue(StubURLProtocol.requests.allSatisfy { !($0.url?.path.hasPrefix("/v1/places/") ?? false) },
                      "an address has nothing to load from /v1/places/{id}")
        let query = try XCTUnwrap(geocodeRequests().first?.url?.query)
        XCTAssertTrue(query.contains("lat=43.257900") && query.contains("lon=76.945000"), query)
    }

    func testTapOnAPlaceSelectsItAndLoadsItsCard() async throws {
        let museum = UITestSupport.summary(UITestSupport.centerPlaceID, "Fixture Museum", "museum", 43.2, 76.9)
        StubURLProtocol.install { request in
            if request.url?.path == "/v1/geocode/reverse" {
                let body = "{\"kind\":\"place\",\"place\":\(museum),\"lat\":43.2,\"lon\":76.9,\"distance_m\":3}"
                return reply(body, request)
            }
            return reply(UITestSupport.detailJSON(id: UITestSupport.centerPlaceID), request)
        }
        let model = makeModel()
        model.tapPoint(almaty)
        await wait { if case .loaded = model.detail { true } else { false } }
        XCTAssertEqual(model.selected?.name, "Fixture Museum")
        XCTAssertNil(model.selected?.tappedPoint)
    }

    func testBarePointAndFailedLookupBothOpenThePoint() async throws {
        StubURLProtocol.install { reply("{\"kind\":\"point\",\"lat\":43.3,\"lon\":77.1}", $0) }
        let model = makeModel()
        model.tapPoint(GeoPoint(lat: 43.3, lon: 77.1))
        await wait { model.selected != nil }
        XCTAssertEqual(model.selected?.tappedPoint?.isBare, true)

        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        model.clearSelection()
        model.tapPoint(almaty)
        await wait { model.selected != nil }
        XCTAssertEqual(model.selected?.tappedPoint?.isBare, true, "no network: «Route» only needs the coordinates")
        XCTAssertEqual(model.selected?.lat ?? 0, almaty.lat, accuracy: 1e-9)

        let limited = "{\"error\":{\"code\":\"rate_limited\",\"message\":\"x\"}}"
        StubURLProtocol.install { reply(limited, status: 429, $0) }
        model.clearSelection()
        model.tapPoint(almaty)
        await wait { model.selected != nil }
        XCTAssertEqual(model.selected?.tappedPoint?.isBare, true, "over the limit: still the point")
    }

    func testTapOutsideTheServiceAreaOnlyClosesTheCard() async throws {
        StubURLProtocol.install { reply(addressJSON, $0) }
        let model = makeModel()
        model.tapPoint(almaty)
        await wait { model.selected != nil }
        model.tapPoint(GeoPoint(lat: 51.1, lon: 71.4)) // Astana
        XCTAssertNil(model.selected)
        try? await Task.sleep(for: .milliseconds(100))
        XCTAssertEqual(geocodeRequests().count, 1, "no request outside Almaty: the server would answer 422")
    }

    func testLateAnswerOfAnEarlierTapIsDropped() async throws {
        let calls = Counter()
        StubURLProtocol.install { request in
            let first = calls.next() == 0
            if first { Thread.sleep(forTimeInterval: 0.3) }
            let street = first ? "First 1" : "Second 2"
            let body = "{\"kind\":\"address\",\"address\":\"\(street)\",\"name\":null,\"lat\":43.25,\"lon\":76.9}"
            return reply(body, request)
        }
        let model = makeModel()
        model.tapPoint(almaty)
        try? await Task.sleep(for: .milliseconds(50))
        model.tapPoint(GeoPoint(lat: 43.26, lon: 76.95))
        await wait { model.selected != nil }
        try? await Task.sleep(for: .milliseconds(500))
        XCTAssertEqual(model.selected?.name, "Second 2")
    }

    func testClosingTheCardCancelsAPendingTap() async throws {
        StubURLProtocol.install { request in
            Thread.sleep(forTimeInterval: 0.2)
            return reply(addressJSON, request)
        }
        let model = makeModel()
        model.tapPoint(almaty)
        model.clearSelection()
        try? await Task.sleep(for: .milliseconds(500))
        XCTAssertNil(model.selected, "an answer that arrives after the card was closed does not reopen it")
    }

    // MARK: - Directions to a tapped point

    func testDirectionsGoByCoordinatesForAPointAndByIDForAPlace() throws {
        let point = GeoPoint(lat: 43.25797, lon: 76.94506)
        let toPoint = try JSONSerialization.jsonObject(
            with: JSONEncoder().encode(DirectionsRequest(from: almaty, toPoint: point))) as? [String: Any]
        XCTAssertNil(toPoint?["to_place_id"])
        let to = try XCTUnwrap(toPoint?["to"] as? [String: Double])
        XCTAssertEqual(to["lat"] ?? 0, 43.25797, accuracy: 1e-9)
        XCTAssertEqual(to["lon"] ?? 0, 76.94506, accuracy: 1e-9)

        let id = try XCTUnwrap(UUID(uuidString: UITestSupport.centerPlaceID))
        let toPlace = try JSONSerialization.jsonObject(
            with: JSONEncoder().encode(DirectionsRequest(from: almaty, toPlaceID: id))) as? [String: Any]
        XCTAssertEqual(toPlace?["to_place_id"] as? String, UITestSupport.centerPlaceID)
        XCTAssertNil(toPlace?["to"], "the server wants exactly one destination")
    }

    func testDirectionsModelSendsTheTappedPointAsTo() async throws {
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(), installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        let locator = PointLocator(.located(almaty))
        let model = DirectionsModel(api: client, locator: locator)
        StubURLProtocol.install { reply(UITestSupport.directionsJSON, $0) }
        let target = GeoPoint(lat: 43.25797, lon: 76.94506)
        let tapped = try XCTUnwrap(PlaceSummary.tapped(.address(street: "Abay 1", name: nil, point: target)))
        model.start(to: tapped, mapCenter: nil)
        await wait { model.phase == .loaded }

        let request = try XCTUnwrap(StubURLProtocol.requests.last { $0.url?.path == "/v1/directions" })
        let body = try XCTUnwrap(JSONSerialization.jsonObject(with: try XCTUnwrap(request.httpBody)) as? [String: Any])
        XCTAssertNil(body["to_place_id"])
        XCTAssertEqual((body["to"] as? [String: Double])?["lat"] ?? 0, 43.25797, accuracy: 1e-9)
    }
}

@MainActor
private final class PointLocator: LocationProviding {
    let result: LocationResult
    init(_ result: LocationResult) { self.result = result }
    func currentLocation() async -> LocationResult { result }
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
