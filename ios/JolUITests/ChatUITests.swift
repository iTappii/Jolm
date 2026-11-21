import XCTest

/// Ш-32. The chat on RECORDED SSE streams (`Resources/Fixtures/chat-*.sse`, replayed through the stub URLProtocol
/// by `-JolStubAPI`, one event every 120 ms): text streaming, the graph growing and converging, places on the map,
/// `chat_busy`, stream errors, reopening a chat, the weather proposal.
///
/// The map layer is not introspectable through accessibility, so pins are checked through the 1-pt marker
/// `chat-map-places`, whose value is the number of chat places handed to the map layer (the layer itself is
/// verified by hand, see docs/reviews/Ш-32.md).
@MainActor
final class ChatUITests: XCTestCase {
    private func launch(signedIn: Bool = true, language: String = "en") -> XCUIApplication {
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

    private func send(_ app: XCUIApplication, _ text: String) {
        let input = element(app, "chat-input")
        XCTAssertTrue(input.waitForExistence(timeout: 10))
        input.tap()
        input.typeText(text)
        element(app, "chat-send").tap()
    }

    private func waitFor(_ app: XCUIApplication, _ identifier: String, timeout: TimeInterval = 15,
                         file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(element(app, identifier).waitForExistence(timeout: timeout),
                      "\(identifier) never appeared", file: file, line: line)
    }

    private func waitForValue(_ element: XCUIElement, _ value: String, timeout: TimeInterval = 10,
                              file: StaticString = #filePath, line: UInt = #line) {
        let predicate = NSPredicate(format: "value == %@", value)
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: timeout), .completed,
                       "value is \(String(describing: element.value)), expected \(value)", file: file, line: line)
    }

    private func waitForLabel(_ element: XCUIElement, contains text: String, timeout: TimeInterval = 15,
                              file: StaticString = #filePath, line: UInt = #line) {
        let predicate = NSPredicate(format: "label CONTAINS %@", text)
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: timeout), .completed,
                       "label is \(element.label)", file: file, line: line)
    }

    private func waitForDisappearance(_ element: XCUIElement, timeout: TimeInterval = 15) {
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: timeout), .completed)
    }

    private func capture(_ name: String) {
        let screenshot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        screenshot.name = name
        screenshot.lifetime = .keepAlways
        add(screenshot)
    }

    // MARK: - Registered chat on the recorded trip stream

    func testTripStreamGrowsTheGraphConvergesAndPutsPlacesOnTheMap() {
        let app = launch()
        XCTAssertEqual(element(app, "chat-map-places").value as? String, "0")
        send(app, "Plan 3 days in Almaty")

        // Text streams into one assistant bubble under the user's message.
        waitFor(app, "chat-message-user")
        XCTAssertEqual(element(app, "chat-message-user").label, "Plan 3 days in Almaty")

        // The graph grows node by node and, while it is still growing, has no final node.
        waitFor(app, "graph-node-1")
        XCTAssertFalse(element(app, "graph-final").exists, "the graph converges only on route_ready")
        capture("chat-graph-growing")
        waitFor(app, "graph-node-3")
        waitFor(app, "graph-final")
        XCTAssertEqual(element(app, "graph-node-1").label, "3 days, Dec 5-7")
        XCTAssertEqual(element(app, "graph-node-2").label, "Budget 900 000 tenge")
        XCTAssertEqual(element(app, "graph-node-3").label, "Wants museums")

        let answer = element(app, "chat-message-assistant")
        waitForLabel(answer, contains: "Your route is ready.")
        capture("chat-route-ready")
        XCTAssertEqual(
            answer.label,
            "Three days in Almaty, sounds great. I put the museum on your map. Your route is ready."
        )

        // The brief chips, the places behind the chat and the offer to open the full map.
        waitFor(app, "brief-budget")
        XCTAssertTrue(element(app, "brief-budget").label.contains("900"), element(app, "brief-budget").label)
        XCTAssertTrue(element(app, "brief-dates").label.contains("Dec"), element(app, "brief-dates").label)
        XCTAssertTrue(element(app, "brief-lodging").exists)
        waitForValue(element(app, "chat-map-places"), "2")
        waitFor(app, "chat-route-card")
        XCTAssertTrue(app.buttons["chat-open-route"].exists)
        XCTAssertFalse(element(app, "chat-error").exists)

        // «Open full map»: the full route map with the first day's stops (Ш-37; details in TripMapUITests).
        app.buttons["chat-open-route"].tap()
        waitFor(app, "trip-map")
        waitFor(app, "trip-stop-1")
        XCTAssertTrue(app.staticTexts["Fixture Museum"].exists)
        app.buttons["trip-map-close"].tap()
        waitForDisappearance(element(app, "trip-map"))
    }

    func testCollapsingKeepsTheStreamRunningAndShowsTypingInTheBar() {
        let app = launch()
        send(app, "Plan 3 days in Almaty")
        waitFor(app, "graph-node-1")
        app.buttons["chat-collapse"].tap()
        XCTAssertTrue(app.buttons["chat-collapsed-bar"].waitForExistence(timeout: 5))
        waitFor(app, "chat-collapsed-typing", timeout: 5)

        // The stream finishes while collapsed; the typing indicator goes and the pins stay.
        waitForDisappearance(element(app, "chat-collapsed-typing"))
        waitForValue(element(app, "chat-map-places"), "2")
        capture("chat-map-places")
        app.buttons["chat-collapsed-bar"].tap()
        waitFor(app, "graph-final", timeout: 5)
        XCTAssertTrue(element(app, "chat-route-card").exists)
    }

    func testChatBusyIsShownInlineAndRetryContinues() {
        let app = launch()
        send(app, "busy: plan 3 days")
        waitFor(app, "chat-error")
        XCTAssertTrue(element(app, "chat-error").label.contains("still answering"), element(app, "chat-error").label)
        XCTAssertTrue(app.buttons["chat-retry"].exists)
        XCTAssertFalse(element(app, "graph-node-1").exists)

        app.buttons["chat-retry"].tap()
        waitFor(app, "graph-final")
        XCTAssertFalse(element(app, "chat-error").exists)
        XCTAssertEqual(app.descendants(matching: .any).matching(identifier: "chat-message-user").count, 1,
                       "retry does not add a second bubble")
    }

    func testStreamErrorShowsPartialTextAndInlineErrorWithRetry() {
        let app = launch()
        send(app, "boom, plan 3 days")
        waitFor(app, "chat-error")
        XCTAssertTrue(element(app, "chat-error").label.contains("unavailable"), element(app, "chat-error").label)
        XCTAssertEqual(element(app, "chat-message-assistant").label, "Let me think")

        app.buttons["chat-retry"].tap()
        waitFor(app, "graph-final")
        XCTAssertFalse(element(app, "chat-error").exists)
        XCTAssertFalse(app.staticTexts["Let me think"].exists, "the failed half answer is replaced")
    }

    func testFullChatOffersOnlyANewChat() {
        let app = launch()
        send(app, "full of ideas")
        waitFor(app, "chat-error")
        XCTAssertTrue(element(app, "chat-error").label.contains("full"))
        XCTAssertFalse(app.buttons["chat-retry"].exists)
        app.buttons["chat-full-new"].tap()
        waitFor(app, "chat-greeting", timeout: 5)
        XCTAssertFalse(element(app, "chat-error").exists)
    }

    // MARK: - Side panel, reopening, proposals

    func testRecentChatReopensWithGraphPinsAndTheProposalCanBeAccepted() {
        let app = launch()
        app.buttons["open-sidebar"].tap()
        waitFor(app, "sidebar-chats")
        let row = app.buttons.matching(identifier: "sidebar-chat-row").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        XCTAssertTrue(row.label.contains("Weather change"), row.label)
        row.tap()

        // Messages, the rebuilt graph (converged: the chat has a trip) and the pins restored from the trip.
        waitFor(app, "chat-transcript")
        waitFor(app, "graph-final")
        XCTAssertEqual(element(app, "graph-node-1").label, "3 days, Dec 5-7")
        XCTAssertEqual(element(app, "graph-node-2").label, "Budget 900 000 tenge")
        waitForValue(element(app, "chat-map-places"), "2")
        XCTAssertTrue(app.staticTexts["Rain is forecast on Dec 6. Move the museum to Dec 7?"].exists)
        XCTAssertTrue(app.buttons["proposal-accept"].exists)
        XCTAssertTrue(app.buttons["proposal-decline"].exists)

        let proposal = app.buttons["proposal-accept"]
        if !proposal.isHittable { element(app, "chat-transcript").swipeDown() }
        capture("chat-weather-proposal")
        app.buttons["proposal-accept"].tap()
        waitFor(app, "proposal-status")
        XCTAssertEqual(element(app, "proposal-status").label, "Accepted")
        XCTAssertFalse(app.buttons["proposal-accept"].exists)
        // The chat was reloaded: the assistant's follow-up is there.
        XCTAssertTrue(app.staticTexts["Done: the museum is now on Dec 7."].waitForExistence(timeout: 5))
    }

    func testDecliningAProposalRemovesTheButtons() {
        let app = launch()
        app.buttons["open-sidebar"].tap()
        let row = app.buttons.matching(identifier: "sidebar-chat-row").firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        waitFor(app, "proposal-decline")
        app.buttons["proposal-decline"].tap()
        waitFor(app, "proposal-status")
        XCTAssertEqual(element(app, "proposal-status").label, "Declined")
    }

    // MARK: - Guest

    /// Opt in with TEST_RUNNER_JOL_LIVE_CHAT=1 and a local dev API using its default fake provider.
    func testGuestReceivesAnAnswerFromTheLocalAPI() throws {
        guard ProcessInfo.processInfo.environment["JOL_LIVE_CHAT"] == "1" else {
            throw XCTSkip("Requires a local API with the fake LLM provider")
        }
        let app = XCUIApplication()
        app.launchArguments = ["-JolLiveGuest", "-AppleLanguages", "(en)", "-AppleLocale", "en_US"]
        app.launch()
        send(app, "What can I visit in Almaty?")
        waitForLabel(element(app, "chat-message-assistant"), contains: "This is the fake LLM.")
        waitFor(app, "chat-guest-signin")
        capture("chat-live-local-api")
    }

    func testGuestChatsWithoutAnAccountAndIsOfferedSignInForAPersonalRoute() {
        let app = launch(signedIn: false)
        send(app, "Where is the museum?")
        XCTAssertFalse(element(app, "account-gate").exists, "a simple question needs no account")
        waitFor(app, "chat-message-assistant")
        waitForLabel(element(app, "chat-message-assistant"), contains: "in the centre.")
        waitForValue(element(app, "chat-map-places"), "1")
        XCTAssertFalse(element(app, "graph-node-1").exists, "the guest chat has no graph")

        waitFor(app, "chat-guest-signin")
        app.buttons["chat-guest-signin"].tap()
        waitFor(app, "account-gate", timeout: 5)
    }

    func testRussianInterface() {
        let app = launch(language: "ru")
        send(app, "Составь маршрут на 3 дня")
        waitFor(app, "graph-final")
        XCTAssertEqual(element(app, "graph-final").label, "Маршрут готов")
        XCTAssertEqual(app.buttons["chat-open-route"].label, "Открыть полную карту")
        XCTAssertTrue(app.staticTexts["3 дня"].exists)
    }
}
