@testable import Jol
import XCTest

@MainActor
final class PlacesTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!

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

    private func bounds(_ west: Double, _ south: Double, size: Double) -> GeoBounds {
        GeoBounds(west: west, south: south, east: west + size, north: south + size)
    }

    private func placeRequests() -> [URLRequest] {
        StubURLProtocol.requests.filter { $0.url?.path == "/v1/places" }
    }

    // MARK: - Decoding

    func testDecodesPlaceDetail() throws {
        let data = Data(UITestSupport.detailJSON(id: UITestSupport.centerPlaceID).utf8)
        let place = try JSONDecoder().decode(PlaceDetail.self, from: data)
        XCTAssertEqual(place.name, "Fixture Museum")
        XCTAssertEqual(place.prices.entryPriceKzt, 1500)
        XCTAssertNil(place.prices.avgCheckKzt)
        XCTAssertEqual(place.hours.count, 7)
        XCTAssertEqual(place.openNow, true)
        XCTAssertEqual(place.typicalVisitMin, 90)
    }

    func testDecodesCuratedRouteInOrder() throws {
        let data = Data(UITestSupport.routeJSON.utf8)
        let route = try JSONDecoder().decode(CuratedRouteDetail.self, from: data)
        XCTAssertEqual(route.stops.map(\.name), ["Fixture Museum", "Fixture Cafe"])
        XCTAssertEqual(route.items.map(\.ord), [1, 2])
    }

    // MARK: - Loading

    func testRegionChangeIsDebouncedAndStaleRequestsAreDropped() async {
        StubURLProtocol.install { json(UITestSupport.placesJSON, $0) }
        let model = makeModel()
        model.regionChanged(bounds(76.0, 43.0, size: 0.1))
        model.regionChanged(bounds(76.5, 43.5, size: 0.1))
        model.regionChanged(bounds(76.9, 43.2, size: 0.1))
        await wait { !model.pins.isEmpty }
        try? await Task.sleep(for: .milliseconds(150))
        let requests = placeRequests()
        XCTAssertEqual(requests.count, 1, "only the last camera position is requested")
        let query = requests.first?.url?.query ?? ""
        XCTAssertTrue(query.contains("bbox="))
        XCTAssertTrue(query.contains("limit=1000"))
        XCTAssertEqual(model.pins.count, 2)
    }

    func testMovingInsideLoadedAreaDoesNotRequestAgain() async {
        StubURLProtocol.install { json(UITestSupport.placesJSON, $0) }
        let model = makeModel()
        model.regionChanged(bounds(76.9, 43.2, size: 0.1))
        await wait { !model.pins.isEmpty }
        let version = model.pinsVersion
        model.regionChanged(bounds(76.92, 43.22, size: 0.08))  // inside the padded area
        try? await Task.sleep(for: .milliseconds(150))
        XCTAssertEqual(placeRequests().count, 1)
        XCTAssertEqual(model.pinsVersion, version)
    }

    func testDuplicatesAreMergedById() async {
        StubURLProtocol.install { json(UITestSupport.placesJSON, $0) }
        let model = makeModel()
        model.regionChanged(bounds(76.9, 43.2, size: 0.1))
        await wait { model.pins.count == 2 }
        model.regionChanged(bounds(77.5, 43.2, size: 0.1))  // new area, same items come back
        await wait { placeRequests().count == 2 }
        try? await Task.sleep(for: .milliseconds(100))
        XCTAssertEqual(model.pins.count, 2)
        XCTAssertEqual(model.pinsVersion, 1, "unchanged data does not touch the map")
    }

    func testPinsAreCapped() async {
        let counter = Counter()
        StubURLProtocol.install { json(page(counter.next()), $0) }
        let model = makeModel()
        for step in 0..<5 {
            model.regionChanged(bounds(70.0 + Double(step) * 3, 43.0, size: 0.1))
            await wait { placeRequests().count == step + 1 }
            try? await Task.sleep(for: .milliseconds(60))
        }
        XCTAssertLessThanOrEqual(model.pins.count, PlacesModel.cap)
        XCTAssertGreaterThan(model.pins.count, 0)
    }

    func testFailedLoadKeepsExistingPins() async {
        let fail = Counter()
        StubURLProtocol.install { request in
            if fail.next() > 0 { throw URLError(.notConnectedToInternet) }
            return json(UITestSupport.placesJSON, request)
        }
        let model = makeModel()
        model.regionChanged(bounds(76.9, 43.2, size: 0.1))
        await wait { model.pins.count == 2 }
        model.regionChanged(bounds(77.5, 43.2, size: 0.1))
        await wait { model.pinsFailed }
        XCTAssertTrue(model.pinsFailed)
        XCTAssertEqual(model.pins.count, 2)
    }

    // MARK: - Selection and routes

    func testSelectLoadsDetailAndLatestSelectionWins() async throws {
        StubURLProtocol.install { request in
            let path = request.url!.path
            if path == "/v1/places" { return json(UITestSupport.placesJSON, request) }
            return json(UITestSupport.detailJSON(id: String(path.dropFirst("/v1/places/".count))), request)
        }
        let model = makeModel()
        model.regionChanged(bounds(76.9, 43.2, size: 0.1))
        await wait { model.pins.count == 2 }
        let first = try XCTUnwrap(UUID(uuidString: UITestSupport.centerPlaceID))
        let second = try XCTUnwrap(UUID(uuidString: UITestSupport.secondPlaceID))
        model.select(first)
        model.select(second)
        await wait { if case .loaded = model.detail { true } else { false } }
        guard case .loaded(let detail) = model.detail else { return XCTFail("detail not loaded") }
        XCTAssertEqual(detail.id, second)
        XCTAssertEqual(model.selected?.id, second)
        model.clearSelection()
        XCTAssertNil(model.selected)
        XCTAssertEqual(model.detail, .idle)
    }

    func testOpenRouteShowsStopsAndPausesPinLoading() async {
        StubURLProtocol.install { request in
            let list = request.url!.path == "/v1/curated-routes"
            return json(list ? UITestSupport.routesJSON : UITestSupport.routeJSON, request)
        }
        let model = makeModel()
        await model.loadRoutes()
        guard case .loaded(let routes) = model.routes, let route = routes.first else { return XCTFail("no routes") }
        XCTAssertEqual(route.placesCount, 2)
        model.openRoute(id: route.id)
        await wait { model.activeRoute != nil }
        XCTAssertEqual(model.routeStops.count, 2)
        model.regionChanged(bounds(76.9, 43.2, size: 0.1))
        try? await Task.sleep(for: .milliseconds(120))
        XCTAssertTrue(placeRequests().isEmpty, "pins are not loaded while a route is shown")
        model.closeRoute()
        XCTAssertNil(model.activeRoute)
        await wait { !placeRequests().isEmpty }
        XCTAssertFalse(placeRequests().isEmpty, "pins reload after the route is closed")
    }

    // MARK: - Helpers

    func testDarkStyleVariantKeepsHost() {
        let light = URL(string: "http://localhost:8080/native/jol-light.json")!
        XCTAssertEqual(AppConfig.darkVariant(of: light).absoluteString, "http://localhost:8080/native/jol-dark.json")
        let other = URL(string: "https://example.com/style.json")!
        XCTAssertEqual(AppConfig.darkVariant(of: other), other)
        let file = URL(fileURLWithPath: "/tmp/placeholder-style.json")
        XCTAssertEqual(AppConfig.darkVariant(of: file), file)
    }

    func testBoundsPaddingIsClampedToServerLimit() {
        let padded = bounds(76.0, 43.0, size: 3.0).padded(by: 0.25, maxSpan: 2)
        XCTAssertEqual(padded.width, 2, accuracy: 1e-9)
        XCTAssertEqual(padded.height, 2, accuracy: 1e-9)
        let small = bounds(76.0, 43.0, size: 0.1).padded(by: 0.25, maxSpan: 2)
        XCTAssertEqual(small.width, 0.15, accuracy: 1e-9)
        XCTAssertEqual(bounds(1, 2, size: 1).queryValue, "1.00000,2.00000,2.00000,3.00000")
    }

    func testNavigatorURLs() {
        let coordinate = AlmatyCamera.center
        let apple = Navigator.url(for: .appleMaps, name: "Cafe & Bar", coordinate: coordinate)?.absoluteString
        XCTAssertTrue(apple?.hasPrefix("https://maps.apple.com/?daddr=43.238000,76.945000") == true, apple ?? "")
        XCTAssertTrue(apple?.contains("Cafe") == true)
        let gis = Navigator.url(for: .twoGIS, name: "x", coordinate: coordinate)?.absoluteString
        XCTAssertEqual(gis, "dgis://2gis.ru/routeSearch/rsType/car/to/76.945000,43.238000")
    }

    func testCategoryStyleFallbacks() {
        XCTAssertEqual(PlaceCategoryStyle.imageName(for: "museum"), "pin-museum")
        XCTAssertEqual(PlaceCategoryStyle.imageName(for: "cafe_korean"), "pin-cafe")
        XCTAssertEqual(PlaceCategoryStyle.imageName(for: "unknown"), "pin-default")
        XCTAssertEqual(PlaceCategoryStyle.imageName(for: nil), "pin-default")
        for entry in PlaceCategoryStyle.allImages {
            XCTAssertNotNil(UIImage(systemName: entry.style.symbol), "missing SF Symbol \(entry.style.symbol)")
        }
    }

    func testWeekdayIsMondayBasedInAlmaty() {
        // 2026-11-21 is a Saturday.
        let date = DateComponents(calendar: .init(identifier: .gregorian), timeZone: PlaceFormatting.almaty,
                                  year: 2026, month: 11, day: 21, hour: 12).date!
        XCTAssertEqual(PlaceFormatting.weekday(of: date), 5)
    }
}

private func page(_ index: Int) -> String {
    let items = (0..<PlacesService.pageLimit).map { offset in
        let id = String(format: "%08X-0000-4000-8000-%012X", index, offset)
        return "{\"id\":\"\(id)\",\"name\":\"P\",\"category\":\"coffee\",\"kind\":\"venue\","
            + "\"lat\":43.2,\"lon\":76.9,\"is_public\":true,\"is_partner\":false,\"popularity\":\(offset)}"
    }
    return "{\"items\":[\(items.joined(separator: ","))]}"
}

private func json(_ text: String, _ request: URLRequest) -> (HTTPURLResponse, Data) {
    (StubURLProtocol.response(request.url!), Data(text.utf8))
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
