import XCTest

/// Ш-37, the full route map (milestone M3), on the trip fixture of the stub API (`-JolStubAPI`): a three-day trip
/// over budget with legs that carry transport options. Opened from the side panel's «My trips».
@MainActor
final class TripMapUITests: XCTestCase {
    private func launch(language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func waitFor(_ app: XCUIApplication, _ identifier: String, timeout: TimeInterval = 15,
                         file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(element(app, identifier).waitForExistence(timeout: timeout), "\(identifier) never appeared",
                      file: file, line: line)
    }

    private func waitGone(_ app: XCUIApplication, _ identifier: String, timeout: TimeInterval = 10,
                          file: StaticString = #filePath, line: UInt = #line) {
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, identifier))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: timeout), .completed, "\(identifier) is still there",
                       file: file, line: line)
    }

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func openTrip(_ app: XCUIApplication) {
        let open = app.buttons["open-sidebar"]
        XCTAssertTrue(open.waitForExistence(timeout: 10))
        open.tap()
        let row = element(app, "sidebar-trip-row")
        XCTAssertTrue(row.waitForExistence(timeout: 10), app.debugDescription)
        row.tap()
        waitFor(app, "trip-map")
        waitFor(app, "trip-stop-1")
    }

    func testDaysStopsLegsAndTransportChoice() {
        let app = launch()
        openTrip(app)

        // Day 1: numbered stops with times, the leg between them.
        XCTAssertTrue(element(app, "trip-stop-1").label.contains("Fixture Museum"), element(app, "trip-stop-1").label)
        XCTAssertTrue(element(app, "trip-stop-1").label.contains("09:30"))
        XCTAssertTrue(element(app, "trip-stop-2").label.contains("Fixture Cafe"))
        XCTAssertTrue(element(app, "trip-day-chip-3").exists, "every day of the trip has a chip, empty ones too")
        capture("trip-map-day-1")

        // Day 2: other stops; the empty day 3 says so.
        element(app, "trip-day-chip-2").tap()
        XCTAssertTrue(element(app, "trip-stop-1").label.contains("Fixture Cafe"), element(app, "trip-stop-1").label)
        capture("trip-map-day-2")
        element(app, "trip-day-chip-3").tap()
        waitFor(app, "trip-free-day")
        element(app, "trip-day-chip-1").tap()

        // The leg: options with the chosen one marked; a slow mode warns about the late arrival.
        waitFor(app, "trip-leg-row")
        element(app, "trip-leg-row").tap()
        waitFor(app, "trip-leg-sheet")
        XCTAssertTrue(element(app, "trip-leg-option-bus").isSelected, "the plan's own choice is marked")
        XCTAssertTrue(element(app, "trip-leg-option-taxi").exists)
        XCTAssertFalse(element(app, "trip-leg-late").exists)
        element(app, "trip-leg-option-walk").tap()
        waitFor(app, "trip-leg-late")
        XCTAssertTrue(element(app, "trip-leg-option-walk").isSelected)
        capture("trip-leg-options")
        element(app, "trip-leg-option-taxi").tap()
        waitGone(app, "trip-leg-late")
        XCTAssertTrue(element(app, "trip-leg-option-taxi").isSelected)
        element(app, "trip-leg-done").tap()
        waitGone(app, "trip-leg-sheet")
    }

    func testBudgetWarningAndTheTwoVariants() {
        let app = launch()
        openTrip(app)
        waitFor(app, "trip-over-budget")
        capture("trip-map-over-budget")
        element(app, "trip-over-budget").tap()
        waitFor(app, "trip-budget-sheet")
        XCTAssertTrue(element(app, "trip-budget-over").label.contains("20"), element(app, "trip-budget-over").label)
        waitFor(app, "trip-budget-variant-drop_places")
        waitFor(app, "trip-budget-variant-cheaper")
        XCTAssertFalse(element(app, "trip-budget-infeasible-drop_places").exists)
        XCTAssertTrue(element(app, "trip-budget-infeasible-cheaper").exists,
                      "a variant that still does not fit says so")
        capture("trip-budget-variants")
        element(app, "trip-budget-choose-drop_places").tap()
        waitFor(app, "trip-budget-chosen")
        element(app, "trip-budget-done").tap()
        waitGone(app, "trip-over-budget")
    }

    func testRemovingAMustHaveAsksFirst() {
        let app = launch()
        openTrip(app)

        // An ordinary stop goes at once.
        element(app, "trip-stop-remove-2").tap()
        waitGone(app, "trip-stop-2")
        XCTAssertTrue(element(app, "trip-stop-1").label.contains("Fixture Museum"))

        // The must-have: the server answers 409, the app asks; «Keep it» changes nothing, «Remove anyway» removes.
        element(app, "trip-stop-remove-1").tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 10), app.debugDescription)
        app.alerts.buttons["Keep it"].firstMatch.tap()
        XCTAssertTrue(element(app, "trip-stop-1").label.contains("Fixture Museum"))
        element(app, "trip-stop-remove-1").tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 10))
        app.alerts.buttons["Remove anyway"].firstMatch.tap()
        waitFor(app, "trip-free-day")
    }

    func testTappingAStopOpensThePlaceCard() {
        let app = launch()
        openTrip(app)
        element(app, "trip-stop-1").tap()
        waitFor(app, "place-card")
        XCTAssertEqual(app.staticTexts["place-name"].label, "Fixture Museum")
        waitGone(app, "trip-panel")
    }

    func testRussianLabels() {
        let app = launch(language: "ru")
        openTrip(app)
        XCTAssertTrue(element(app, "trip-day-title").label.contains("День 1"), element(app, "trip-day-title").label)
        let over = element(app, "trip-over-budget")
        XCTAssertTrue(over.label.contains("Превышение"), over.label)
    }
}
