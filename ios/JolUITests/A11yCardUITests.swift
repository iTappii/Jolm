import XCTest

/// Ш-52 (card, content forms, favorites, sign-in): the largest text size (AX3) on the stub API. The theme is the
/// simulator's (`xcrun simctl ui <device> appearance dark|light`; a launch argument does not switch it): run the class
/// once per theme with `TEST_RUNNER_A11Y_THEME=dark|light`, which only names the screenshots. Screenshots go to the
/// test report and, with `TEST_RUNNER_A11Y_SHOTS=<dir>`, to that folder.
@MainActor
final class A11yCardUITests: XCTestCase {
    private static let xxxl = "UICTContentSizeCategoryAccessibilityXXXL"

    private let theme = ProcessInfo.processInfo.environment["A11Y_THEME"] ?? "dark"

    private func launch(signedIn: Bool = true, large: Bool = true, language: String = "en",
                        reviews: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if reviews { app.launchArguments.append("-JolStubReviewsForAll") }
        if large { app.launchArguments += ["-UIPreferredContentSizeCategoryName", Self.xxxl] }
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

    private func shot(_ app: XCUIApplication, _ name: String) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "\(name)-\(theme)"
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = ProcessInfo.processInfo.environment["A11Y_SHOTS"], !dir.isEmpty {
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            let file = URL(fileURLWithPath: dir).appendingPathComponent("\(name)-\(theme).png")
            try? screenshot.pngRepresentation.write(to: file)
        }
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
        waitFor(app, "place-directions")
    }

    /// A control is reachable: on the screen, not under another one, at least 44 pt each way (HIG).
    private func assertTapTarget(_ app: XCUIApplication, _ identifier: String,
                                 file: StaticString = #filePath, line: UInt = #line) {
        let control = element(app, identifier)
        XCTAssertTrue(control.exists, "\(identifier) missing", file: file, line: line)
        XCTAssertTrue(control.isHittable, "\(identifier) not hittable", file: file, line: line)
        XCTAssertGreaterThanOrEqual(control.frame.height, 43.5, "\(identifier) height", file: file, line: line)
        XCTAssertGreaterThanOrEqual(control.frame.width, 43.5, "\(identifier) width", file: file, line: line)
        XCTAssertTrue(app.frame.contains(control.frame), "\(identifier) outside the screen", file: file, line: line)
    }

    // MARK: - Place card

    func testCardAtLargestTextDark() {
        let app = launch()
        openMuseum(app)
        // The pinned buttons stay reachable even though the sheet is only a third of the screen.
        assertTapTarget(app, "place-directions")
        assertTapTarget(app, "place-favorite")
        XCTAssertEqual(element(app, "place-favorite").label, "Add to favorites", "the heart is named for VoiceOver")
        shot(app, "card-ax3-third")

        element(app, "place-card").swipeUp()
        assertTapTarget(app, "place-directions")
        for tab in ["overview", "reviews", "photos"] {
            let button = element(app, "place-tab-\(tab)")
            XCTAssertTrue(button.exists)
            XCTAssertGreaterThanOrEqual(button.frame.height, 43.5, "tab \(tab)")
        }
        XCTAssertTrue(element(app, "place-tab-overview").isSelected, "the selected tab is announced as selected")
        shot(app, "card-ax3-large")
        element(app, "place-tab-reviews").tap()
        XCTAssertTrue(element(app, "place-tab-reviews").isSelected)
        XCTAssertFalse(element(app, "place-tab-overview").isSelected)
        waitFor(app, "place-reviews-empty")
        shot(app, "card-reviews-empty-ax3")
    }

    func testCardAtNormalSize() {
        let app = launch(large: false)
        openMuseum(app)
        assertTapTarget(app, "place-directions")
        assertTapTarget(app, "place-favorite")
        element(app, "place-card").swipeUp()
        shot(app, "card-normal-large")
    }

    func testReviewRowsAnnounceTheRatingAtLargestText() {
        let app = launch(reviews: true)
        openMuseum(app)
        element(app, "place-card").swipeUp()
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-reviews-summary")
        let first = app.descendants(matching: .any).matching(identifier: "review-row").firstMatch
        XCTAssertTrue(first.waitForExistence(timeout: 5))
        XCTAssertTrue(first.label.contains("5 of 5"), "the stars are read as a number: \(first.label)")
        shot(app, "card-reviews-ax3")
    }

    func testAddressCardAtLargestText() {
        let app = launch()
        collapseChat(app)
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.25, dy: 0.3)).tap()
        waitFor(app, "point-card")
        assertTapTarget(app, "place-directions")
        shot(app, "address-card-ax3")
    }

    // MARK: - Add info form

    func testContentFormAtLargestText() {
        let app = launch()
        openMuseum(app)
        element(app, "place-card").swipeUp()
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-write-review")
        app.swipeUp()
        assertTapTarget(app, "place-write-review")
        element(app, "place-write-review").tap()
        waitFor(app, "content-sheet")
        for star in 1...5 { assertTapTarget(app, "content-star-\(star)") }
        XCTAssertEqual(element(app, "content-star-4").label, "4 of 5")
        element(app, "content-star-4").tap()
        XCTAssertTrue(element(app, "content-star-4").isSelected)
        shot(app, "content-form-ax3")
    }

    func testContentFormInRussian() {
        let app = launch(large: false, language: "ru")
        openMuseum(app)
        element(app, "place-card").swipeUp()
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-write-review")
        element(app, "place-write-review").tap()
        waitFor(app, "content-sheet")
        XCTAssertEqual(element(app, "content-star-4").label, "4 из 5")
        shot(app, "content-form-normal-ru")
    }

    // MARK: - Sign in

    func testSignInGateAtLargestText() {
        let app = launch(signedIn: false)
        openMuseum(app)
        element(app, "place-card").swipeUp()
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-write-review")
        element(app, "place-write-review").tap()
        waitFor(app, "account-gate")
        waitFor(app, "sign-in-destination")
        shot(app, "gate-ax3-1")
        let field = element(app, "sign-in-destination")
        XCTAssertGreaterThanOrEqual(field.frame.height, 43.5)
        field.tap()
        field.typeText("tourist@example.com")
        XCTAssertGreaterThanOrEqual(element(app, "sign-in-send").frame.height, 43.5, "the send button")
        shot(app, "gate-ax3-2")
        field.typeText("\n") // «continue» on the keyboard sends the code
        waitFor(app, "sign-in-code")
        let code = element(app, "sign-in-code")
        XCTAssertEqual(code.label, "6-digit code", "the code field is one element with a clear label")
        XCTAssertGreaterThanOrEqual(code.frame.height, 43.5)
        shot(app, "gate-ax3-code")
        app.swipeUp()
        assertTapTarget(app, "sign-in-change")
        assertTapTarget(app, "sign-in-resend")
    }

    func testSignInGateNormalSize() {
        let app = launch(signedIn: false, large: false)
        openMuseum(app)
        element(app, "place-card").swipeUp()
        element(app, "place-tab-reviews").tap()
        waitFor(app, "place-write-review")
        element(app, "place-write-review").tap()
        waitFor(app, "account-gate")
        shot(app, "gate-normal")
    }

    // MARK: - Favorites

    func testFavoritesListAtLargestText() {
        let app = launch()
        openMuseum(app)
        element(app, "place-favorite").tap()
        let on = NSPredicate(format: "isSelected == true")
        XCTAssertEqual(XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: on,
                                                                          object: element(app, "place-favorite"))],
                                        timeout: 5), .completed)
        element(app, "place-card").swipeDown()
        app.buttons["open-sidebar"].tap()
        let entry = app.buttons["sidebar-favorites"]
        XCTAssertTrue(entry.waitForExistence(timeout: 5))
        entry.tap()
        let row = app.buttons["favorite-row"].firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertGreaterThanOrEqual(row.frame.height, 43.5)
        shot(app, "favorites-ax3")
    }
}
