import XCTest

/// Ш-43 (SSOT §11.4). The side panel on the stubbed API (`-JolStubAPI`): trips, recent chats, "New chat", reopening a
/// saved chat and what a guest sees (a guest chat has no history, SSOT §3.1).
@MainActor
final class SidebarUITests: XCTestCase {
    private func launch(signedIn: Bool, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        var arguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))", "-AppleLocale",
                         language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if signedIn { arguments.append("-JolStubSignedIn") }
        app.launchArguments = arguments
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func openSidebar(_ app: XCUIApplication) {
        let open = app.buttons["open-sidebar"]
        XCTAssertTrue(open.waitForExistence(timeout: 10))
        open.tap()
        XCTAssertTrue(element(app, "sidebar-panel").waitForExistence(timeout: 5))
    }

    func testSignedInPanelListsTripsChatsAndNewChat() {
        let app = launch(signedIn: true)
        openSidebar(app)
        XCTAssertTrue(app.staticTexts["Recent chats"].exists)
        XCTAssertTrue(app.buttons["sidebar-new-chat"].exists)
        XCTAssertTrue(element(app, "sidebar-trips").waitForExistence(timeout: 10), "my trips")
        XCTAssertTrue(app.staticTexts["My trips"].exists)
        XCTAssertTrue(app.buttons.matching(identifier: "sidebar-trip-row").firstMatch.exists)
        let chat = app.buttons.matching(identifier: "sidebar-chat-row").firstMatch
        XCTAssertTrue(chat.waitForExistence(timeout: 10), "recent chats")
        XCTAssertTrue(chat.label.contains("Weather change"), chat.label)
        XCTAssertFalse(element(app, "sidebar-guest-hint").exists)
    }

    func testReopenedChatIsReadableAndNewChatStartsFresh() {
        let app = launch(signedIn: true)
        openSidebar(app)
        let row = app.buttons.matching(identifier: "sidebar-chat-row").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(element(app, "sidebar-panel").waitForNonExistence(timeout: 5), "the panel closes")
        XCTAssertTrue(element(app, "chat-transcript").waitForExistence(timeout: 15), "the chat is shown for rereading")
        XCTAssertTrue(app.staticTexts["Jol: Rain is forecast on Dec 6. Move the museum to Dec 7?"].exists)

        openSidebar(app)
        app.buttons["sidebar-new-chat"].tap()
        XCTAssertTrue(app.staticTexts["chat-greeting"].waitForExistence(timeout: 5), "new chat: the greeting again")
        XCTAssertFalse(element(app, "chat-transcript").exists)
    }

    func testTripRowOpensTheFullMap() {
        let app = launch(signedIn: true)
        openSidebar(app)
        let row = app.buttons.matching(identifier: "sidebar-trip-row").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(element(app, "trip-map").waitForExistence(timeout: 15))
    }

    func testGuestSeesNoHistoryOnlyAHintAndCanStartANewChat() {
        let app = launch(signedIn: false)
        openSidebar(app)
        XCTAssertTrue(element(app, "sidebar-guest-hint").exists)
        XCTAssertFalse(app.buttons["sidebar-chat-row"].exists)
        XCTAssertFalse(element(app, "sidebar-trips").exists)
        app.buttons["sidebar-new-chat"].tap()
        XCTAssertTrue(app.staticTexts["chat-greeting"].waitForExistence(timeout: 5))
    }

    func testGuestHintOpensTheSignInGate() {
        let app = launch(signedIn: false)
        openSidebar(app)
        let hint = app.buttons["sidebar-guest-hint"]
        XCTAssertTrue(hint.waitForExistence(timeout: 5))
        hint.tap()
        XCTAssertTrue(element(app, "account-gate").waitForExistence(timeout: 5), app.debugDescription)
    }

    func testPanelIsLocalizedInRussian() {
        let app = launch(signedIn: false, language: "ru")
        openSidebar(app)
        XCTAssertTrue(app.staticTexts["Недавние чаты"].exists)
        XCTAssertTrue(app.buttons["sidebar-new-chat"].label.contains("Новый чат"))
        XCTAssertEqual(app.buttons["sidebar-guest-hint"].label, "Войдите, чтобы сохранять чаты и поездки.")
    }
}
