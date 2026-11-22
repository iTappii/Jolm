@testable import Jol
import XCTest

/// Ш-49 / Ш-55: «My bookings» — the list, a page, cancelling, the 409 `not_cancellable` answer, date text.
@MainActor
final class BookingsListTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!

    private func makeModel(signedIn: Bool = true) -> MyBookingsModel {
        let store = MemoryTokenStore(signedIn ? SessionTokens(accessToken: "a", refreshToken: "r") : nil)
        let client = APIClient(
            baseURL: .success(base), tokens: store, installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return MyBookingsModel(api: client, auth: AuthState(tokens: store))
    }

    private func wait(_ timeout: TimeInterval = 3, until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    private nonisolated static func booking(
        _ id: String, status: String = "confirmed", kind: String = "table", start: String = "2026-12-06T19:00:00+05:00"
    ) -> String {
        """
        {"id":"\(id)","place":{"id":"\(UITestSupport.secondPlaceID)","name":"Fixture Cafe"},"kind":"\(kind)",\
        "status":"\(status)","party_size":2,"starts_at":"\(start)","ends_at":null,"event_id":null,"note":null,\
        "created_at":"2026-11-20T10:00:00+05:00","updated_at":"2026-11-20T10:00:00+05:00"}
        """
    }

    private nonisolated static let first = UITestPlaceActions.tableBookingID
    private nonisolated static let second = UITestPlaceActions.ticketBookingID

    // MARK: - Decoding

    func testDecodesAPageAndAnUnknownFutureStatus() throws {
        let items = [Self.booking(Self.first), Self.booking(Self.second, status: "waitlisted")]
        let json = "{\"items\":[\(items.joined(separator: ","))],\"next_cursor\":\"abc\"}"
        let page = try JSONDecoder().decode(BookingPage.self, from: Data(json.utf8))
        XCTAssertEqual(page.items.count, 2)
        XCTAssertEqual(page.nextCursor, "abc")
        XCTAssertEqual(page.items[0].place?.name, "Fixture Cafe")
        XCTAssertEqual(page.items[0].partySize, 2)
        XCTAssertTrue(page.items[0].canCancel)
        XCTAssertFalse(page.items[1].canCancel, "a status the app does not know offers no cancel button")
        XCTAssertEqual(page.items[0].createdAt, "2026-11-20T10:00:00+05:00")
    }

    func testOnlyPendingAndConfirmedCanBeCancelled() throws {
        for (status, expected) in [("pending", true), ("confirmed", true), ("declined", false), ("cancelled", false),
                                   ("failed", false)] {
            let one = try JSONDecoder().decode(Booking.self, from: Data(Self.booking(Self.first, status: status).utf8))
            XCTAssertEqual(one.canCancel, expected, status)
        }
    }

    // MARK: - List and cancel

    func testLoadsTheListAndTheNextPage() async throws {
        StubURLProtocol.install { request in
            let cursor = URLComponents(url: request.url!, resolvingAgainstBaseURL: false)?.queryItems?
                .first { $0.name == "cursor" }?.value
            let body = cursor == nil
                ? "{\"items\":[\(Self.booking(Self.first))],\"next_cursor\":\"c1\"}"
                : "{\"items\":[\(Self.booking(Self.second))],\"next_cursor\":null}"
            return (StubURLProtocol.response(request.url!), Data(body.utf8))
        }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.phase, .loaded)
        XCTAssertEqual(model.items.count, 1)
        await model.loadMore()
        XCTAssertEqual(model.items.count, 2)
        XCTAssertNil(model.nextCursor)
        let get = try XCTUnwrap(StubURLProtocol.requests.first)
        XCTAssertEqual(get.url?.path, "/v1/bookings")
        XCTAssertEqual(StubURLProtocol.requests.last?.url?.query?.contains("cursor=c1"), true)
    }

    func testAFailedFirstLoadShowsTheErrorState() async {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!, status: 500), Data("{}".utf8)) }
        let model = makeModel()
        await model.load()
        XCTAssertEqual(model.phase, .failed)
    }

    func testAGuestLoadsNothing() async {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), Data("{}".utf8)) }
        let model = makeModel(signedIn: false)
        await model.load()
        XCTAssertEqual(model.phase, .idle)
        XCTAssertTrue(StubURLProtocol.requests.isEmpty)
    }

    func testCancelPostsToTheBookingAndShowsItCancelled() async throws {
        StubURLProtocol.install { request in
            let path = request.url?.path ?? ""
            if request.httpMethod == "POST" {
                let cancelled = Self.booking(Self.first, status: "cancelled")
                return (StubURLProtocol.response(request.url!), Data(cancelled.utf8))
            }
            XCTAssertEqual(path, "/v1/bookings")
            return (StubURLProtocol.response(request.url!),
                    Data("{\"items\":[\(Self.booking(Self.first))],\"next_cursor\":null}".utf8))
        }
        let model = makeModel()
        await model.load()
        let id = try XCTUnwrap(UUID(uuidString: Self.first))
        let done = await model.cancel(id)
        XCTAssertTrue(done)
        XCTAssertEqual(model.booking(id: id)?.status, "cancelled")
        XCTAssertNil(model.cancelProblem)
        XCTAssertNil(model.cancellingID)
        let post = try XCTUnwrap(StubURLProtocol.requests.last)
        XCTAssertEqual(post.httpMethod, "POST")
        XCTAssertEqual(post.url?.path, "/v1/bookings/\(Self.first)/cancel")
    }

    func testNotCancellableIsShownAndTheBookingIsReadAgain() async throws {
        StubURLProtocol.install { request in
            let url = request.url!
            let path = url.path
            if request.httpMethod == "POST" {
                return (StubURLProtocol.response(url, status: 409),
                        Data("{\"error\":{\"code\":\"not_cancellable\",\"message\":\"over\"}}".utf8))
            }
            if path == "/v1/bookings/\(Self.first)" {
                return (StubURLProtocol.response(url), Data(Self.booking(Self.first, status: "declined").utf8))
            }
            return (StubURLProtocol.response(url),
                    Data("{\"items\":[\(Self.booking(Self.first))],\"next_cursor\":null}".utf8))
        }
        let model = makeModel()
        await model.load()
        let id = try XCTUnwrap(UUID(uuidString: Self.first))
        let done = await model.cancel(id)
        XCTAssertFalse(done)
        XCTAssertEqual(model.cancelProblem, .notCancellable)
        XCTAssertEqual(model.booking(id: id)?.status, "declined", "the status that made it impossible is shown")
        model.dismissCancelProblem()
        XCTAssertNil(model.cancelProblem)
    }

    func testCancelWithoutConnectionKeepsTheBooking() async throws {
        StubURLProtocol.install { request in
            if request.httpMethod == "POST" { throw URLError(.notConnectedToInternet) }
            return (StubURLProtocol.response(request.url!),
                    Data("{\"items\":[\(Self.booking(Self.first))],\"next_cursor\":null}".utf8))
        }
        let model = makeModel()
        await model.load()
        let id = try XCTUnwrap(UUID(uuidString: Self.first))
        let done = await model.cancel(id)
        XCTAssertFalse(done)
        XCTAssertEqual(model.cancelProblem, .network)
        XCTAssertEqual(model.booking(id: id)?.status, "confirmed")
    }

    // MARK: - Dates

    func testWhenIsShownInAlmatyTime() throws {
        let en = Locale(identifier: "en_US")
        let table = try JSONDecoder().decode(Booking.self, from: Data(Self.booking(Self.first).utf8))
        let text = try XCTUnwrap(BookingFormatting.when(table, locale: en))
        XCTAssertTrue(text.contains("19:00"), text)
        XCTAssertTrue(text.contains("Dec"), text)
        // A time written in UTC is shown in Almaty (+05:00).
        let utc = try JSONDecoder().decode(
            Booking.self, from: Data(Self.booking(Self.first, start: "2026-12-06T14:00:00Z").utf8)
        )
        XCTAssertTrue(try XCTUnwrap(BookingFormatting.when(utc, locale: en)).contains("19:00"))
        let food = try JSONDecoder().decode(
            Booking.self, from: Data(Self.booking(Self.first, kind: "food").replacingOccurrences(
                of: "\"2026-12-06T19:00:00+05:00\"", with: "null"
            ).utf8)
        )
        XCTAssertNil(BookingFormatting.when(food, locale: en), "a food order has no time")
    }
}
