@testable import Jol
import XCTest

@MainActor
final class FavoritesTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let museum = PlaceSummary(
        id: UUID(uuidString: UITestSupport.centerPlaceID)!, name: "Fixture Museum", category: "museum", kind: "venue",
        lat: 43.238, lon: 76.945, isPublic: true, isPartner: false, popularity: 50
    )

    private func makeModel() -> FavoritesModel {
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r")),
            installID: "i", session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return FavoritesModel(api: client)
    }

    private func calls(_ method: String) -> [URLRequest] {
        StubURLProtocol.requests.filter {
            $0.httpMethod == method && ($0.url?.path.hasPrefix("/v1/me/favorites") ?? false)
        }
    }

    func testLoadsListAndMarksIDs() async {
        StubURLProtocol.install { request in
            let json = "{\"items\":[{\"id\":\"\(UITestSupport.centerPlaceID)\",\"name\":\"Fixture Museum\","
                + "\"category\":\"museum\",\"kind\":\"venue\",\"lat\":43.2,\"lon\":76.9,\"is_public\":true,"
                + "\"is_partner\":false,\"popularity\":5,\"address\":\"x\",\"created_at\":\"2026-11-21T00:00:00Z\"}]}"
            return (StubURLProtocol.response(request.url!), Data(json.utf8))
        }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.state, .loaded)
        XCTAssertEqual(model.items.map(\.name), ["Fixture Museum"])
        XCTAssertTrue(model.isFavorite(museum.id))
    }

    func testAddIsOptimisticSendsPutAndRemoveSendsDelete() async throws {
        StubURLProtocol.install { ($0.url.map { StubURLProtocol.response($0, status: 204) }!, Data()) }
        let model = makeModel()
        await model.toggle(museum)
        XCTAssertTrue(model.isFavorite(museum.id))
        XCTAssertEqual(model.items.first?.id, museum.id)
        let put = try XCTUnwrap(calls("PUT").first)
        XCTAssertEqual(put.url?.path, "/v1/me/favorites/\(UITestSupport.centerPlaceID)")
        XCTAssertEqual(put.value(forHTTPHeaderField: "Authorization"), "Bearer a")

        await model.toggle(museum)
        XCTAssertFalse(model.isFavorite(museum.id))
        XCTAssertTrue(model.items.isEmpty)
        XCTAssertEqual(calls("DELETE").count, 1)
    }

    func testLimitRollsBackAndReports() async {
        StubURLProtocol.install { request in
            let body = Data("{\"error\":{\"code\":\"favorites_limit\",\"message\":\"m\"}}".utf8)
            return (StubURLProtocol.response(request.url!, status: 409), body)
        }
        let model = makeModel()
        await model.add(museum)
        XCTAssertFalse(model.isFavorite(museum.id))
        XCTAssertEqual(model.problem, .limit)
        model.dismissProblem()
        XCTAssertNil(model.problem)
    }

    func testFailedRemoveRollsBack() async {
        StubURLProtocol.install { ($0.url.map { StubURLProtocol.response($0, status: 204) }!, Data()) }
        let model = makeModel()
        await model.add(museum)
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        await model.remove(museum)
        XCTAssertTrue(model.isFavorite(museum.id), "the heart goes back")
        XCTAssertEqual(model.problem, .failed)
    }

    func testUnauthorizedListClearsState() async {
        StubURLProtocol.install { request in
            let body = Data("{\"error\":{\"code\":\"unauthorized\",\"message\":\"m\"}}".utf8)
            return (StubURLProtocol.response(request.url!, status: 401), body)
        }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.state, .idle)
        XCTAssertTrue(model.items.isEmpty)
    }
}
