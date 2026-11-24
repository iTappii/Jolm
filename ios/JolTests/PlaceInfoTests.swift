import CoreLocation
import XCTest

@testable import Jol

/// Ш-70: rating / today / logo on the wire, the card's lines, the distance, when pins show on the map.
@MainActor
final class PlaceInfoTests: XCTestCase {
    private let almaty = TimeZone(identifier: "Asia/Almaty")!

    /// 2026-11-24 `hh:mm` in the region's time (UTC+5).
    private func at(_ hour: Int, _ minute: Int = 0) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = almaty
        return calendar.date(from: DateComponents(year: 2026, month: 11, day: 24, hour: hour, minute: minute))!
    }

    private func today(_ json: String) throws -> PlaceToday {
        try JSONDecoder().decode(PlaceToday.self, from: Data(json.utf8))
    }

    // MARK: - Decoding

    func testDecodesRatingTodayAndLogo() throws {
        let data = Data(UITestSupport.detailJSON(id: UITestSupport.centerPlaceID).utf8)
        let place = try JSONDecoder().decode(PlaceDetail.self, from: data)
        XCTAssertEqual(place.rating, PlaceRating(average: 4.6, count: 23))
        XCTAssertEqual(place.today, PlaceToday(opens: "10:00", closes: "23:00", openNow: true))
        XCTAssertNil(place.logoURL)
        let bakery = try JSONDecoder().decode(
            PlaceDetail.self, from: Data(UITestSupport.detailJSON(id: UITestSupport.logoPlaceID).utf8))
        XCTAssertEqual(bakery.logoURL, "asset:StubLogo")
        XCTAssertEqual(bakery.today?.closedToday, true)
    }

    func testOlderServerWithoutTheNewFieldsStillDecodes() throws {
        let json = """
        {"id":"\(UITestSupport.centerPlaceID)","name":"A","description":null,"category":null,"kind":"venue","lat":1,\
        "lon":2,"address":null,"website":null,"prices":{},"typical_visit_min":null,"is_public":true,\
        "is_partner":false,"photos":[],"hours":[],"open_now":null}
        """
        let place = try JSONDecoder().decode(PlaceDetail.self, from: Data(json.utf8))
        XCTAssertNil(place.rating)
        XCTAssertNil(place.today)
        XCTAssertNil(place.logoURL)
    }

    func testNullRatingAndSparseTodayDecode() throws {
        let sparse = try today(#"{"open_now":null}"#)
        XCTAssertNil(sparse.opens)
        XCTAssertFalse(sparse.open24h)
        XCTAssertFalse(sparse.closedToday)
        let summary = try JSONDecoder().decode(
            PlaceSummary.self,
            from: Data(UITestSupport.summary("a0000000-0000-4000-8000-0000000000aa", "X", "cafe_oriental", 1, 2,
                                             logo: "https://x/y.png").utf8))
        XCTAssertEqual(summary.logoURL, "https://x/y.png")
    }

    // MARK: - Today line

    func testTodayLineCases() throws {
        func line(_ json: String, _ hour: Int, _ minute: Int = 0) throws -> TodayLine? {
            PlaceFormatting.todayLine(try today(json), now: at(hour, minute), timeZone: almaty)
        }
        let open = #"{"opens":"10:00","closes":"23:00","open_now":true}"#
        XCTAssertEqual(try line(open, 12), .hours(opens: "10:00", closes: "23:00", state: .open))
        let shut = #"{"opens":"10:00","closes":"23:00","open_now":false}"#
        XCTAssertEqual(try line(shut, 8), .opensAt("10:00"), "before the opening time")
        XCTAssertEqual(try line(shut, 23, 30), .hours(opens: "10:00", closes: "23:00", state: .closed), "after closing")
        XCTAssertEqual(try line(#"{"opens":"10:00","closes":"23:00"}"#, 12),
                       .hours(opens: "10:00", closes: "23:00", state: .unknown))
        XCTAssertEqual(try line(#"{"open_24h":true,"open_now":true}"#, 3), .open24h)
        XCTAssertEqual(try line(#"{"closed_today":true,"open_now":false}"#, 12), .closedToday)
        XCTAssertNil(try line(#"{"open_now":true}"#, 12), "no hours at all")
    }

    func testTodayLinePastMidnight() throws {
        func line(_ openNow: Bool, _ hour: Int, _ minute: Int = 0) throws -> TodayLine? {
            let json = #"{"opens":"18:00","closes":"02:00","open_now":\#(openNow)}"#
            return PlaceFormatting.todayLine(try today(json), now: at(hour, minute), timeZone: almaty)
        }
        XCTAssertEqual(try line(true, 23, 30), .hours(opens: "18:00", closes: "02:00", state: .open))
        XCTAssertEqual(try line(true, 1), .hours(opens: "18:00", closes: "02:00", state: .open), "after midnight")
        XCTAssertEqual(try line(false, 3), .opensAt("18:00"), "closed at 03:00, opens in the evening")
        XCTAssertEqual(try line(false, 18, 1), .hours(opens: "18:00", closes: "02:00", state: .closed))
    }

    func testTodayLineWording() {
        XCTAssertEqual(PlaceFormatting.text(for: .hours(opens: "10:00", closes: "23:00", state: .open), language: "ru"),
                       "Сегодня 10:00–23:00 · Открыто")
        XCTAssertEqual(PlaceFormatting.text(for: .hours(opens: "10:00", closes: "23:00", state: .open), language: "en"),
                       "Today 10:00–23:00 · Open")
        XCTAssertEqual(PlaceFormatting.text(for: .opensAt("10:00"), language: "ru"), "Закрыто · откроется в 10:00")
        XCTAssertEqual(PlaceFormatting.text(for: .opensAt("10:00"), language: "en"), "Closed · opens at 10:00")
        XCTAssertEqual(PlaceFormatting.text(for: .open24h, language: "ru"), "Круглосуточно")
        XCTAssertEqual(PlaceFormatting.text(for: .closedToday, language: "ru"), "Сегодня выходной")
        XCTAssertEqual(PlaceFormatting.text(for: .closedToday, language: "en"), "Closed today")
    }

    // MARK: - Reviews plural

    private func reviews(_ count: Int, _ language: String) -> String {
        String(format: L10n.string("(%lld reviews)", language: language), locale: Locale(identifier: language), count)
    }

    func testRussianPluralOfReview() {
        XCTAssertEqual(reviews(1, "ru"), "(1 отзыв)")
        XCTAssertEqual(reviews(2, "ru"), "(2 отзыва)")
        XCTAssertEqual(reviews(4, "ru"), "(4 отзыва)")
        XCTAssertEqual(reviews(5, "ru"), "(5 отзывов)")
        XCTAssertEqual(reviews(11, "ru"), "(11 отзывов)")
        XCTAssertEqual(reviews(21, "ru"), "(21 отзыв)")
        XCTAssertEqual(reviews(23, "ru"), "(23 отзыва)")
        XCTAssertEqual(reviews(112, "ru"), "(112 отзывов)")
    }

    func testEnglishPluralOfReview() {
        XCTAssertEqual(reviews(1, "en"), "(1 review)")
        XCTAssertEqual(reviews(23, "en"), "(23 reviews)")
    }

    func testStarSymbols() {
        XCTAssertEqual((1...5).map { PlaceHeaderView.symbol(star: $0, average: 4.6) },
                       ["star.fill", "star.fill", "star.fill", "star.fill", "star.leadinghalf.filled"])
        XCTAssertEqual((1...5).map { PlaceHeaderView.symbol(star: $0, average: 1.0) },
                       ["star.fill", "star", "star", "star", "star"])
    }

    // MARK: - Distance

    func testDistanceText() {
        XCTAssertEqual(PlaceFormatting.distanceText(meters: 4, language: "en"), "10 m")
        XCTAssertEqual(PlaceFormatting.distanceText(meters: 847, language: "en"), "850 m")
        XCTAssertEqual(PlaceFormatting.distanceText(meters: 847, language: "ru"), "850 м")
        XCTAssertEqual(PlaceFormatting.distanceText(meters: 996, language: "ru"), "1,0 км")
        XCTAssertEqual(PlaceFormatting.distanceText(meters: 1234, language: "ru"), "1,2 км")
        XCTAssertEqual(PlaceFormatting.distanceText(meters: 1234, language: "en"), "1.2 km")
        XCTAssertEqual(PlaceFormatting.distanceText(meters: 14_600, language: "en"), "15 km")
        XCTAssertEqual(PlaceFormatting.distanceFromYou(meters: 1234, language: "ru"), "1,2 км от вас")
        XCTAssertEqual(PlaceFormatting.distanceFromYou(meters: 1234, language: "en"), "1.2 km away")
    }

    func testDistanceFromTheUser() {
        let user = GeoPoint(lat: 43.2310, lon: 76.9350)
        let place = CLLocationCoordinate2D(latitude: 43.2310, longitude: 76.9350 + 0.01)
        let meters = PlaceFormatting.distance(from: user, to: place)
        XCTAssertEqual(meters, 810, accuracy: 15, "0.01° of longitude at 43° is about 810 m")
    }

    // MARK: - Pins by zoom

    func testPinsShowFromStreetZoomOnly() {
        XCTAssertFalse(PlacePinVisibility.showsPins(atZoom: 11))
        XCTAssertFalse(PlacePinVisibility.showsPins(atZoom: 14.5), "landmarks only at mid zoom")
        XCTAssertTrue(PlacePinVisibility.showsPins(atZoom: 15))
        XCTAssertTrue(PlacePinVisibility.showsPins(atZoom: 17.5))
        // The sights come in at 12–13 (Ш-69): the pins never share a zoom range with the lowest sights.
        XCTAssertTrue(UITestSupport.landmarkFixtures.allSatisfy { $0.minZoom < PlacePinVisibility.streetZoom })
    }
}
