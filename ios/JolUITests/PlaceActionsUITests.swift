import XCTest

/// Ш-47 (crowd), Ш-48 (events), Ш-49 (booking) on the stub API. The cafe has crowd statistics, an event and a booking
/// partner; the museum has none of them.
@MainActor
final class PlaceActionsUITests: XCTestCase {
    private func launch(signedIn: Bool = true, location: String? = nil, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if signedIn { app.launchArguments.append("-JolStubSignedIn") }
        if let location { app.launchArguments += ["-JolStubLocation", location] }
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

    private func capture(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func collapseChat(_ app: XCUIApplication) {
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        XCTAssertTrue(app.buttons["chat-collapsed-bar"].waitForExistence(timeout: 5))
    }

    /// The museum sits at the map centre; pins load asynchronously, so tap until its card opens.
    private func openMuseum(_ app: XCUIApplication) {
        collapseChat(app)
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
    }

    /// The cafe is the second stop of the fixture trip: it is reached from the side panel's «My trips».
    private func openCafe(_ app: XCUIApplication) {
        app.buttons["open-sidebar"].tap()
        let row = element(app, "sidebar-trip-row")
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        waitFor(app, "trip-stop-2")
        element(app, "trip-stop-2").tap()
        waitFor(app, "place-card")
        waitFor(app, "place-crowd-actions")
    }

    // MARK: - Crowd (Ш-47)

    func testCrowdBlockOnlyWhenThePlaceHasData() {
        let app = launch()
        openMuseum(app)
        waitFor(app, "place-crowd-actions")
        XCTAssertFalse(element(app, "place-crowd").exists, "no statistics block while `crowd` is null")
        XCTAssertTrue(element(app, "place-checkin").exists, "adding data stays possible")
        XCTAssertFalse(element(app, "place-book").isEnabled, "no partner, no booking")
    }

    func testCheckInTooFarThenNearby() {
        let app = launch()
        openMuseum(app)
        waitFor(app, "place-checkin")
        element(app, "place-checkin").tap()
        waitFor(app, "place-crowd-outcome")
        let outcome = element(app, "place-crowd-outcome")
        XCTAssertTrue(outcome.label.contains("200 m"), outcome.label)

        let near = launch(location: "near")
        openMuseum(near)
        waitFor(near, "place-checkin")
        element(near, "place-checkin").tap()
        waitFor(near, "place-crowd-outcome")
        XCTAssertTrue(element(near, "place-crowd-outcome").label.contains("checked in"))
        element(near, "place-crowd-busy").tap()
        waitFor(near, "place-crowd-outcome")
        XCTAssertTrue(element(near, "place-crowd-outcome").label.contains("Thanks for the report"),
                      element(near, "place-crowd-outcome").label)
        capture("place-crowd-actions")
    }

    func testRepeatedCheckInAndRateLimit() {
        let app = launch(location: "near")
        openMuseum(app)
        waitFor(app, "place-checkin")
        element(app, "place-checkin").tap()
        waitFor(app, "place-crowd-outcome")
        XCTAssertTrue(element(app, "place-crowd-outcome").label.contains("checked in"))
        element(app, "place-checkin").tap()
        let again = NSPredicate(format: "label CONTAINS %@", "a moment ago")
        expectation(for: again, evaluatedWith: element(app, "place-crowd-outcome"))
        waitForExpectations(timeout: 10)
        element(app, "place-crowd-empty").tap()
        let limited = NSPredicate(format: "label CONTAINS %@", "Try again in 2 min")
        expectation(for: limited, evaluatedWith: element(app, "place-crowd-outcome"))
        waitForExpectations(timeout: 10)
    }

    func testCrowdBlockAndBookingOnThePartnerCafe() {
        let app = launch(location: "near")
        openCafe(app)
        waitFor(app, "place-crowd")
        XCTAssertTrue(element(app, "place-crowd-now").label.contains("Busy"), element(app, "place-crowd-now").label)
        XCTAssertTrue(element(app, "place-crowd-chart").exists)
        XCTAssertTrue(element(app, "place-book").isEnabled, "the cafe has a partner")
        XCTAssertTrue(element(app, "place-events").exists)
        XCTAssertTrue(element(app, "place-event").exists)
        capture("place-crowd-block")
    }

    // MARK: - Booking (Ш-49)

    func testBookingRequestFlow() {
        let app = launch()
        openCafe(app)
        element(app, "place-book").tap()
        waitFor(app, "booking-sheet")
        XCTAssertTrue(element(app, "booking-kind").exists, "the cafe takes tables and tickets")
        element(app, "booking-submit").tap()
        waitFor(app, "booking-result")
        XCTAssertEqual(element(app, "booking-status").label, "Confirmed")
        capture("booking-confirmed")
        element(app, "booking-close").tap()
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, "booking-sheet"))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 10), .completed)
    }

    func testBookingUnavailableShowsAnError() {
        let app = launch()
        openCafe(app)
        element(app, "place-book").tap()
        waitFor(app, "booking-sheet")
        let note = element(app, "booking-note")
        note.tap()
        note.typeText("full")
        element(app, "booking-submit").tap()
        waitFor(app, "booking-error")
        let error = element(app, "booking-error")
        XCTAssertTrue(error.label.contains("can't take this"), error.label)
    }

    func testGuestBookingMeetsTheSignInGate() {
        let app = launch(signedIn: false)
        collapseChat(app)
        // A guest reaches only the museum (the cafe is in a trip, which needs an account).
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        waitFor(app, "place-crowd-actions")
        element(app, "place-checkin").tap()
        waitFor(app, "account-gate")
    }

    // MARK: - Events (Ш-48)

    func testEventCardShowsTheAdLabel() {
        // The offline stub style draws no circle layers, so the pin cannot be tapped: the app opens the first
        // loaded event itself (`-JolStubSelectEvent`); the pin on the real map is checked by hand (see the review).
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSelectEvent", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "-jol.language", "system"]
        app.launch()
        waitFor(app, "event-card")
        XCTAssertEqual(element(app, "event-title").label, "Fixture Jazz Night")
        XCTAssertEqual(element(app, "event-ad-label").label, "Ad")
        XCTAssertTrue(element(app, "event-when").exists)
        capture("event-card-ad")
    }
}
