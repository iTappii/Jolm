import XCTest

/// Ш-46: the bonus account in the profile menu, on the stub API. A guest has no bonus row.
@MainActor
final class BonusUITests: XCTestCase {
    private func launch(signedIn: Bool = true, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
            + (signedIn ? ["-JolStubSignedIn"] : [])
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func openProfile(_ app: XCUIApplication) {
        let profile = app.buttons["open-profile-menu"]
        XCTAssertTrue(profile.waitForExistence(timeout: 10))
        profile.tap()
        XCTAssertTrue(element(app, "profile-menu").waitForExistence(timeout: 10))
    }

    func testBalanceAndHistory() {
        let app = launch()
        openProfile(app)
        let row = element(app, "profile-bonuses")
        XCTAssertTrue(row.waitForExistence(timeout: 10), app.debugDescription)
        let balance = element(app, "profile-bonus-balance")
        XCTAssertTrue(balance.waitForExistence(timeout: 10), "the menu row shows the balance")
        XCTAssertEqual(balance.label, "240")
        row.tap()

        XCTAssertTrue(element(app, "bonus-screen").waitForExistence(timeout: 10))
        XCTAssertEqual(element(app, "bonus-balance").label, "240")
        XCTAssertEqual(element(app, "bonus-rate").label, "1 bonus ≈ 1 ₸")
        XCTAssertTrue(element(app, "bonus-spending-soon").exists, "spending is announced as coming soon")
        let rows = app.descendants(matching: .any).matching(identifier: "bonus-row")
        XCTAssertTrue(rows.firstMatch.waitForExistence(timeout: 10))
        XCTAssertEqual(rows.count, 2)
        let (menu, review) = (rows.element(boundBy: 0).label, rows.element(boundBy: 1).label)
        XCTAssertTrue(menu.contains("Menu") && menu.contains("+188"), menu)
        XCTAssertTrue(review.contains("Review") && review.contains("+52"), review)
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = "bonus-screen"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func testRussianStrings() {
        let app = launch(language: "ru")
        openProfile(app)
        element(app, "profile-bonuses").tap()
        XCTAssertTrue(element(app, "bonus-screen").waitForExistence(timeout: 10))
        XCTAssertEqual(element(app, "bonus-rate").label, "1 бонус ≈ 1 ₸")
        XCTAssertEqual(element(app, "bonus-spending-soon").label, "Траты бонусов: скоро")
        XCTAssertTrue(element(app, "bonus-row").waitForExistence(timeout: 10))
        XCTAssertTrue(element(app, "bonus-row").label.contains("Меню"), element(app, "bonus-row").label)
    }

    func testAGuestHasNoBonusRow() {
        let app = launch(signedIn: false)
        openProfile(app)
        XCTAssertTrue(element(app, "profile-sign-in").waitForExistence(timeout: 10))
        XCTAssertFalse(element(app, "profile-bonuses").exists)
    }
}
