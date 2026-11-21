import XCTest

/// Ш-44. Reviews of a place and «Add info» on the stub API (`-JolStubAPI`): the fixture cafe has two reviews, the
/// museum has none; a review whose text contains "spam" is refused by the stub's filter.
@MainActor
final class ContentUITests: XCTestCase {
    private func launch(signedIn: Bool = true, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if signedIn { app.launchArguments.append("-JolStubSignedIn") }
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

    private func collapseChat(_ app: XCUIApplication) {
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        XCTAssertTrue(app.buttons["chat-collapsed-bar"].waitForExistence(timeout: 5))
    }

    private func openMuseum(_ app: XCUIApplication) {
        collapseChat(app)
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
    }

    /// The cafe is the second stop of the fixture trip (signed-in only: «My trips» is in the side panel).
    private func openCafe(_ app: XCUIApplication) {
        app.buttons["open-sidebar"].tap()
        let row = element(app, "sidebar-trip-row")
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        waitFor(app, "trip-stop-2")
        element(app, "trip-stop-2").tap()
        waitFor(app, "place-card")
        waitFor(app, "place-tab-reviews")
    }

    private func openReviewForm(_ app: XCUIApplication) {
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-write-review")
        element(app, "place-write-review").tap()
        waitFor(app, "content-sheet")
    }

    func testReviewsTabShowsTheServersReviews() {
        let app = launch()
        openCafe(app)
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-reviews-summary")
        let summary = element(app, "place-reviews-summary").label
        XCTAssertTrue(summary.contains("4.5"), summary)
        XCTAssertTrue(summary.contains("2 reviews"), summary)
        let rows = app.descendants(matching: .any).matching(identifier: "review-row")
        XCTAssertEqual(rows.count, 2)
        let all = rows.allElementsBoundByIndex.map(\.label).joined(separator: "|")
        XCTAssertTrue(all.contains("Great coffee and a calm room."), all)
        XCTAssertTrue(all.contains("Anonymous"), "no display name → «Anonymous»")
        XCTAssertTrue(all.contains("Aigerim"))
        XCTAssertTrue(all.contains("will be checked later"), "a review that still waits for the moderator says so")
        XCTAssertFalse(element(app, "place-reviews-empty").exists)
    }

    func testNoReviewsKeepsTheEmptyState() {
        let app = launch()
        openMuseum(app)
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-reviews-empty")
        XCTAssertTrue(element(app, "place-write-review").exists)
    }

    func testSignedInSendsAReviewAndSeesTheCheckedLaterNote() {
        let app = launch()
        openCafe(app)
        openReviewForm(app)
        XCTAssertFalse(element(app, "content-submit").isEnabled, "a rating is required")
        element(app, "content-star-5").tap()
        XCTAssertTrue(element(app, "content-submit").isEnabled)
        element(app, "content-submit").tap()
        waitFor(app, "content-result")
        XCTAssertEqual(element(app, "content-result-title").label, "Thank you!")
        XCTAssertTrue(element(app, "content-result-note").label.contains("checked later"))
        element(app, "content-close").tap()
        XCTAssertTrue(element(app, "content-sheet").waitForNonExistence(timeout: 5))
    }

    func testFilterRefusalIsNotAnErrorAndRussianStringsWork() {
        let app = launch(language: "ru")
        openCafe(app)
        openReviewForm(app)
        element(app, "content-star-2").tap()
        let text = element(app, "content-review-text")
        text.tap()
        text.typeText("spam")
        element(app, "content-submit").tap()
        waitFor(app, "content-result")
        XCTAssertEqual(element(app, "content-result-title").label, "Не прошло автоматическую проверку")
        XCTAssertTrue(element(app, "content-result-note").label.contains("не начислен"))
    }

    func testAlreadyReviewedIsTold() {
        let app = launch()
        openCafe(app)
        openReviewForm(app)
        element(app, "content-star-3").tap()
        let text = element(app, "content-review-text")
        text.tap()
        text.typeText("again")
        element(app, "content-submit").tap()
        waitFor(app, "content-error")
        XCTAssertEqual(element(app, "content-error").label, "You have already left a review here.")
        XCTAssertFalse(element(app, "content-result").exists)
    }

    func testGuestMeetsTheSignInGate() {
        let app = launch(signedIn: false)
        openMuseum(app)
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-write-review")
        element(app, "place-write-review").tap()
        waitFor(app, "account-gate")
        XCTAssertFalse(element(app, "content-sheet").exists, "the form opens only after signing in")
    }

    func testAnAddressCardHasNoAddInfo() {
        let app = launch()
        collapseChat(app)
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.25, dy: 0.3)).tap()
        waitFor(app, "point-card")
        XCTAssertFalse(element(app, "place-add-info").exists)
        XCTAssertFalse(element(app, "place-write-review").exists)
    }
}
