import XCTest

/// Ш-23b (iOS part). Stub API with an in-memory favorites list (`-JolStubSignedIn` = a signed-in stub user).
@MainActor
final class FavoritesUITests: XCTestCase {
    private func launch(signedIn: Bool) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "-jol.language", "system"] + (signedIn ? ["-JolStubSignedIn"] : [])
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func openCard(_ app: XCUIApplication) {
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
    }

    func testSignedInUserTogglesFavoriteAndSeesItInSidebarList() {
        let app = launch(signedIn: true)
        openCard(app)
        let heart = element(app, "place-favorite")
        XCTAssertTrue(heart.waitForExistence(timeout: 5))
        XCTAssertFalse(heart.isSelected)
        heart.tap()
        let on = NSPredicate(format: "isSelected == true")
        XCTAssertEqual(XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: on, object: heart)], timeout: 5),
                       .completed, "filled heart")
        XCTAssertEqual(heart.label, "In favorites")

        // Close the card, open the list from the side panel, tap the row → the card opens again.
        element(app, "place-card").swipeDown()
        app.buttons["open-sidebar"].tap()
        let entry = app.buttons["sidebar-favorites"]
        XCTAssertTrue(entry.waitForExistence(timeout: 5))
        entry.tap()
        let row = app.buttons["favorite-row"].firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertTrue(app.staticTexts["Fixture Museum"].exists)
        row.tap()
        XCTAssertTrue(element(app, "place-card").waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["place-name"].label, "Fixture Museum")

        // Toggle off.
        let heartAgain = element(app, "place-favorite")
        XCTAssertTrue(heartAgain.waitForExistence(timeout: 5))
        XCTAssertTrue(heartAgain.isSelected, "state was loaded from the server")
        heartAgain.tap()
        let off = NSPredicate(format: "isSelected == false")
        XCTAssertEqual(XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: off, object: heartAgain)],
                                        timeout: 5), .completed)
    }

    func testGuestIsAskedToSignInAndThePlaceIsAddedAfterwards() {
        let app = launch(signedIn: false)
        openCard(app)
        element(app, "place-favorite").tap()
        XCTAssertTrue(element(app, "account-gate").waitForExistence(timeout: 5), app.debugDescription)

        let field = element(app, "sign-in-destination")
        XCTAssertTrue(field.waitForExistence(timeout: 5))
        field.tap()
        field.typeText("tourist@example.com")
        element(app, "sign-in-send").tap()
        let code = element(app, "sign-in-code")
        XCTAssertTrue(code.waitForExistence(timeout: 5))
        code.typeText("123456")

        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, "account-gate"))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 10), .completed)
        let heart = element(app, "place-favorite")
        let on = NSPredicate(format: "isSelected == true")
        XCTAssertEqual(XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: on, object: heart)], timeout: 10),
                       .completed, "added after sign-in")
    }
}
