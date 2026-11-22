import XCTest

/// Ш-32b. The answer chain in the chat on a RECORDED dialog (`chat-dlg-0…6.sse`, replayed by `-JolStubAPI`):
/// question → the tourist's answer → a node with the value (days → budget → lodging → a wish), a changed answer
/// changes the label and not the node count, the chain ends with a finish node after `route_ready`. The turns of
/// the dialog are in `UITestChatStub`.
@MainActor
final class ChatChainUITests: XCTestCase {
    private func launch(language: String = "en", dark: Bool = false) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        XCUIDevice.shared.appearance = dark ? .dark : .light
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

    private func waitFor(_ app: XCUIApplication, _ identifier: String, timeout: TimeInterval = 15) {
        XCTAssertTrue(element(app, identifier).waitForExistence(timeout: timeout), "\(identifier) never appeared")
    }

    private func waitForValue(_ element: XCUIElement, _ value: String) {
        let predicate = NSPredicate(format: "value == %@", value)
        let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: 10), .completed,
                       "value is \(String(describing: element.value)), expected \(value)")
    }

    private func waitForDisappearance(_ element: XCUIElement) {
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 15), .completed)
    }

    private func nodeCount(_ app: XCUIApplication) -> Int {
        let predicate = NSPredicate(format: "identifier BEGINSWITH 'graph-node-' AND identifier != 'graph-node-detail'"
            + " AND identifier != 'graph-node-thesis'")
        return app.descendants(matching: .any).matching(predicate).count
    }

    private func label(_ app: XCUIApplication, _ index: Int) -> String {
        element(app, "graph-node-\(index)").label
            .replacingOccurrences(of: "\u{00A0}", with: " ").replacingOccurrences(of: "\u{202F}", with: " ")
    }

    private func waitForLabel(_ app: XCUIApplication, _ index: Int, _ expected: String) {
        let node = element(app, "graph-node-\(index)")
        let predicate = NSPredicate(format: "label == %@", expected)
        XCTAssertEqual(XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: predicate, object: node)],
                                        timeout: 10), .completed, "label is \(node.label), expected \(expected)")
    }

    /// The assistant's reply of a turn has been written (it ends with a question or the route is ready).
    private func waitForAnswerDone(_ app: XCUIApplication) {
        let typing = element(app, "chat-typing")
        sleep(1)
        waitForDisappearance(typing)
    }

    /// One turn of the recorded dialog: the user's answer goes out, the stream is replayed to its end.
    private func turn(_ app: XCUIApplication, _ number: Int, _ answer: String) {
        send(app, "#dlg\(number) \(answer)")
        waitForAnswerDone(app)
    }

    /// Plays «days → budget → lodging → a wish» and leaves the chain with four nodes.
    private func playToFourNodes(_ app: XCUIApplication) {
        turn(app, 0, "plan a trip")
        turn(app, 1, "5 days")
        turn(app, 2, "200000")
        turn(app, 3, "I have a hotel")
        turn(app, 4, "eastern food")
    }

    func testNodesAreTheAnswersInOrderOfAnswering() {
        let app = launch()
        turn(app, 0, "plan a trip")
        XCTAssertEqual(nodeCount(app), 0, "a question alone makes no node")
        XCTAssertFalse(element(app, "chat-chain").exists)

        turn(app, 1, "5 days")
        waitFor(app, "graph-node-1")
        XCTAssertTrue(label(app, 1).hasPrefix("5 days"), label(app, 1))
        XCTAssertEqual(nodeCount(app), 1)

        turn(app, 2, "200000")
        waitFor(app, "graph-node-2")
        XCTAssertEqual(label(app, 2), "200,000 ₸")
        XCTAssertEqual(nodeCount(app), 2)

        turn(app, 3, "I have a hotel")
        waitFor(app, "graph-node-3")
        XCTAssertEqual(label(app, 3), "Have accommodation")

        turn(app, 4, "eastern food")
        waitFor(app, "graph-node-4")
        XCTAssertEqual(label(app, 4), "Eastern cuisine")
        XCTAssertEqual(nodeCount(app), 4)
        XCTAssertEqual(element(app, "chat-chain").value as? String, "building")
        XCTAssertEqual(element(app, "chat-chain").label, "4 answers, route is not ready")
        XCTAssertFalse(element(app, "graph-chain-finish").exists)
    }

    func testChangedAnswerUpdatesTheLabelNotTheNodeCount() {
        let app = launch()
        playToFourNodes(app)
        XCTAssertEqual(label(app, 2), "200,000 ₸")
        turn(app, 5, "actually 300000")
        waitForLabel(app, 2, "300,000 ₸")
        XCTAssertEqual(nodeCount(app), 4, "the answer changed, no new node")
        XCTAssertEqual(label(app, 4), "Eastern cuisine")
    }

    func testFinishNodeEndsTheChainOnRouteReadyAndTapShowsTheFullValue() {
        let app = launch()
        playToFourNodes(app)
        XCTAssertFalse(app.buttons["chat-open-route"].exists, "the open-map button comes with the finish node")
        send(app, "#dlg6 build it")
        waitFor(app, "graph-chain-finish")
        waitForValue(element(app, "chat-chain"), "ready")
        XCTAssertEqual(nodeCount(app), 4)
        XCTAssertEqual(element(app, "chat-chain").label, "4 answers, route is ready")
        XCTAssertTrue(app.buttons["chat-open-route"].exists)

        element(app, "graph-node-1").tap()
        waitFor(app, "graph-node-detail")
        let detail = element(app, "graph-node-detail").label
        XCTAssertTrue(detail.hasPrefix("5 days · "), detail)
        element(app, "graph-node-1").tap()
        waitForDisappearance(element(app, "graph-node-detail"))
    }

    private func mid(_ app: XCUIApplication, _ index: Int) -> CGPoint {
        let frame = element(app, "graph-node-\(index)").frame
        return CGPoint(x: frame.midX, y: frame.midY)
    }

    /// Ш-32b (owner): the chain is a strip at the top of the card, full width, under the header and above the
    /// messages; 1 node is centred, 2 sit left and right, then it grows left to right with a wave.
    func testChainStripSitsUnderTheHeaderAndGrowsLeftToRight() {
        let app = launch()
        turn(app, 0, "plan a trip")
        turn(app, 1, "5 days")
        waitFor(app, "graph-node-1")
        let card = element(app, "chat-panel").frame
        let chain = element(app, "chat-chain").frame
        XCTAssertGreaterThan(chain.width, card.width * 0.8, "full card width")
        XCTAssertEqual(chain.midX, card.midX, accuracy: 4)
        XCTAssertGreaterThanOrEqual(chain.minY, element(app, "chat-collapse").frame.maxY - 1, "under the header")
        XCTAssertLessThan(chain.height, 95, "compact")
        XCTAssertEqual(mid(app, 1).x, chain.midX, accuracy: 6, "one node is centred")

        turn(app, 2, "200000")
        waitFor(app, "graph-node-2")
        sleep(1)
        XCTAssertLessThan(mid(app, 1).x, chain.midX)
        XCTAssertGreaterThan(mid(app, 2).x, chain.midX)
        XCTAssertEqual((mid(app, 1).x + mid(app, 2).x) / 2, chain.midX, accuracy: 6, "the pair is centred")

        turn(app, 3, "I have a hotel")
        turn(app, 4, "eastern food")
        waitFor(app, "graph-node-4")
        sleep(1)
        let xs = (1...4).map { mid(app, $0).x }
        XCTAssertEqual(xs, xs.sorted(), "left to right")
        XCTAssertEqual((xs[0] + xs[3]) / 2, chain.midX, accuracy: 6, "the chain is centred")
        XCTAssertLessThan(mid(app, 1).y, mid(app, 2).y, "wave: node 1 high, node 2 low")
        XCTAssertLessThan(mid(app, 3).y, mid(app, 2).y, "wave: node 3 high")
        // Above the messages and the input.
        let transcript = element(app, "chat-transcript").frame
        XCTAssertLessThanOrEqual(chain.maxY, transcript.minY + 14, "chain is above the messages")
        XCTAssertLessThan(chain.maxY, element(app, "chat-input").frame.minY)
        XCTAssertTrue(card.contains(chain))
        assertHomeLayout(app, nodes: 4)
    }

    /// With more nodes than fit the strip scrolls to the newest node and stays above the messages and the input.
    func testManyNodesScrollToTheNewest() {
        let app = launch()
        playToFourNodes(app)
        turn(app, 7, "more")
        waitFor(app, "graph-node-8")
        sleep(1)
        let chain = element(app, "chat-chain").frame
        let last = mid(app, 8)
        XCTAssertTrue(chain.contains(last), "the newest node is scrolled into view: \(last) in \(chain)")
        XCTAssertLessThan(chain.maxY, element(app, "chat-input").frame.minY)
        XCTAssertEqual(nodeCount(app), 8)
        XCTAssertEqual(label(app, 8), "Prefer quiet")
        assertHomeLayout(app, nodes: 8)
    }

    /// The home layout around the card: profile top-right, the card between the top buttons and the attribution.
    private func assertHomeLayout(_ app: XCUIApplication, nodes: Int) {
        // The field keeps the keyboard after sending; the resting layout is checked with it closed.
        if !app.keyboards.allElementsBoundByIndex.isEmpty {
            element(app, "chat-transcript").tap()
            let closed = XCTNSPredicateExpectation(predicate: NSPredicate(format: "count == 0"), object: app.keyboards)
            XCTAssertEqual(XCTWaiter().wait(for: [closed], timeout: 5), .completed, "the keyboard closes")
        }
        let card = element(app, "chat-panel").frame
        let attribution = element(app, "osm-attribution").frame
        XCTAssertLessThanOrEqual(attribution.minY - card.maxY, 16, "\(nodes) nodes: card reaches attribution")
        XCTAssertGreaterThanOrEqual(attribution.minY - card.maxY, 0, "\(nodes) nodes: card above attribution")
        let profile = element(app, "open-profile-menu").frame
        XCTAssertGreaterThan(profile.midX, app.frame.width * 0.75, "profile button in the right quarter")
        XCTAssertLessThan(profile.midY, app.frame.height * 0.25, "profile button in the upper quarter")
        XCTAssertLessThanOrEqual(profile.maxY, card.minY, "\(nodes) nodes: card is below the profile button")
    }

    /// Ш-32b (owner): the attribution line is pinned to the bottom; the keyboard slides over it, it does not rise.
    func testAttributionStaysPutWhenTheKeyboardAppears() {
        let app = launch()
        playToFourNodes(app)
        let before = element(app, "osm-attribution").frame
        element(app, "chat-input").tap()
        sleep(2)
        XCTAssertEqual(element(app, "osm-attribution").frame, before, "the attribution does not move with the keyboard")
        XCTAssertLessThan(element(app, "chat-input").frame.maxY, app.frame.height, "the input stays on screen")
        let card = element(app, "chat-panel").frame
        XCTAssertGreaterThanOrEqual(card.minY, element(app, "open-profile-menu").frame.maxY, "card under buttons")
    }

    func testRussianLabels() {
        let app = launch(language: "ru")
        playToFourNodes(app)
        XCTAssertTrue(label(app, 1).hasPrefix("5 дней"), label(app, 1))
        XCTAssertEqual(label(app, 2), "200 000 ₸")
        XCTAssertEqual(label(app, 3), "жильё есть")
        XCTAssertEqual(element(app, "chat-chain").label, "4 ответа, маршрут не готов")
    }

    /// Screenshots for the review (light and dark): 1, 2, 4 nodes, 8 nodes + route ready, keyboard up, collapsed.
    /// Skipped when the directory does not exist.
    func testChainScreenshots() throws {
        let directory = "/Users/ramazannurahunov/Desktop/Jol v2/docs/reviews/img"
        try XCTSkipUnless(FileManager.default.fileExists(atPath: directory), "no screenshot directory")
        func shot(_ name: String, _ suffix: String) throws {
            sleep(2)
            try XCUIScreen.main.screenshot().pngRepresentation
                .write(to: URL(fileURLWithPath: "\(directory)/chain-\(name)-\(suffix).png"))
        }
        for dark in [false, true] {
            let suffix = dark ? "dark" : "light"
            let app = launch(dark: dark)
            if !dark { try shot("empty", suffix) }
            turn(app, 0, "plan a trip")
            turn(app, 1, "5 days")
            waitFor(app, "graph-node-1")
            try shot("1node", suffix)
            turn(app, 2, "200000")
            waitFor(app, "graph-node-2")
            try shot("2nodes", suffix)
            turn(app, 3, "I have a hotel")
            turn(app, 4, "eastern food")
            waitFor(app, "graph-node-4")
            try shot("4nodes", suffix)
            element(app, "chat-input").tap()
            try shot("keyboard", suffix)
            element(app, "chat-collapse").tap()
            if !dark { try shot("collapsed", suffix) }
            element(app, "chat-collapsed-bar").tap()
            send(app, "#dlg6 build it")
            waitFor(app, "graph-chain-finish")
            waitForAnswerDone(app)
            try shot("route-ready", suffix)
            turn(app, 7, "more")
            waitFor(app, "graph-node-8")
            try shot("8nodes-ready", suffix)
            app.terminate()
        }
    }
}
