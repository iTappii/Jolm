@testable import Jol
import XCTest

/// Ш-46: balance and history of the bonus account (SSOT §10.3).
@MainActor
final class BonusTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let session = SessionTokens(accessToken: "access-1", refreshToken: "refresh-1")

    private func makeModel(signedIn: Bool = true) -> BonusModel {
        let store = MemoryTokenStore(signedIn ? session : nil)
        let client = APIClient(
            baseURL: .success(base), tokens: store, installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return BonusModel(api: client, auth: AuthState(tokens: store))
    }

    private nonisolated static func entry(_ id: Int, _ amount: Int, _ type: String) -> String {
        "{\"id\":\"c0000000-0000-4000-8000-00000000000\(id)\",\"amount\":\(amount),\"kind\":\"accrual\","
            + "\"submission_id\":null,\"submission_type\":\"\(type)\","
            + "\"created_at\":\"2026-11-20T12:00:00.123456+05:00\"}"
    }

    private nonisolated static func page(balance: Int, items: [String], cursor: String?) -> Data {
        let next = cursor.map { "\"\($0)\"" } ?? "null"
        return Data("{\"balance\":\(balance),\"tenge_per_bonus\":1,\"next_cursor\":\(next),"
            .appending("\"items\":[\(items.joined(separator: ","))]}").utf8)
    }

    func testDecodesTheServerPage() throws {
        let page = try JSONDecoder().decode(BonusPage.self, from: Data(UITestExtraStub.bonusesJSON.utf8))
        XCTAssertEqual(page.balance, 240)
        XCTAssertEqual(page.tengePerBonus, 1)
        XCTAssertEqual(page.items.map(\.amount), [188, 52])
        XCTAssertEqual(page.items.map(\.reasonKey), ["Menu", "Review"])
        XCTAssertNil(page.nextCursor)
        XCTAssertNotNil(page.items[0].date)
    }

    func testAnUnknownSubmissionTypeStillShows() throws {
        let json = "{\"balance\":5,\"items\":[\(Self.entry(1, 5, "hologram"))]}"
        let page = try JSONDecoder().decode(BonusPage.self, from: Data(json.utf8))
        XCTAssertEqual(page.items[0].reasonKey, "Bonus")
        XCTAssertEqual(page.tengePerBonus, 1, "the rate defaults to 1 bonus = 1 tenge")
        XCTAssertNotNil(page.items[0].date, "fractional seconds parse")
    }

    func testLoadsBalanceAndHistoryWithTheToken() async throws {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!), Data(UITestExtraStub.bonusesJSON.utf8))
        }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.phase, .loaded)
        XCTAssertEqual(model.balance, 240)
        XCTAssertEqual(model.balanceKzt, 240)
        XCTAssertEqual(model.items.count, 2)
        let request = try XCTUnwrap(StubURLProtocol.requests.first)
        XCTAssertEqual(request.url?.path, "/v1/me/bonuses")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer access-1")
        XCTAssertEqual(URLComponents(url: try XCTUnwrap(request.url), resolvingAgainstBaseURL: false)?
            .queryItems?.first { $0.name == "limit" }?.value, "20")
    }

    func testAGuestMakesNoRequest() async {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), Data()) }
        let model = makeModel(signedIn: false)
        await model.load()
        XCTAssertEqual(model.phase, .idle)
        XCTAssertNil(model.balance)
        XCTAssertTrue(StubURLProtocol.requests.isEmpty)
    }

    func testNextPageUsesTheCursorAndSkipsRepeats() async throws {
        StubURLProtocol.install { request in
            let query = URLComponents(url: request.url!, resolvingAgainstBaseURL: false)?.queryItems ?? []
            if query.first(where: { $0.name == "cursor" })?.value == "next-1" {
                return (StubURLProtocol.response(request.url!),
                        Self.page(balance: 30, items: [Self.entry(2, 10, "photo"), Self.entry(3, 5, "price")],
                                  cursor: nil))
            }
            return (StubURLProtocol.response(request.url!),
                    Self.page(balance: 30, items: [Self.entry(1, 15, "review"), Self.entry(2, 10, "photo")],
                              cursor: "next-1"))
        }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.nextCursor, "next-1")
        await model.loadMore()
        XCTAssertEqual(model.items.map(\.amount), [15, 10, 5], "an entry the first page had is not repeated")
        XCTAssertNil(model.nextCursor)
        await model.loadMore()
        XCTAssertEqual(StubURLProtocol.requests.count, 2, "no cursor, no request")
    }

    func testFailuresKeepTheScreenAndAreRetryable() async throws {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.phase, .failed)
        XCTAssertNil(model.balance)

        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!),
             Self.page(balance: 9, items: [Self.entry(1, 9, "menu")], cursor: "c"))
        }
        await model.load()
        XCTAssertEqual(model.balance, 9)

        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        await model.loadMore()
        XCTAssertTrue(model.moreFailed)
        await model.load()
        XCTAssertEqual(model.balance, 9, "a failed refresh keeps the balance on screen")
        XCTAssertEqual(model.phase, .loaded)
    }
}
