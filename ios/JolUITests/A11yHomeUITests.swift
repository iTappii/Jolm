import XCTest

/// Ш-52 (остаток): accessibility of the home screen and the chat — VoiceOver labels and values, the 44 pt targets,
/// the chain read as «Step N: value», the live route, the largest Dynamic Type (accessibility XXXL) and the dark theme,
/// on the stub API. The theme is forced with `-JolForceTheme` (the system appearance is shared with other sessions).
/// Screenshots go to the test report and, with `TEST_RUNNER_A11Y_SHOTS=<dir>`, to that folder.
@MainActor
final class A11yHomeUITests: XCTestCase {
    private static let xxxl = "UICTContentSizeCategoryAccessibilityXXXL"

    private func launch(dark: Bool = false, large: Bool = false, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-JolForceTheme", dark ? "dark" : "light",
                               "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if large { app.launchArguments += ["-UIPreferredContentSizeCategoryName", Self.xxxl] }
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

    private func waitForLabel(_ element: XCUIElement, _ label: String, timeout: TimeInterval = 15,
                              file: StaticString = #filePath, line: UInt = #line) {
        let expectation = XCTNSPredicateExpectation(predicate: NSPredicate(format: "label == %@", label),
                                                    object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: timeout), .completed,
                       "label is \(element.label), expected \(label)", file: file, line: line)
    }

    private func send(_ app: XCUIApplication, _ text: String) {
        let input = element(app, "chat-input")
        XCTAssertTrue(input.waitForExistence(timeout: 10))
        input.tap()
        input.typeText(text)
        element(app, "chat-send").tap()
    }

    /// One turn of the recorded dialog (`chat-dlg-N.sse`): the answer is written when the typing dots are gone.
    private func turn(_ app: XCUIApplication, _ number: Int, _ answer: String) {
        send(app, "#dlg\(number) \(answer)")
        sleep(1)
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, "chat-typing"))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 15), .completed)
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = ProcessInfo.processInfo.environment["A11Y_SHOTS"], !dir.isEmpty {
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
        }
    }

    /// A control a finger can hit: exists, on the screen, hittable, 44 × 44 pt (the floor is 43.5 for rounding).
    private func assertTarget(_ app: XCUIApplication, _ identifier: String,
                              file: StaticString = #filePath, line: UInt = #line) {
        let control = element(app, identifier)
        XCTAssertTrue(control.exists, "\(identifier) missing", file: file, line: line)
        XCTAssertTrue(control.isHittable, "\(identifier) not hittable", file: file, line: line)
        XCTAssertGreaterThanOrEqual(control.frame.height, 43.5, "\(identifier) height", file: file, line: line)
        XCTAssertGreaterThanOrEqual(control.frame.width, 43.5, "\(identifier) width", file: file, line: line)
        XCTAssertTrue(app.frame.contains(control.frame), "\(identifier) outside the screen", file: file, line: line)
    }

    /// The text field reports only its text line (22 pt) to XCUI; its row is 44 pt (`minHeight` + `contentShape`).
    private func assertField(_ app: XCUIApplication, file: StaticString = #filePath, line: UInt = #line) {
        let field = element(app, "chat-input")
        XCTAssertTrue(field.isHittable, "chat-input not hittable", file: file, line: line)
        XCTAssertTrue(app.frame.contains(field.frame), "chat-input outside the screen", file: file, line: line)
    }

    // MARK: - Home screen

    func testHomeControlsHaveLabelsHintsAndTargets() {
        let app = launch()
        waitFor(app, "chat-panel")
        XCTAssertEqual(element(app, "open-sidebar").label, "Recent chats")
        XCTAssertEqual(element(app, "open-profile-menu").label, "Profile")
        XCTAssertEqual(element(app, "chat-collapse").label, "Collapse chat")
        XCTAssertEqual(element(app, "chat-send").label, "Send")
        XCTAssertFalse(element(app, "chat-send").isEnabled, "nothing to send yet")
        XCTAssertEqual(element(app, "chat-greeting").label, "Shall we start the journey?")
        for id in ["open-sidebar", "open-profile-menu", "chat-collapse"] { assertTarget(app, id) }
        assertField(app)
        element(app, "chat-input").tap()
        element(app, "chat-input").typeText("hello")
        assertTarget(app, "chat-send")
        XCTAssertTrue(element(app, "chat-send").isEnabled)
        XCTAssertTrue(element(app, "osm-attribution").exists, "the attribution line stays")
        shot(app, "home-light")
    }

    func testCollapsedBarSpeaksTheDraftAndExpands() {
        let app = launch()
        element(app, "chat-collapse").tap()
        waitFor(app, "chat-collapsed-bar")
        let bar = element(app, "chat-collapsed-bar")
        XCTAssertEqual(bar.label, "Expand chat")
        XCTAssertGreaterThanOrEqual(bar.frame.height, 47.5)
        bar.tap()
        waitFor(app, "chat-input")
        element(app, "chat-input").tap()
        element(app, "chat-input").typeText("museum")
        element(app, "chat-collapse").tap()
        waitFor(app, "chat-collapsed-bar")
        XCTAssertEqual(element(app, "chat-collapsed-bar").value as? String, "museum", "the draft is the value")
    }

    func testHomeRussianLabels() {
        let app = launch(language: "ru")
        waitFor(app, "chat-panel")
        XCTAssertEqual(element(app, "chat-collapse").label, "Свернуть чат")
        XCTAssertEqual(element(app, "chat-send").label, "Отправить")
        XCTAssertEqual(element(app, "open-profile-menu").label, "Профиль")
    }

    // MARK: - Chain and messages

    func testChainReadsAsStepsAndMessagesNameTheSpeaker() {
        let app = launch()
        turn(app, 0, "plan a trip")
        turn(app, 1, "5 days")
        turn(app, 2, "200000")
        waitFor(app, "graph-node-2")
        let first = element(app, "graph-node-1").label
        XCTAssertTrue(first.hasPrefix("Step 1: 5 days"), first)
        waitForLabel(element(app, "graph-node-2"), "Step 2: 200,000 ₸")
        XCTAssertEqual(element(app, "chat-chain").label, "2 answers, route is not ready")
        XCTAssertEqual(element(app, "chat-chain").value as? String, "building")
        for id in ["graph-node-1", "graph-node-2"] { assertTarget(app, id) }

        element(app, "graph-node-2").tap()
        waitFor(app, "graph-node-detail")
        XCTAssertTrue(element(app, "graph-node-2").isSelected, "the tapped node is selected for VoiceOver")
        XCTAssertEqual(element(app, "graph-node-detail").label, "200,000 ₸")

        let userMessage = element(app, "chat-message-user")
        XCTAssertTrue(userMessage.label.hasPrefix("You: #dlg"), userMessage.label)
        XCTAssertTrue(element(app, "chat-message-assistant").label.hasPrefix("Jol: "))
        shot(app, "chat-chain-light")
    }

    func testChainReadsAsStepsInRussian() {
        let app = launch(language: "ru")
        turn(app, 0, "plan a trip")
        turn(app, 1, "5 days")
        turn(app, 2, "200000")
        waitFor(app, "graph-node-2")
        XCTAssertTrue(element(app, "graph-node-1").label.hasPrefix("Шаг 1: 5 дней"), element(app, "graph-node-1").label)
        let node = element(app, "graph-node-2")
        let spaced = NSPredicate { object, _ in
            let text = ((object as? XCUIElement)?.label ?? "").replacingOccurrences(of: "\u{00A0}", with: " ")
                .replacingOccurrences(of: "\u{202F}", with: " ")
            return text == "Шаг 2: 200 000 ₸"
        }
        XCTAssertEqual(XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: spaced, object: node)],
                                        timeout: 10), .completed, node.label)
        XCTAssertTrue(element(app, "chat-message-user").label.hasPrefix("Вы: "))
    }

    // MARK: - Largest text, dark theme

    func testChatAtLargestTextInDarkTheme() {
        let app = launch(dark: true, large: true)
        waitFor(app, "chat-panel")
        for id in ["open-sidebar", "open-profile-menu", "chat-collapse"] { assertTarget(app, id) }
        assertField(app)
        let greeting = element(app, "chat-greeting").frame
        XCTAssertTrue(app.frame.contains(greeting), "the greeting is not clipped by the screen")
        shot(app, "home-axxxl-dark")

        turn(app, 0, "plan a trip")
        turn(app, 1, "5 days")
        waitFor(app, "graph-node-1")
        assertTarget(app, "graph-node-1")
        assertField(app)
        element(app, "graph-node-1").tap()
        waitFor(app, "graph-node-detail")
        XCTAssertTrue(app.frame.contains(element(app, "graph-node-detail").frame))
        shot(app, "chat-axxxl-dark")

        element(app, "chat-collapse").tap()
        waitFor(app, "chat-collapsed-bar")
        let bar = element(app, "chat-collapsed-bar")
        XCTAssertTrue(app.frame.contains(bar.frame))
        XCTAssertTrue(bar.isHittable)
        XCTAssertTrue(element(app, "osm-attribution").exists)
        shot(app, "collapsed-axxxl-dark")
    }

    func testChatInDarkTheme() {
        let app = launch(dark: true)
        turn(app, 0, "plan a trip")
        turn(app, 1, "5 days")
        turn(app, 2, "200000")
        waitFor(app, "graph-node-2")
        shot(app, "chat-dark")
        let attribution = element(app, "osm-attribution")
        XCTAssertTrue(attribution.exists)
        XCTAssertEqual(attribution.label, "© OpenStreetMap contributors")
    }

    // MARK: - Live route

    func testLiveRouteIsReadInOrderAndTargetsAreLargeAtLargestText() {
        let app = launch(dark: true, large: true)
        send(app, "Chinese restaurant live1")
        waitFor(app, "live-stop-1")
        XCTAssertEqual(element(app, "live-stop-1").label, "Stop 1: Lan Zhou Noodle House")
        assertTarget(app, "live-stop-1")
        let alternative = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'live-alt-'")).firstMatch
        XCTAssertTrue(alternative.waitForExistence(timeout: 5))
        XCTAssertTrue(alternative.label.hasPrefix("Alternative: "), alternative.label)
        XCTAssertGreaterThanOrEqual(alternative.frame.height, 43.5)
        sleep(2)
        XCTAssertTrue(alternative.isHittable, "the pale pin is not under the chat card")
        alternative.tap()
        waitFor(app, "live-choose-card")
        for id in ["live-choose-confirm", "live-choose-details", "live-choose-close"] { assertTarget(app, id) }
        shot(app, "live-choose-axxxl-dark")
        element(app, "live-choose-close").tap()
        send(app, "First President park live2")
        waitFor(app, "live-edge-1-2")
        XCTAssertEqual(element(app, "live-edge-1-2").label, "From 1 to 2: by public transport 18 minutes")
        shot(app, "live-axxxl-dark")
    }
}
