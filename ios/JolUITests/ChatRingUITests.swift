import XCTest

/// Ш-32a. The thesis ring in the chat on RECORDED SSE streams (`chat-ring6/3/1.sse`, replayed by `-JolStubAPI`):
/// the node count grows with `graph_node`, the ring is open until `route_ready` and closed after it, a tap on a
/// node shows the full thesis. Details of the stream in `UITestChatStub`.
@MainActor
final class ChatRingUITests: XCTestCase {
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
        let predicate = NSPredicate(format: "identifier BEGINSWITH 'graph-node-' AND identifier != 'graph-node-detail'")
        return app.descendants(matching: .any).matching(predicate).count
    }

    func testRingGrowsOpenThenClosesOnRouteReady() {
        let app = launch()
        send(app, "#ring6 plan a trip")
        let ring = element(app, "chat-graph-ring")
        waitFor(app, "graph-node-1")
        XCTAssertEqual(ring.value as? String, "open")
        XCTAssertFalse(element(app, "graph-ring-closed").exists)
        XCTAssertFalse(app.buttons["chat-open-route"].exists, "the open-map button comes with the closed ring")

        // Each `graph_node` adds a node (1 → 3 nodes in the other tests); the ring closes only on `route_ready`.
        waitFor(app, "graph-node-2")
        waitFor(app, "graph-ring-closed")
        waitForValue(ring, "closed")
        waitFor(app, "graph-node-6")
        XCTAssertEqual(nodeCount(app), 6)
        XCTAssertEqual(ring.label, "6 theses, route is ready")
        XCTAssertTrue(app.buttons["chat-open-route"].exists)

        // Tapping a node shows its full text; tapping it again hides it.
        element(app, "graph-node-4").tap()
        waitFor(app, "graph-node-detail")
        XCTAssertEqual(element(app, "graph-node-detail").label, "Loves mountain hikes")
        element(app, "graph-node-4").tap()
        waitForDisappearance(element(app, "graph-node-detail"))
    }

    func testOpenRingWithThreeNodesStaysOpen() {
        let app = launch()
        send(app, "#ring3 plan a trip")
        waitFor(app, "graph-node-3")
        waitForDisappearance(element(app, "chat-typing"))
        XCTAssertEqual(element(app, "chat-graph-ring").value as? String, "open")
        XCTAssertEqual(element(app, "chat-graph-ring").label, "3 theses, route is not ready")
        XCTAssertFalse(element(app, "graph-ring-closed").exists)
        XCTAssertFalse(app.buttons["chat-open-route"].exists)
        XCTAssertEqual(nodeCount(app), 3)
    }

    func testSingleThesisIsOneDot() {
        let app = launch()
        send(app, "#ring1 plan a trip")
        waitFor(app, "graph-node-1")
        waitForDisappearance(element(app, "chat-typing"))
        XCTAssertEqual(nodeCount(app), 1)
        XCTAssertEqual(element(app, "chat-graph-ring").label, "1 thesis, route is not ready")
        XCTAssertFalse(element(app, "graph-ring-closed").exists)
    }

    func testRussianRingSummary() {
        let app = launch(language: "ru")
        send(app, "#ring6 маршрут")
        waitFor(app, "graph-ring-closed")
        XCTAssertEqual(element(app, "chat-graph-ring").label, "6 тезисов, маршрут готов")
    }

    /// Screenshots of the final layout (light and dark) for the review. Skipped when the directory does not exist.
    func testRingScreenshots() throws {
        let directory = "/private/tmp/claude-501/-Users-ramazannurahunov--claude-spares-spare-jlg9ow/"
            + "cd2828c5-189b-4c50-a996-9b0538ff97d7/scratchpad"
        try XCTSkipUnless(FileManager.default.fileExists(atPath: directory), "no screenshot directory")
        let scenarios = [("open-3", "#ring3", "graph-node-3"), ("closed-6", "#ring6", "graph-ring-closed"),
                         ("single", "#ring1", "graph-node-1")]
        for dark in [false, true] {
            for (name, marker, ready) in scenarios {
                let app = launch(dark: dark)
                send(app, "\(marker) plan a trip")
                waitFor(app, ready)
                waitForDisappearance(element(app, "chat-typing"))
                sleep(2)
                let data = XCUIScreen.main.screenshot().pngRepresentation
                try data.write(to: URL(fileURLWithPath: "\(directory)/ring-\(name)-\(dark ? "dark" : "light").png"))
                app.terminate()
            }
        }
    }
}
