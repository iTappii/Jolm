import XCTest

@MainActor
final class HomeScreenUITests: XCTestCase {
    private func launch(signedIn: Bool = false, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        var arguments = ["-AppleLanguages", "(\(language))", "-AppleLocale", language == "ru" ? "ru_RU" : "en_US",
                         "-jol.language", "system"]
        if signedIn { arguments.append("-JolFakeSignedIn") }
        app.launchArguments = arguments
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
        XCTAssertTrue(element(app, "profile-menu").waitForExistence(timeout: 5))
    }

    func testChatCollapsesAndExpands() {
        let app = launch()
        XCTAssertTrue(element(app, "chat-panel").waitForExistence(timeout: 10))
        XCTAssertTrue(app.staticTexts["chat-greeting"].exists)
        XCTAssertEqual(app.staticTexts["chat-greeting"].label, "Shall we start the journey?")
        XCTAssertTrue(app.textFields["chat-input"].exists)
        XCTAssertFalse(app.buttons["chat-collapsed-bar"].exists)

        let input = app.textFields["chat-input"]
        input.tap()
        input.typeText("Almaty")

        app.buttons["chat-collapse"].tap()
        let bar = app.buttons["chat-collapsed-bar"]
        XCTAssertTrue(bar.waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["osm-attribution"].exists, "map stays fully visible")
        XCTAssertFalse(element(app, "chat-panel").exists)

        bar.tap()
        XCTAssertTrue(element(app, "chat-panel").waitForExistence(timeout: 5))
        XCTAssertEqual(app.textFields["chat-input"].value as? String, "Almaty", "draft survives collapse")
    }

    func testSidebarOpensByButtonAndClosesOutside() {
        let app = launch()
        app.buttons["open-sidebar"].tap()
        XCTAssertTrue(element(app, "sidebar-panel").waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Recent chats"].exists)
        XCTAssertTrue(app.buttons["sidebar-new-chat"].exists)
        XCTAssertTrue(element(app, "sidebar-empty").exists)

        element(app, "sidebar-scrim").coordinate(withNormalizedOffset: CGVector(dx: 0.95, dy: 0.5)).tap()
        XCTAssertTrue(waitForDisappearance(element(app, "sidebar-panel")))
    }

    func testSidebarOpensByEdgeSwipeAndNewChatFocusesChat() {
        let app = launch()
        XCTAssertTrue(element(app, "chat-panel").waitForExistence(timeout: 10))
        app.buttons["chat-collapse"].tap()
        XCTAssertTrue(app.buttons["chat-collapsed-bar"].waitForExistence(timeout: 5))

        let start = app.coordinate(withNormalizedOffset: CGVector(dx: 0, dy: 0.5)).withOffset(CGVector(dx: 2, dy: 0))
        let end = app.coordinate(withNormalizedOffset: CGVector(dx: 0.6, dy: 0.5))
        start.press(forDuration: 0.05, thenDragTo: end)
        XCTAssertTrue(element(app, "sidebar-panel").waitForExistence(timeout: 5), "edge swipe opens the panel")

        app.buttons["sidebar-new-chat"].tap()
        XCTAssertTrue(waitForDisappearance(element(app, "sidebar-panel")))
        XCTAssertTrue(element(app, "chat-panel").waitForExistence(timeout: 5), "new chat expands the chat")
    }

    func testProfileMenuItemsOpenForGuest() {
        let app = launch()
        openProfile(app)
        XCTAssertFalse(app.buttons["profile-sign-out"].exists)
        XCTAssertFalse(app.buttons["profile-delete-account"].exists)

        for (row, screen) in [("profile-settings", "settings-screen"), ("profile-help", "help-screen"),
                              ("profile-about", "about-screen")] {
            app.buttons[row].tap()
            XCTAssertTrue(element(app, screen).waitForExistence(timeout: 5), "\(row) opens")
            if screen == "about-screen" {
                XCTAssertTrue(app.staticTexts["© OpenStreetMap contributors"].exists)
                XCTAssertTrue(element(app, "about-version").exists)
            }
            app.navigationBars.buttons.firstMatch.tap()
        }

        app.buttons["profile-language"].tap()
        XCTAssertTrue(app.buttons["language-ru"].waitForExistence(timeout: 5), app.debugDescription)
        app.navigationBars.buttons.firstMatch.tap()

        app.buttons["profile-sign-in"].tap()
        XCTAssertTrue(element(app, "sign-in-entry").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "sign-in-channel").exists)
        XCTAssertTrue(element(app, "sign-in-send").exists)
    }

    func testLanguageSwitchAppliesWithoutRestart() {
        let app = launch()
        openProfile(app)
        app.buttons["profile-language"].tap()
        app.buttons["language-ru"].tap()
        XCTAssertTrue(app.buttons["Системный"].waitForExistence(timeout: 5), "language screen is Russian at once")
        app.navigationBars.buttons.firstMatch.tap()
        XCTAssertTrue(app.buttons["profile-settings"].staticTexts["Настройки"].waitForExistence(timeout: 5))

        app.buttons["profile-done"].tap()
        XCTAssertTrue(waitForDisappearance(element(app, "profile-menu")))
        XCTAssertEqual(app.staticTexts["chat-greeting"].label, "Начнём путешествие?", "main screen switched too")

        openProfile(app)
        app.buttons["profile-language"].tap()
        app.buttons["language-en"].tap()
        XCTAssertTrue(app.buttons["System"].waitForExistence(timeout: 5), "back to English at once")
    }

    func testSignedInMenuShowsAccountRowsAndSignOut() {
        let app = launch(signedIn: true)
        openProfile(app)
        XCTAssertTrue(element(app, "profile-identity").exists)
        XCTAssertFalse(app.buttons["profile-sign-in"].exists)
        XCTAssertTrue(app.buttons["profile-delete-account"].exists)

        app.buttons["profile-delete-account"].tap()
        let confirm = app.buttons["delete-confirm"]
        XCTAssertTrue(confirm.waitForExistence(timeout: 5), "confirmation dialog appears")
        XCTAssertTrue(app.staticTexts["Your account and its data will be permanently deleted. This cannot be undone."]
            .exists)
        // On this iOS the dialog is anchored to the row and has no Cancel button: tap outside to dismiss.
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.1, dy: 0.1)).tap()
        XCTAssertTrue(waitForDisappearance(confirm), "dialog dismissed")
        XCTAssertTrue(app.buttons["profile-sign-out"].waitForExistence(timeout: 5), "cancel leaves the menu as is")

        app.buttons["profile-sign-out"].tap()
        XCTAssertTrue(waitForDisappearance(element(app, "profile-menu")), "sheet closes after sign out")
        openProfile(app)
        XCTAssertTrue(app.buttons["profile-sign-in"].waitForExistence(timeout: 5), "now a guest")
    }

    private func waitForDisappearance(_ element: XCUIElement, timeout: TimeInterval = 5) -> Bool {
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)
        return XCTWaiter().wait(for: [gone], timeout: timeout) == .completed
    }
}
