@testable import Jol
import XCTest

/// Ш-37: the trip wire shapes and the edits of the full route map, against the recorded stub JSON.
@MainActor
final class TripMapTests: XCTestCase {
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

    private func decodeTrip() throws -> TripOverview {
        try JSONDecoder().decode(TripOverview.self, from: Data(TripStub.json(id: ChatStub.tripID).utf8))
    }

    /// Answers like the server for one scripted scenario; every request is recorded by `StubURLProtocol`.
    private func install(mode: @escaping @Sendable (URLRequest) -> (Int, String)) {
        StubURLProtocol.install { request in
            let path = request.url?.path ?? ""
            if request.httpMethod == "GET", path == "/v1/trips/\(ChatStub.tripID)" {
                return (StubURLProtocol.response(request.url!), Data(TripStub.json(id: ChatStub.tripID).utf8))
            }
            if request.httpMethod == "GET", path == "/v1/events" {
                return (StubURLProtocol.response(request.url!), Data("{\"items\":[]}".utf8))
            }
            let (status, body) = mode(request)
            return (StubURLProtocol.response(request.url!, status: status), Data(body.utf8))
        }
    }

    private nonisolated static func body(of request: URLRequest) throws -> [String: Any] {
        let data = try XCTUnwrap(request.httpBody)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    // MARK: - Decoding

    func testDecodesDaysLegsOptionsAndBudgetVariants() throws {
        let trip = try decodeTrip()
        XCTAssertEqual(trip.days.count, 3)
        XCTAssertEqual(trip.days[0].items.map(\.place.name), ["Fixture Museum", "Fixture Cafe"])
        XCTAssertEqual(trip.days[0].items[0].mustHave, true)
        XCTAssertEqual(trip.days[0].items[0].startTime, "09:30")
        XCTAssertTrue(trip.days[2].items.isEmpty, "an empty day stays")
        let leg = try XCTUnwrap(trip.days[0].legs.first)
        XCTAssertEqual(leg.chosenMode, .bus)
        XCTAssertEqual(leg.modeChoices.map(\.mode).sorted { $0.rawValue < $1.rawValue }, [.bus, .taxi, .walk])
        XCTAssertEqual(leg.activeOption?.mode, .bus)
        XCTAssertGreaterThan(leg.activeOption?.line.count ?? 0, 2, "polyline6 decodes to a line")
        let budget = try XCTUnwrap(trip.budgetDetail)
        XCTAssertTrue(budget.isOver)
        XCTAssertEqual(budget.shortfallKzt, 20_000)
        XCTAssertEqual(budget.dropPlaces?.feasible, true)
        XCTAssertEqual(budget.cheaper?.feasible, false, "an infeasible variant is kept as the server sent it")
        XCTAssertEqual(budget.cheaper?.shortfallKzt, 10_000)
        XCTAssertTrue(trip.needsBudgetChoice)
        XCTAssertEqual(trip.events.count, 2)
        XCTAssertEqual(trip.events.first?.visibleAdLabel, "Ad")
        XCTAssertNil(trip.events.last?.visibleAdLabel)
    }

    func testAnUnknownTransportModeDoesNotHideThePlan() throws {
        let json = """
        {"id":"\(ChatStub.tripID)","start_date":"2026-12-05","end_date":"2026-12-05","days":[{"date":"2026-12-05",\
        "items":[],"legs":[{"id":"\(UUID().uuidString)","to_item_id":"\(UUID().uuidString)","options":[\
        {"mode":"hoverboard","duration_s":1,"distance_m":1,"cost_kzt_min":0,"cost_kzt_max":0,"geometry":""},\
        {"mode":"walk","duration_s":60,"distance_m":80,"cost_kzt_min":0,"cost_kzt_max":0,"geometry":""}]}]}]}
        """
        let trip = try JSONDecoder().decode(TripOverview.self, from: Data(json.utf8))
        XCTAssertEqual(trip.days[0].legs[0].options.map(\.mode), [.walk])
    }

    func testLegWithoutGeometryIsDrawnAsAStraightApproximateLine() async {
        install { _ in (404, "{}") }
        let model = makeModel()
        model.open(tripID: tripID)
        await wait { model.phase == .loaded }
        XCTAssertEqual(model.stops.count, 2)
        XCTAssertEqual(model.lines.count, 1)
        XCTAssertFalse(model.lines[0].approximate)
        model.selectDay(1)
        XCTAssertEqual(model.stops.first?.number, 1)
    }

    // MARK: - Edits

    func testChoosingAModeSendsItAndKeepsTheLateWarning() async throws {
        install { _ in (200, "") }
        let model = makeModel()
        model.open(tripID: tripID)
        await wait { model.phase == .loaded }
        // The stub answers the real POST with its own state; here the handler above is only for GETs.
        StubURLProtocol.install { request in
            let path = request.url?.path ?? ""
            if request.httpMethod == "POST" {
                let leg = TripStub.legOne
                let json = """
                {"trip_id":"\(ChatStub.tripID)","version":2,"leg":{"id":"\(leg)","to_item_id":"\(TripStub.cafeItem)",\
                "from_item_id":"\(TripStub.museumItem)","chosen_mode":"walk","options":[]},"late_by_s":900,\
                "changed_days":["2026-12-05"],"budget":{"status":"over","total_kzt":121000,"remaining_kzt":-21000,\
                "shortfall_kzt":21000}}
                """
                return (StubURLProtocol.response(request.url!), Data(json.utf8))
            }
            let body = path == "/v1/events" ? "{\"items\":[]}" : TripStub.json(id: ChatStub.tripID)
            return (StubURLProtocol.response(request.url!), Data(body.utf8))
        }
        let leg = try XCTUnwrap(model.days[0].legs.first)
        model.chooseMode(leg: leg, mode: .walk)
        await wait { model.lateBy[leg.id] != nil }
        XCTAssertEqual(model.lateBy[leg.id], 900)
        let post = try XCTUnwrap(StubURLProtocol.requests.last { $0.httpMethod == "POST" })
        XCTAssertEqual(post.url?.path, "/v1/trips/\(ChatStub.tripID)/legs/\(TripStub.legOne)/mode")
        XCTAssertEqual(try Self.body(of: post)["mode"] as? String, "walk")
        XCTAssertEqual(model.editRevision, 1)
    }

    func testRemovingAMustHaveNeedsAConfirmationThenSendsForce() async throws {
        install { request in
            let force = (try? Self.body(of: request)["force"] as? Bool) ?? false
            if force {
                return (200, "{\"trip_id\":\"\(ChatStub.tripID)\",\"version\":2,\"changed_days\":[],\"dropped\":[]}")
            }
            return (409, "{\"error\":{\"code\":\"must_have\",\"message\":\"must\"}}")
        }
        let model = makeModel()
        model.open(tripID: tripID)
        await wait { model.phase == .loaded }
        let item = try XCTUnwrap(model.days[0].items.first)
        model.remove(item)
        await wait { model.pendingRemoval != nil }
        XCTAssertEqual(model.pendingRemoval?.name, "Fixture Museum")
        XCTAssertEqual(model.editRevision, 0, "nothing changed yet")
        model.confirmRemoval()
        await wait { model.editRevision == 1 }
        XCTAssertNil(model.pendingRemoval)
        // Only this test's removals: a late request of an earlier test can land in the shared stub's record.
        let removePath = "/items/\(item.id.uuidString.lowercased())/remove"
        let posts = StubURLProtocol.requests.filter {
            $0.httpMethod == "POST" && ($0.url?.path ?? "").lowercased().hasSuffix(removePath)
        }
        XCTAssertEqual(try posts.map { try Self.body(of: $0)["force"] as? Bool }, [false, true])
    }

    func testBudgetChoiceIsSentAndStaleAnswersReload() async throws {
        install { _ in (409, "{\"error\":{\"code\":\"budget_choice_unavailable\",\"message\":\"x\"}}") }
        let model = makeModel()
        model.open(tripID: tripID)
        await wait { model.phase == .loaded }
        model.choose(budget: "drop_places")
        await wait { model.problem != nil }
        XCTAssertEqual(model.problem, .outdated)
        let post = try XCTUnwrap(StubURLProtocol.requests.last { $0.httpMethod == "POST" })
        XCTAssertEqual(try Self.body(of: post)["choice"] as? String, "drop_places")
        XCTAssertEqual(model.editRevision, 0)
    }

    func testProblemMapping() {
        XCTAssertEqual(TripMapModel.problem(for: APIError.network(URLError(.notConnectedToInternet))), .network)
        let notFound = APIError.server(status: 404, code: "not_found", message: "")
        XCTAssertEqual(TripMapModel.problem(for: notFound), .outdated)
        let broken = APIError.server(status: 500, code: "x", message: "Oops")
        XCTAssertEqual(TripMapModel.problem(for: broken), .server("Oops"))
    }
}
