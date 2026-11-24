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
        XCTAssertEqual(element(app, "chat-message-user").label, "You: Plan 3 days in Almaty")

        // The chain (see ChatChainUITests) grows node by node; no finish node until the route is ready.
        waitFor(app, "graph-node-1")
        XCTAssertFalse(element(app, "graph-chain-finish").exists, "the finish node comes only with route_ready")
        capture("chat-graph-growing")
        waitFor(app, "graph-node-4")
        waitFor(app, "graph-chain-finish")
        // The nodes are the answers (the brief), in the order they were given — not the AI's theses.
        XCTAssertTrue(
            element(app, "graph-node-1").label.hasPrefix("Step 1: 3 days"), element(app, "graph-node-1").label)
        XCTAssertTrue(element(app, "graph-node-2").label.contains("900"), element(app, "graph-node-2").label)
        XCTAssertEqual(element(app, "graph-node-3").label, "Step 3: Have accommodation")
        XCTAssertEqual(element(app, "graph-node-4").label, "Step 4: Fixture Museum")

        let answer = element(app, "chat-message-assistant")
        waitForLabel(answer, contains: "Your route is ready.")
        capture("chat-route-ready")
        XCTAssertEqual(
            answer.label,
            "Jol: Three days in Almaty, sounds great. I put the museum on your map. Your route is ready."
        )

        // The finish node of the chain, the places behind the chat and the offer to open the full map.
        waitFor(app, "graph-chain-finish")
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

    /// The cursor stays in the field after sending (owner, 2026-11-22): the next wish is typed without a tap, both
    /// after the send button and after the keyboard's return key.
    func testInputKeepsFocusAfterSending() {
        let app = launch()
        let input = element(app, "chat-input")
        send(app, "live1 Chinese restaurant")
        waitFor(app, "chat-message-user")
        XCTAssertTrue(waitForFocus(input), "the field keeps the keyboard after the send button")
        // A new message is accepted once the answer has finished streaming (the send button turns on then).
        input.typeText("live2 First President park")
        let ready = XCTNSPredicateExpectation(predicate: NSPredicate(format: "isEnabled == true"),
                                              object: element(app, "chat-send"))
        XCTAssertEqual(XCTWaiter().wait(for: [ready], timeout: 15), .completed, "the answer finished")
        input.typeText("\n")
        let users = app.descendants(matching: .any).matching(identifier: "chat-message-user")
        XCTAssertTrue(users.element(boundBy: 1).waitForExistence(timeout: 15), "sent with return, no tap")
        XCTAssertEqual(
            users.element(boundBy: 1).label, "You: live2 First President park", "no new line left in the text")
        XCTAssertTrue(waitForFocus(input), "the field keeps the keyboard after the return key")
    }

    private func waitForFocus(_ input: XCUIElement, timeout: TimeInterval = 5) -> Bool {
        let focused = XCTNSPredicateExpectation(predicate: NSPredicate(format: "hasKeyboardFocus == true"),
                                                object: input)
        return XCTWaiter().wait(for: [focused], timeout: timeout) == .completed
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
        waitFor(app, "graph-chain-finish", timeout: 5)
        XCTAssertTrue(element(app, "chat-route-card").exists)
    }

    func testDailyAILimitShowsMessageWithoutRetryAndInputStaysUsable() {
        let app = launch()
        send(app, "budget please")
        waitFor(app, "chat-error")
        XCTAssertTrue(element(app, "chat-error").label.contains("today's AI message limit"),
                      element(app, "chat-error").label)
        XCTAssertFalse(app.buttons["chat-retry"].exists)
        XCTAssertFalse(app.buttons["chat-full-new"].exists)
        let input = element(app, "chat-input")
        XCTAssertTrue(input.isHittable)
        input.tap()
        input.typeText("hello again")
        XCTAssertTrue(element(app, "chat-send").isEnabled)
    }

    func testChatBusyIsShownInlineAndRetryContinues() {
        let app = launch()
        send(app, "busy: plan 3 days")
        waitFor(app, "chat-error")
        XCTAssertTrue(element(app, "chat-error").label.contains("still answering"), element(app, "chat-error").label)
        XCTAssertTrue(app.buttons["chat-retry"].exists)
        XCTAssertFalse(element(app, "graph-node-1").exists)

        app.buttons["chat-retry"].tap()
        waitFor(app, "graph-chain-finish")
        XCTAssertFalse(element(app, "chat-error").exists)
        XCTAssertEqual(app.descendants(matching: .any).matching(identifier: "chat-message-user").count, 1,
                       "retry does not add a second bubble")
    }

    func testStreamErrorShowsPartialTextAndInlineErrorWithRetry() {
        let app = launch()
        send(app, "boom, plan 3 days")
        waitFor(app, "chat-error")
        XCTAssertTrue(element(app, "chat-error").label.contains("unavailable"), element(app, "chat-error").label)
        XCTAssertEqual(element(app, "chat-message-assistant").label, "Jol: Let me think")

        app.buttons["chat-retry"].tap()
        waitFor(app, "graph-chain-finish")
        XCTAssertFalse(element(app, "chat-error").exists)
        XCTAssertFalse(app.staticTexts["Jol: Let me think"].exists, "the failed half answer is replaced")
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
        waitFor(app, "graph-chain-finish")
        XCTAssertTrue(
            element(app, "graph-node-1").label.hasPrefix("Step 1: 3 days"), element(app, "graph-node-1").label)
        XCTAssertTrue(element(app, "graph-node-2").label.contains("900"), element(app, "graph-node-2").label)
        XCTAssertEqual(element(app, "graph-node-4").label, "Step 4: Fixture Museum", "restored from filled_order")
        waitForValue(element(app, "chat-map-places"), "2")
        XCTAssertTrue(app.staticTexts["Jol: Rain is forecast on Dec 6. Move the museum to Dec 7?"].exists)
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
        XCTAssertTrue(app.staticTexts["Jol: Done: the museum is now on Dec 7."].waitForExistence(timeout: 5))
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
        waitFor(app, "graph-chain-finish")
        XCTAssertEqual(element(app, "graph-chain-finish").label, "Маршрут готов")
        XCTAssertEqual(app.buttons["chat-open-route"].label, "Открыть полную карту")
        XCTAssertTrue(app.staticTexts["3 дня"].exists)
    }
}
