@testable import Jol
import XCTest

/// Ш-62: the intercity parts of the live route and of the plan by days (SSOT §5.4 п. 7, §11.1, §11.3): decoding
/// with and without the new fields, the texts, the arc of a long edge, the day model and the camera points.
@MainActor
final class IntercityTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!

    private func trip() throws -> TripOverview {
        try JSONDecoder().decode(TripOverview.self, from: Data(IntercityStub.json(id: IntercityStub.tripID).utf8))
    }

    private func liveRoute(_ turn: Int) throws -> LiveRoute {
        let text = ChatStub.fixture("chat-icity-\(turn)")
        for chunk in text.components(separatedBy: "\n\n") where chunk.hasPrefix("event: live_route") {
            let json = String(chunk.drop { $0 != "{" })
            return try JSONDecoder().decode(LiveRoute.self, from: Data(json.utf8))
        }
        throw XCTSkip("no live_route in turn \(turn)")
    }

    // MARK: - Live route decoding

    func testIntercityLegsDecodeWithModeFlagAndPrice() throws {
        let route = try liveRoute(4)
        XCTAssertEqual(route.stops.map(\.place.name), [
            "Shymbulak", "Charyn Canyon", "Kolsai Lakes", "Khoja Ahmed Yasawi Mausoleum",
        ])
        XCTAssertEqual(route.legs.map(\.mode), [.car, .car, .plane])
        XCTAssertEqual(route.legs.map(\.isIntercity), [true, true, true])
        let plane = route.legs[2]
        XCTAssertEqual(plane.priceKztMin, 18_000)
        XCTAssertEqual(plane.priceKztMax, 35_000)
        XCTAssertEqual(route.edges.map(\.id), ["1-2", "2-3", "3-4"])
    }

    func testOldLegsHaveNoIntercityFields() throws {
        let json = """
        {"stops":[],"legs":[{"from_ord":1,"to_ord":2,"mode":"transit","duration_s":1080,"distance_m":8600}]}
        """
        let leg = try XCTUnwrap(JSONDecoder().decode(LiveRoute.self, from: Data(json.utf8)).legs.first)
        XCTAssertEqual(leg.mode, .transit)
        XCTAssertFalse(leg.intercity)
        XCTAssertFalse(leg.isIntercity)
        XCTAssertNil(leg.priceKztMin)
    }

    func testUnknownIntercityModeStaysLabelledWithAGenericIcon() throws {
        let json = """
        {"stops":[],"legs":[{"from_ord":1,"to_ord":2,"mode":"hyperloop","duration_s":7200,"intercity":true,
        "price_kzt_min":"oops"}]}
        """
        let leg = try XCTUnwrap(JSONDecoder().decode(LiveRoute.self, from: Data(json.utf8)).legs.first)
        XCTAssertNil(leg.mode)
        XCTAssertTrue(leg.isIntercity)
        XCTAssertTrue(leg.isLabelled, "an unknown way between cities is still drawn with a label")
        XCTAssertNil(leg.priceKztMin, "a malformed price does not break the leg")
        XCTAssertEqual(LiveRouteFormatting.edgeSymbol(leg.mode), LiveRouteFormatting.genericIntercitySymbol)
        // An unknown way inside a city keeps the old behaviour: no label.
        let local = LiveLeg(fromOrd: 1, toOrd: 2, mode: nil, durationS: 60)
        XCTAssertFalse(local.isLabelled)
    }

    func testIntercityOnlyModesAreIntercityWithoutTheFlag() {
        for mode in [LiveMode.plane, .train, .busIntercity, .tour] {
            XCTAssertTrue(LiveLeg(fromOrd: 1, toOrd: 2, mode: mode, durationS: 60).isIntercity)
        }
        XCTAssertFalse(LiveLeg(fromOrd: 1, toOrd: 2, mode: .car, durationS: 60).isIntercity)
        XCTAssertEqual(LiveMode(rawValue: "bus_intercity"), .busIntercity)
    }

    // MARK: - Live route texts

    func testIntercityLabelsUseHoursAndATilde() {
        XCTAssertEqual(LiveRouteFormatting.intercityDuration(2 * 3600, language: "en"), "~2 h")
        XCTAssertEqual(LiveRouteFormatting.intercityDuration(2 * 3600, language: "ru"), "~2 ч")
        XCTAssertEqual(LiveRouteFormatting.intercityDuration(11 * 3600 + 1800, language: "en"), "~11 h 30 min")
        XCTAssertEqual(LiveRouteFormatting.intercityDuration(50 * 60, language: "en"), "~50 min")
    }

    func testSymbolsOfIntercityModes() {
        XCTAssertEqual(LiveRouteFormatting.symbol(.plane), "airplane")
        XCTAssertEqual(LiveRouteFormatting.symbol(.train), "tram.fill")
        XCTAssertEqual(LiveRouteFormatting.symbol(.busIntercity), "bus.fill")
        XCTAssertEqual(LiveRouteFormatting.symbol(.car), "car.fill")
        XCTAssertEqual(LiveRouteFormatting.symbol(.tour), "binoculars.fill")
    }

    func testSpokenIntercityEdge() throws {
        let edge = try XCTUnwrap(liveRoute(4).edges.last)
        XCTAssertEqual(LiveRouteFormatting.spokenEdge(edge, language: "en"), "From 3 to 4: by plane about 2 hours")
        XCTAssertEqual(LiveRouteFormatting.spokenEdge(edge, language: "ru"), "От 3 до 4: на самолёте около 2 часов")
        XCTAssertEqual(LiveRouteFormatting.spokenApproximate(3600, language: "ru"), "1 часа")
        XCTAssertEqual(LiveRouteFormatting.spokenApproximate(5 * 3600 + 20 * 60, language: "ru"), "5 часов 20 минут")
        XCTAssertEqual(LiveRouteFormatting.spokenApproximate(21 * 3600, language: "ru"), "21 часа")
    }

    // MARK: - Arc

    func testArcBulgesUpAndItsMiddleIsOnTheCurve() {
        let from = CGPoint(x: 0, y: 200), to = CGPoint(x: 300, y: 200)
        let arc = LiveRouteGeometry.arc(from: from, to: to)
        XCTAssertEqual(arc.middle.x, 150, accuracy: 0.001)
        XCTAssertLessThan(arc.middle.y, 200, "bulges to the upper side, like the capsules")
        // The middle of a quadratic curve is a quarter of each end plus half the control point.
        XCTAssertEqual(arc.middle.y, 0.25 * 200 + 0.5 * arc.control.y + 0.25 * 200, accuracy: 0.001)
        // The bulge is capped, so a long edge does not shoot off the screen.
        let far = LiveRouteGeometry.arc(from: .zero, to: CGPoint(x: 3000, y: 0))
        XCTAssertEqual(abs(far.middle.y), 64, accuracy: 0.001)
    }

    func testArcOfAZeroLengthEdgeDoesNotCrash() {
        let point = CGPoint(x: 10, y: 10)
        let arc = LiveRouteGeometry.arc(from: point, to: point)
        XCTAssertEqual(arc.middle.x, 10, accuracy: 0.001)
    }

    // MARK: - Plan days

    func testPlanWithoutTheNewFieldsDecodesAsRegularDays() throws {
        let plan = try JSONDecoder().decode(
            TripOverview.self, from: Data(TripStub.json(id: ChatStub.tripID).utf8))
        XCTAssertTrue(plan.days.allSatisfy { $0.kind == .regular && $0.overnight == nil })
        XCTAssertTrue(plan.days.flatMap(\.legs).allSatisfy { $0.intercity == nil })
        XCTAssertNil(IntercityFormatting.transferTitle(plan.days[0], language: "en"))
        XCTAssertNil(IntercityFormatting.overnightLine(plan.days[0], language: "en"))
    }

    func testDaysCarryKindOvernightAndIntercityLegs() throws {
        let plan = try trip()
        XCTAssertEqual(plan.days.map(\.kind), [.regular, .regular, .regular, .transfer, .transfer])
        XCTAssertEqual(plan.days[2].overnight?.city.en, "Saty")
        XCTAssertEqual(plan.days[2].overnight?.city.ru, "Саты")
        XCTAssertEqual(plan.days[2].overnight?.region, "kz-almaty")
        XCTAssertNotNil(plan.days[2].overnight?.coordinate)
        let flight = try XCTUnwrap(plan.days[4].intercityLeg)
        XCTAssertEqual(flight.chosenModeRaw, "plane")
        XCTAssertNil(flight.chosenMode, "a plane is not one of the in-city ways")
        XCTAssertEqual(flight.travelS, 7200)
        XCTAssertNil(flight.fromItemID)
        let info = try XCTUnwrap(flight.intercity)
        XCTAssertEqual(info.mode, .plane)
        XCTAssertTrue(info.approximate)
        XCTAssertEqual(info.toCity?.en, "Turkestan")
        XCTAssertEqual(info.priceKztMin, 18_000)
        XCTAssertEqual(info.priceKztMax, 35_000)
        XCTAssertNil(plan.days[0].intercityLeg)
    }

    func testUnknownKindAndBrokenOvernightFallBackToARegularDay() throws {
        let json = """
        {"date":"2026-12-05","kind":"teleport","overnight":{"city":"nope"},
         "legs":[{"id":"\(UUID().uuidString)","to_item_id":"\(UUID().uuidString)","intercity":{"mode":"rocket"}}]}
        """
        let day = try JSONDecoder().decode(TripDay.self, from: Data(json.utf8))
        XCTAssertEqual(day.kind, .regular)
        XCTAssertNil(day.overnight)
        let info = try XCTUnwrap(day.legs.first?.intercity)
        XCTAssertNil(info.mode, "an unknown way is kept, with a generic icon")
        XCTAssertEqual(IntercityFormatting.symbol(info.mode), "arrow.left.arrow.right")
        XCTAssertFalse(info.approximate)
    }

    // MARK: - Plan texts

    func testTransferTitleAndOvernightLineInBothLanguages() throws {
        let plan = try trip()
        XCTAssertEqual(IntercityFormatting.transferTitle(plan.days[4], language: "en"), "Travel to Turkestan")
        XCTAssertEqual(IntercityFormatting.transferTitle(plan.days[4], language: "ru"), "Переезд в Туркестан")
        XCTAssertEqual(IntercityFormatting.transferTitle(plan.days[3], language: "ru"), "Переезд в Алматы")
        XCTAssertNil(IntercityFormatting.transferTitle(plan.days[2], language: "en"), "a regular day has no title")
        XCTAssertEqual(IntercityFormatting.overnightLine(plan.days[2], language: "en"), "Overnight: Saty")
        XCTAssertEqual(IntercityFormatting.overnightLine(plan.days[2], language: "ru"), "Ночёвка: Саты")
        XCTAssertEqual(CityName(ru: nil, en: "Saty").text(language: "ru"), "Saty", "the other language fills in")
        XCTAssertNil(CityName(ru: nil, en: nil).text(language: "en"))
    }

    func testPriceRangeAndDurationOfAnIntercityLeg() throws {
        let info = try XCTUnwrap(trip().days[4].intercityLeg?.intercity)
        let range = try XCTUnwrap(IntercityFormatting.priceRange(info, locale: Locale(identifier: "en_US")))
        XCTAssertTrue(range.hasPrefix("~18,000–35,000"), range)
        XCTAssertTrue(range.hasSuffix(Region.current.currencySymbol))
        let english = Locale(identifier: "en_US")
        XCTAssertEqual(
            IntercityFormatting.priceRange(IntercityInfo(mode: .train, priceKztMin: 9_000), locale: english),
            "~9,000\u{00A0}\(Region.current.currencySymbol)")
        XCTAssertNil(IntercityFormatting.priceRange(IntercityInfo(mode: .car), locale: english))
        XCTAssertEqual(IntercityFormatting.duration(seconds: 7200, language: "en"), "~2 h")
        XCTAssertEqual(IntercityFormatting.duration(seconds: 39_600, language: "ru"), "~11 ч")
        XCTAssertEqual(IntercityFormatting.title(.plane, language: "ru"), "Перелёт")
        XCTAssertEqual(IntercityFormatting.title(.bus, language: "en"), "Intercity bus")
    }

    func testSpokenIntercityLeg() throws {
        let flight = try XCTUnwrap(trip().days[4].intercityLeg)
        let ru = try XCTUnwrap(IntercityFormatting.spoken(flight, language: "ru"))
        XCTAssertTrue(ru.hasPrefix("Перелёт в Туркестан, около 2 часов"), ru)
        let en = try XCTUnwrap(IntercityFormatting.spoken(flight, language: "en"))
        XCTAssertTrue(en.hasPrefix("Flight to Turkestan, about 2 hours"), en)
        let drive = try XCTUnwrap(trip().days[2].legs.first)
        XCTAssertTrue(IntercityFormatting.spoken(drive, language: "en")?.hasPrefix("My car to Saty") == true)
    }

    // MARK: - Map

    private func makeModel() -> TripMapModel {
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r")),
            installID: "install-1", session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        return TripMapModel(api: client)
    }

    private func wait(until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(3)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    func testTransferDayDrawsADashedLineBetweenTheCitiesAndFitsBoth() async throws {
        let id = UUID(uuidString: IntercityStub.tripID)!
        StubURLProtocol.install { request in
            let path = request.url?.path ?? ""
            let body = path == "/v1/trips/\(id.uuidString.lowercased())"
                ? IntercityStub.json(id: IntercityStub.tripID) : "{\"items\":[]}"
            return (StubURLProtocol.response(request.url!), Data(body.utf8))
        }
        let model = makeModel()
        model.open(tripID: id)
        await wait { model.phase == .loaded }
        model.selectDay(4)
        XCTAssertEqual(model.stops.count, 1)
        let line = try XCTUnwrap(model.lines.first)
        XCTAssertTrue(line.approximate, "a transfer is a dashed straight line")
        XCTAssertEqual(line.coordinates.count, 2)
        XCTAssertEqual(line.coordinates[0].longitude, 76.8897, accuracy: 0.001, "it leaves from the night in Almaty")
        XCTAssertEqual(line.coordinates[1].longitude, 68.2706, accuracy: 0.001)
        XCTAssertEqual(model.fitExtras.count, 1, "the night in Turkestan is fitted too")
        // The first day has no transfer: no extra line, and the camera holds its stop and the night.
        model.selectDay(0)
        XCTAssertTrue(model.lines.isEmpty)
        // Day 3: the drive between two stops of the day is a dashed line as well.
        model.selectDay(2)
        XCTAssertEqual(model.lines.count, 1)
        XCTAssertTrue(model.lines[0].approximate)
        // All days at once: every transfer is drawn.
        model.selectAllDays()
        XCTAssertEqual(model.lines.count, 3)
        XCTAssertEqual(model.fitExtras.count, 5)
    }
}
