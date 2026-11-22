import XCTest

/// Ш-18 / Ш-19. The API is stubbed (`-JolStubAPI`: fixtures in the app, offline stub style), so no server is needed.
@MainActor
final class PlacesUITests: XCTestCase {
    private func launch(language: String = "en", dark: Bool = false) -> XCUIApplication {
        // The app has no theme override: the dark theme is the device's (a launch argument is ignored).
        XCUIDevice.shared.appearance = dark ? .dark : .light
        addTeardownBlock { XCUIDevice.shared.appearance = .light }
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))",
                               "-AppleLocale", language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func collapseChat(_ app: XCUIApplication) {
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        XCTAssertTrue(app.buttons["chat-collapsed-bar"].waitForExistence(timeout: 5))
    }

    /// The fixture museum sits exactly at the initial map center; pins load asynchronously, so tap until it opens.
    private func tapCenterPin(_ app: XCUIApplication) {
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
    }

    func testTapPinOpensMiniCardThenFullCard() {
        let app = launch()
        collapseChat(app)
        tapCenterPin(app)

        XCTAssertEqual(app.staticTexts["place-name"].label, "Fixture Museum")
        XCTAssertTrue(element(app, "place-open-now").waitForExistence(timeout: 5))
        XCTAssertEqual(element(app, "place-open-now").label, "Open now")
        XCTAssertTrue(app.staticTexts["Entry ≈ 1\u{00A0}500\u{00A0}₸"].exists || app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS %@", "1\u{00A0}500")).firstMatch.exists, "approximate price")
        XCTAssertTrue(element(app, "place-hours-today").exists)
        XCTAssertTrue(element(app, "place-directions").isHittable)
        XCTAssertTrue(element(app, "place-navigator").exists)
        XCTAssertFalse(element(app, "place-book").isEnabled, "the museum has no booking partner (`booking: null`)")
        XCTAssertTrue(element(app, "place-gallery").exists)
        XCTAssertTrue(element(app, "place-address").waitForExistence(timeout: 5), "address under the name")
        XCTAssertTrue(element(app, "place-favorite").isHittable, "pinned buttons stay visible")
        let screenshot = XCTAttachment(screenshot: app.screenshot())
        screenshot.name = "place-card"
        screenshot.lifetime = .keepAlways
        add(screenshot)

        // Drag the sheet up → everything fits.
        element(app, "place-card").swipeUp()
        XCTAssertTrue(element(app, "place-hours").waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["A fixture place used by UI tests."].exists)
        XCTAssertTrue(element(app, "place-directions").isHittable, "still pinned when expanded")
    }

    func testTabsOverviewReviewsPhotos() {
        let app = launch()
        collapseChat(app)
        tapCenterPin(app)
        XCTAssertTrue(element(app, "place-tab-overview").isSelected)
        XCTAssertTrue(element(app, "place-tab-content-overview").waitForExistence(timeout: 5))

        element(app, "place-tab-reviews").tap()
        XCTAssertTrue(element(app, "place-reviews-empty").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "place-tab-reviews").isSelected)

        element(app, "place-tab-photos").tap()
        XCTAssertTrue(element(app, "place-photos-empty").waitForExistence(timeout: 5))

        element(app, "place-tab-overview").tap()
        XCTAssertTrue(element(app, "place-open-now").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "place-directions").isHittable)
    }

    func testFavoritesButtonAsGuestOpensSignInGate() {
        let app = launch()
        collapseChat(app)
        tapCenterPin(app)
        element(app, "place-favorite").tap()
        XCTAssertTrue(element(app, "account-gate").waitForExistence(timeout: 5), app.debugDescription)
    }

    func testCardClosesBySwipingDown() {
        let app = launch()
        collapseChat(app)
        tapCenterPin(app)
        element(app, "place-card").swipeDown()
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, "place-card"))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 5), .completed)
    }

    func testCuratedRouteListOpensRouteAndStopOpensCard() {
        let app = launch()
        app.buttons["open-sidebar"].tap()
        let entry = app.buttons["sidebar-routes"]
        XCTAssertTrue(entry.waitForExistence(timeout: 5))
        entry.tap()

        let row = app.buttons["route-row"].firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertTrue(app.staticTexts["Fixture Route"].exists)
        XCTAssertTrue(app.staticTexts["2 places"].exists)
        row.tap()

        XCTAssertTrue(element(app, "route-bar").waitForExistence(timeout: 5))
        XCTAssertEqual(element(app, "route-title").label, "Fixture Route")
        let second = app.buttons["route-stop-2"]
        XCTAssertTrue(second.waitForExistence(timeout: 5))
        second.tap()
        XCTAssertTrue(element(app, "place-card").waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["place-name"].label, "Fixture Cafe")
    }

    func testCuratedRouteClosesAndRussianStrings() {
        let app = launch(language: "ru")
        app.buttons["open-sidebar"].tap()
        app.buttons["sidebar-routes"].tap()
        let row = app.buttons["route-row"].firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["Мест: 2"].exists)
        row.tap()
        XCTAssertTrue(element(app, "route-bar").waitForExistence(timeout: 5))
        app.buttons["route-close"].tap()
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, "route-bar"))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 5), .completed)
    }
}
