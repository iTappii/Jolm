@testable import Jol
import XCTest

/// Ш-55: replacing a stop (alternatives list, replace request, must-have, no replacement) and the «All days» view.
@MainActor
final class TripReplaceTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let tripID = UUID(uuidString: ChatStub.tripID)!

    private func makeModel() -> TripMapModel {
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r")),
            installID: "install-1", session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return TripMapModel(api: client)
    }

    private func wait(_ timeout: TimeInterval = 3, until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    private nonisolated static let alternativesJSON = """
    {"items":[{"id":"\(TripStub.galleryID)","name":"Fixture Gallery","category":"museum","lat":43.25,"lon":76.9,\
    "price_kzt":2000,"distance_m":850.5},\
    {"id":"\(TripStub.parkID)","name":"Fixture Park","category":"park","lat":43.24,"lon":76.91,"price_kzt":null,\
    "distance_m":1400}]}
    """

    /// The trip and events as the stub serves them; `edit` answers the alternatives and the replace calls.
    private func install(edit: @escaping @Sendable (URLRequest) -> (Int, String)) {
        StubURLProtocol.install { request in
            let path = request.url?.path ?? ""
            if request.httpMethod == "GET", path == "/v1/trips/\(ChatStub.tripID)" {
                return (StubURLProtocol.response(request.url!), Data(TripStub.json(id: ChatStub.tripID).utf8))
            }
            if request.httpMethod == "GET", path == "/v1/events" {
                return (StubURLProtocol.response(request.url!), Data("{\"items\":[]}".utf8))
            }
            let (status, body) = edit(request)
            return (StubURLProtocol.response(request.url!, status: status), Data(body.utf8))
        }
    }

    private nonisolated static func body(of request: URLRequest) throws -> [String: Any] {
        let data = try XCTUnwrap(request.httpBody)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    private func openedModel() async -> TripMapModel {
        let model = makeModel()
        model.open(tripID: tripID)
        await wait { model.phase == .loaded }
        return model
    }

    // MARK: - Wire shapes

    func testDecodesAlternativesAndSkipsABrokenOne() throws {
        let json = """
        {"items":[{"id":"\(TripStub.galleryID)","name":"A","category":"museum","category_name":"Museum","lat":1,\
        "lon":2,"price_kzt":2000,"distance_m":850.5},{"name":"no id"},\
        {"id":"\(TripStub.parkID)","name":"B","lat":1,"lon":2,"price_kzt":null,"distance_m":10}]}
        """
        let list = try JSONDecoder().decode(TripAlternatives.self, from: Data(json.utf8))
        XCTAssertEqual(list.items.map(\.name), ["A", "B"])
        XCTAssertEqual(list.items[0].priceKzt, 2000)
        XCTAssertEqual(list.items[0].distanceM, 850.5)
        XCTAssertEqual(list.items[0].categoryName, "Museum")
        XCTAssertNil(list.items[1].priceKzt)
    }

    func testReplaceBodyHasLowercaseIDAndForce() throws {
        let id = try XCTUnwrap(UUID(uuidString: "33333333-3333-4333-8333-00000000ABCD"))
        let data = try JSONEncoder().encode(ItemReplacement(placeID: id, force: true))
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(object["place_id"] as? String, "33333333-3333-4333-8333-00000000abcd")
        XCTAssertEqual(object["force"] as? Bool, true)
        XCTAssertEqual(Set(object.keys), ["place_id", "force"], "exactly one of place_id/category/query")
    }

    // MARK: - Flow

    func testReplacingLoadsAlternativesSendsTheChoiceAndReloadsTheDay() async throws {
        install { request in
            let path = request.url?.path ?? ""
            if request.httpMethod == "GET", path.hasSuffix("/alternatives") { return (200, Self.alternativesJSON) }
            return (200, "{\"trip_id\":\"\(ChatStub.tripID)\",\"version\":2,\"changed_days\":[],\"dropped\":[]}")
        }
        let model = await openedModel()
        let cafe = model.days[0].items[1]
        model.beginReplace(cafe)
        XCTAssertEqual(model.replacing?.name, "Fixture Cafe")
        await wait { model.alternatives != .loading }
        guard case .loaded(let list) = model.alternatives else { return XCTFail("\(model.alternatives)") }
        XCTAssertEqual(list.count, 2)
        let get = try XCTUnwrap(StubURLProtocol.requests.last { $0.url?.path.hasSuffix("/alternatives") == true })
        XCTAssertEqual(get.url?.path, "/v1/trips/\(ChatStub.tripID)/items/\(TripStub.cafeItem)/alternatives")

        model.replace(with: list[1])
        await wait { model.editRevision == 1 }
        XCTAssertNil(model.replacing, "the sheet closes")
        XCTAssertEqual(model.alternatives, .idle)
        let post = try XCTUnwrap(StubURLProtocol.requests.last { $0.httpMethod == "POST" })
        XCTAssertEqual(post.url?.path, "/v1/trips/\(ChatStub.tripID)/items/\(TripStub.cafeItem)/replace")
        let body = try Self.body(of: post)
        XCTAssertEqual(body["place_id"] as? String, TripStub.parkID)
        XCTAssertEqual(body["force"] as? Bool, false)
        let tripReads = StubURLProtocol.requests.filter { $0.url?.path == "/v1/trips/\(ChatStub.tripID)" }
        XCTAssertGreaterThanOrEqual(tripReads.count, 2, "the plan is read again after the edit")
    }

    func testReplacingAMustHaveAsksFirstThenSendsForce() async throws {
        install { request in
            let path = request.url?.path ?? ""
            if request.httpMethod == "GET", path.hasSuffix("/alternatives") { return (200, Self.alternativesJSON) }
            if (try? Self.body(of: request)["force"] as? Bool) == true {
                return (200, "{\"trip_id\":\"\(ChatStub.tripID)\",\"version\":2,\"changed_days\":[],\"dropped\":[]}")
            }
            return (409, "{\"error\":{\"code\":\"must_have\",\"message\":\"must\"}}")
        }
        let model = await openedModel()
        model.beginReplace(model.days[0].items[0])
        await wait { model.alternatives != .loading }
        guard case .loaded(let list) = model.alternatives else { return XCTFail("\(model.alternatives)") }
        model.replace(with: list[0])
        await wait { model.pendingReplacement != nil }
        XCTAssertEqual(model.pendingReplacement?.alternative.id, list[0].id)
        XCTAssertEqual(model.editRevision, 0, "nothing changed yet")
        XCTAssertNotNil(model.replacing, "the sheet stays while the person decides")
        model.confirmReplacement()
        await wait { model.editRevision == 1 }
        let posts = StubURLProtocol.requests.filter { $0.httpMethod == "POST" }
        XCTAssertEqual(try posts.map { try Self.body(of: $0)["force"] as? Bool }, [false, true])
    }

    func testNoReplacementKeepsTheSheetOpenWithAMessage() async {
        install { request in
            if request.httpMethod == "GET", request.url?.path.hasSuffix("/alternatives") == true {
                return (200, Self.alternativesJSON)
            }
            return (409, "{\"error\":{\"code\":\"no_replacement\",\"message\":\"x\"}}")
        }
        let model = await openedModel()
        model.beginReplace(model.days[0].items[1])
        await wait { model.alternatives != .loading }
        guard case .loaded(let list) = model.alternatives else { return XCTFail("\(model.alternatives)") }
        model.replace(with: list[0])
        await wait { model.problem != nil }
        XCTAssertEqual(model.problem, .noReplacement)
        XCTAssertNotNil(model.replacing)
        XCTAssertEqual(model.editRevision, 0)
    }

    func testAStalePlanClosesTheSheetAndReloads() async {
        install { request in
            if request.httpMethod == "GET", request.url?.path.hasSuffix("/alternatives") == true {
                return (200, Self.alternativesJSON)
            }
            return (409, "{\"error\":{\"code\":\"trip_changed\",\"message\":\"x\"}}")
        }
        let model = await openedModel()
        model.beginReplace(model.days[0].items[1])
        await wait { model.alternatives != .loading }
        guard case .loaded(let list) = model.alternatives else { return XCTFail("\(model.alternatives)") }
        model.replace(with: list[0])
        await wait { model.problem != nil }
        XCTAssertEqual(model.problem, .outdated)
        await wait { model.replacing == nil }
        XCTAssertNil(model.replacing)
    }

    func testFailedAlternativesCanBeRetried() async {
        let attempts = Attempts()
        install { request in
            if request.httpMethod == "GET", request.url?.path.hasSuffix("/alternatives") == true {
                return attempts.next() == 1 ? (500, "{}") : (200, Self.alternativesJSON)
            }
            return (404, "{}")
        }
        let model = await openedModel()
        model.beginReplace(model.days[0].items[1])
        await wait { model.alternatives == .failed }
        XCTAssertEqual(model.alternatives, .failed)
        model.retryAlternatives()
        await wait { model.alternatives != .loading && model.alternatives != .failed }
        guard case .loaded(let list) = model.alternatives else { return XCTFail("\(model.alternatives)") }
        XCTAssertEqual(list.count, 2)
    }

    // MARK: - All days

    func testAllDaysDrawsEveryDayInItsColour() async {
        install { _ in (404, "{}") }
        let model = await openedModel()
        XCTAssertFalse(model.showsAllDays)
        XCTAssertEqual(model.stops.count, 2, "one day at first")
        let fits = model.fitVersion
        model.selectAllDays()
        XCTAssertTrue(model.showsAllDays)
        XCTAssertEqual(model.stops.count, 4)
        XCTAssertEqual(model.lines.count, 2)
        XCTAssertEqual(model.stops.map(\.number), [1, 2, 1, 2], "numbered within each day")
        XCTAssertEqual(
            model.stops.map(\.colorHex),
            [TripMapModel.dayColors[0], TripMapModel.dayColors[0], TripMapModel.dayColors[1],
             TripMapModel.dayColors[1]]
        )
        XCTAssertEqual(model.lines.map(\.colorHex), [TripMapModel.dayColors[0], TripMapModel.dayColors[1]])
        XCTAssertGreaterThan(model.fitVersion, fits, "the camera fits all days")
        model.selectDay(1)
        XCTAssertFalse(model.showsAllDays)
        XCTAssertEqual(model.stops.count, 2)
        XCTAssertEqual(model.stops.first?.colorHex, TripMapModel.dayColors[1])
        model.selectDay(1)
        model.selectAllDays()
        model.selectDay(1)
        XCTAssertFalse(model.showsAllDays, "tapping the day that was selected before still leaves «All days»")
    }
}

/// Counts calls from a `@Sendable` handler.
private final class Attempts: @unchecked Sendable {
    private let lock = NSLock()
    private var count = 0

    func next() -> Int {
        lock.lock(); defer { lock.unlock() }
        count += 1
        return count
    }
}
