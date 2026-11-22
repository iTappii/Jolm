@testable import Jol
import XCTest

@MainActor
final class RegionTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private var defaults: UserDefaults!

    private nonisolated static let twoRegions = """
    {"regions":[
      {"id":"almaty","name":{"ru":"Алматы","en":"Almaty"},"timezone":"Asia/Almaty","currency":"KZT",
       "languages":["ru","en"],"centre":{"lat":43.2389,"lon":76.8897},"camera":{"zoom":11.0},
       "bbox":[76.7,42.95,77.3,43.45],"is_default":false},
      {"id":"berlin","name":{"ru":"Берлин","en":"Berlin"},"timezone":"Europe/Berlin","currency":"EUR",
       "languages":["en"],"centre":{"lat":52.52,"lon":13.405},"camera":{"zoom":10.5},
       "bbox":[13.0,52.3,13.8,52.7],"is_default":true}]}
    """

    override func setUp() {
        super.setUp()
        defaults = UserDefaults(suiteName: "RegionTests-\(UUID().uuidString)")
        Region.current = .builtIn
        Region.known = [.builtIn]
    }

    override func tearDown() {
        Region.current = .builtIn
        Region.known = [.builtIn]
        super.tearDown()
    }

    private func makeModel() -> RegionModel {
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(), installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return RegionModel(api: client, defaults: defaults)
    }

    private func berlin() throws -> Region {
        let answer = try JSONDecoder().decode(RegionsResponse.self, from: Data(Self.twoRegions.utf8))
        return try XCTUnwrap(answer.preferred)
    }

    func testDecodesContract() throws {
        let answer = try JSONDecoder().decode(RegionsResponse.self, from: Data(RegionTests.twoRegions.utf8))
        XCTAssertEqual(answer.regions.count, 2)
        let berlin = try XCTUnwrap(answer.preferred)
        XCTAssertEqual(berlin.id, "berlin")
        XCTAssertTrue(berlin.isDefault)
        XCTAssertEqual(berlin.name.ru, "Берлин")
        XCTAssertEqual(berlin.timezone, "Europe/Berlin")
        XCTAssertEqual(berlin.currency, "EUR")
        XCTAssertEqual(berlin.centre.lon, 13.405, accuracy: 1e-9)
        XCTAssertEqual(berlin.zoom, 10.5)
        XCTAssertEqual(berlin.bbox, [13.0, 52.3, 13.8, 52.7])
    }

    func testLoadSwitchesCurrentRegionAndCachesIt() async {
        StubURLProtocol.install { request in
            XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
            XCTAssertEqual(request.url?.path, "/v1/regions")
            return (StubURLProtocol.response(request.url!), Data(RegionTests.twoRegions.utf8))
        }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.current.id, "berlin")
        XCTAssertEqual(Region.current.id, "berlin")
        // A new launch without network starts from the cached answer.
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        Region.current = .builtIn
        let relaunched = makeModel()
        XCTAssertEqual(relaunched.current.id, "berlin")
        XCTAssertEqual(Region.current.id, "berlin")
    }

    func testNetworkFailureFallsBackToBuiltInRegion() async {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.current, .builtIn)
        XCTAssertEqual(Region.current, .builtIn)
        XCTAssertEqual(Region.current.id, "almaty")
    }

    func testMissingEndpointOrBadBodyKeepsBuiltInRegion() async {
        StubURLProtocol.install { request in
            let body = "{\"error\":{\"code\":\"not_found\",\"message\":\"x\"}}"
            return (StubURLProtocol.response(request.url!, status: 404), Data(body.utf8))
        }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.current, .builtIn)
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), Data("{\"regions\":[]}".utf8)) }
        await model.load()
        XCTAssertEqual(model.current, .builtIn)
    }

    func testPriceFormattingFollowsRegionCurrency() async throws {
        let json = """
        {"mode":"bus","duration_s":600,"distance_m":3000,"cost_kzt_min":120,"cost_kzt_max":120,"geometry":"",
         "approximate":false,"recommended":false}
        """
        let option = try JSONDecoder().decode(DirectionOption.self, from: Data(json.utf8))
        XCTAssertEqual(DirectionsFormatting.price(option, language: "en"), "≈ 120\u{00A0}₸")
        XCTAssertEqual(PlaceFormatting.tenge(1500), "≈ 1\u{00A0}500\u{00A0}₸")
        Region.current = try berlin()
        XCTAssertEqual(DirectionsFormatting.price(option, language: "en"), "≈ 120\u{00A0}€")
        XCTAssertEqual(PlaceFormatting.tenge(1500), "≈ 1\u{00A0}500\u{00A0}€")
        XCTAssertEqual(TripFormatting.kzt(120_000, locale: Locale(identifier: "en_US")), "120,000\u{00A0}€")
        XCTAssertEqual(BriefFormatting.budget(200_000, locale: Locale(identifier: "ru_RU")).last, "€")
    }

    func testTimeFormattingFollowsRegionTimeZone() throws {
        // 2027-01-15 08:00 UTC: 13:00 in Almaty, 09:00 in Berlin.
        let date = Date(timeIntervalSince1970: 1_800_000_000)
        XCTAssertEqual(EventsModel.dateString(date), "2027-01-15")
        XCTAssertEqual(PlaceFormatting.weekday(of: date), 4)  // Friday
        let late = Date(timeIntervalSince1970: 1_800_000_000 + 14 * 3600)  // 22:00 UTC: 03:00 next day in Almaty
        XCTAssertEqual(EventsModel.dateString(late), "2027-01-16")
        Region.current = try berlin()
        XCTAssertEqual(EventsModel.dateString(late), "2027-01-15")  // 23:00 in Berlin
    }

    func testBuiltInRegionKeepsOldValuesAndBox() {
        let region = Region.builtIn
        XCTAssertEqual(region.center.latitude, 43.2380, accuracy: 1e-9)
        XCTAssertEqual(region.center.longitude, 76.9450, accuracy: 1e-9)
        XCTAssertEqual(region.zoom, 11)
        XCTAssertTrue(region.contains(lat: 43.25, lon: 76.9))
        XCTAssertFalse(region.contains(lat: 51.1, lon: 71.4))
    }

    /// Ш-59: "how to get there" works in every region the server knows, not only the one trips are planned in.
    func testServiceAreaCoversEveryKnownRegion() async {
        let turkestan = GeoPoint(lat: 43.297, lon: 68.272)
        let moscow = GeoPoint(lat: 55.75, lon: 37.62)
        XCTAssertFalse(turkestan.isInServiceArea, "only the built-in city before the list is loaded")
        let country = """
        {"regions":[
          {"id":"almaty","name":{"ru":"Алматы","en":"Almaty"},"timezone":"Asia/Almaty","currency":"KZT",
           "languages":["ru","en"],"centre":{"lat":43.2389,"lon":76.9455},"camera":{"zoom":11.0},
           "bbox":[76.7,42.95,77.3,43.45],"is_default":true},
          {"id":"kazakhstan","name":{"ru":"Казахстан","en":"Kazakhstan"},"timezone":"Asia/Almaty",
           "currency":"KZT","languages":["ru","en"],"centre":{"lat":48.0,"lon":66.9},"camera":{"zoom":4.5},
           "bbox":[46.4,40.5,87.4,55.5],"is_default":false}]}
        """
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), Data(country.utf8)) }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(Region.current.id, "almaty", "planning stays in the default region")
        XCTAssertTrue(turkestan.isInServiceArea)
        XCTAssertFalse(moscow.isInServiceArea)
    }
}
