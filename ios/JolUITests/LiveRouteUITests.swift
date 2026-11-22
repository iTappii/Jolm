import XCTest

/// Ш-54. The live route on the map while chatting, on the RECORDED dialog `chat-live-1…4.sse` (turns are picked by a
/// plain word in the message: "live1" … "live4"): a Chinese place with two alternatives → First President's Park
/// (transit 18 min) → Green Bazaar (car 21 min) → `route_ready`. The pins and capsules are SwiftUI over the map, so
/// they are real accessibility elements: `live-stop-N`, `live-alt-…`, `live-edge-A-B`.
///
/// Screenshots go to `docs/reviews/img/Ш-54/` (written from the test; also attached to the result bundle).
@MainActor
final class LiveRouteUITests: XCTestCase {
    private func launch(dark: Bool = false, language: String = "en") -> XCUIApplication {
        XCUIDevice.shared.appearance = dark ? .dark : .light
        addTeardownBlock { XCUIDevice.shared.appearance = .light }
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
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
        XCTAssertTrue(element(app, identifier).waitForExistence(timeout: timeout), "\(identifier) never appeared",
                      file: file, line: line)
    }

    private func waitForLabel(_ element: XCUIElement, contains text: String, timeout: TimeInterval = 15,
                              file: StaticString = #filePath, line: UInt = #line) {
        let expectation = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "label CONTAINS %@", text), object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: timeout), .completed,
                       "label is \(element.label)", file: file, line: line)
    }

    private func waitForValue(_ element: XCUIElement, _ value: String, timeout: TimeInterval = 15,
                              file: StaticString = #filePath, line: UInt = #line) {
        let expectation = XCTNSPredicateExpectation(
            predicate: NSPredicate(format: "value == %@", value), object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [expectation], timeout: timeout), .completed,
                       "value is \(String(describing: element.value)), expected \(value)", file: file, line: line)
    }

    private func waitForDisappearance(_ element: XCUIElement, timeout: TimeInterval = 20,
                                      file: StaticString = #filePath, line: UInt = #line) {
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: element)
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: timeout), .completed, file: file, line: line)
    }

    private func alternatives(_ app: XCUIApplication) -> XCUIElementQuery {
        app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'live-alt-'"))
    }

    private func waitForAnswer(_ app: XCUIApplication) {
        // The stream ends with `done`: the send button is back (it is a stop/typing state while streaming).
        _ = element(app, "chat-input").waitForExistence(timeout: 5)
        Thread.sleep(forTimeInterval: 1.2)
    }

    private func capture(_ name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        // …/ios/JolUITests/File.swift → …/docs/reviews/img/Ш-54/
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<3 { url.deleteLastPathComponent() }
        url.appendPathComponent("docs/reviews/img/Ш-54", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        try? screenshot.pngRepresentation.write(to: url.appendingPathComponent("\(name).png"))
    }

    // MARK: - Tests

    func testLiveRouteGrowsAlternativeIsChosenAndRouteReadyHandsOver() {
        let app = launch()
        XCTAssertEqual(element(app, "live-route-stops").value as? String, "0")

        // Turn 1: one stop, two alternatives; no edge yet.
        send(app, "Chinese restaurant live1")
        waitFor(app, "live-stop-1")
        waitForValue(element(app, "live-route-stops"), "1")
        XCTAssertEqual(alternatives(app).count, 2)
        XCTAssertFalse(element(app, "live-stop-2").exists)
        XCTAssertEqual(element(app, "live-stop-1").label, "Stop 1: Lan Zhou Noodle House")
        waitForAnswer(app)
        capture("live-1-stop-light")

        // Turn 2: the second stop and a transit edge with the time.
        send(app, "First President park live2")
        waitFor(app, "live-stop-2")
        waitFor(app, "live-edge-1-2")
        XCTAssertEqual(element(app, "live-edge-1-2").label, "From 1 to 2: by public transport 18 minutes")
        waitForAnswer(app)
        capture("live-2-stops-light")

        // Turn 3: the third stop; the edge 2→3 is a car leg.
        send(app, "Green Bazaar live3")
        waitFor(app, "live-stop-3")
        waitFor(app, "live-edge-2-3")
        XCTAssertEqual(element(app, "live-edge-2-3").label, "From 2 to 3: by car 21 minutes")
        waitForValue(element(app, "live-route-stops"), "3")
        XCTAssertTrue(element(app, "live-stop-3").isHittable)
        waitForAnswer(app)
        capture("live-3-stops-light")

        // Tapping a pale alternative offers "Choose this instead"; confirming swaps stop 1.
        let alternative = alternatives(app).firstMatch
        XCTAssertTrue(alternative.isHittable)
        XCTAssertGreaterThanOrEqual(alternative.frame.width, 43.9)
        XCTAssertGreaterThanOrEqual(alternative.frame.height, 43.9)
        alternative.tap()
        waitFor(app, "live-choose-card")
        capture("live-choose-card-light")
        element(app, "live-choose-confirm").tap()
        waitForLabel(element(app, "live-stop-1"), contains: "Dragon Pearl")
        waitForDisappearance(element(app, "live-choose-card"), timeout: 5)
        XCTAssertEqual(alternatives(app).count, 2, "the old stop became an alternative")
        waitForAnswer(app)
        capture("live-after-choose-light")

        // route_ready: the live route goes, the trip by days takes over.
        send(app, "Build the route live4")
        waitForDisappearance(element(app, "live-stop-1"), timeout: 30)
        waitForValue(element(app, "live-route-stops"), "0")
        XCTAssertFalse(element(app, "live-edge-1-2").exists)
        waitFor(app, "chat-open-route")
    }

    func testDarkThemeAndRussianLabels() {
        let app = launch(dark: true, language: "ru")
        send(app, "Chinese restaurant live1")
        waitFor(app, "live-stop-1")
        XCTAssertEqual(element(app, "live-stop-1").label, "Остановка 1: Lan Zhou Noodle House")
        waitForAnswer(app)
        capture("live-1-stop-dark")
        send(app, "First President park live2")
        waitFor(app, "live-edge-1-2")
        XCTAssertEqual(element(app, "live-edge-1-2").label, "От 1 до 2: на транспорте 18 минут")
        waitForAnswer(app)
        capture("live-2-stops-dark")
        send(app, "Green Bazaar live3")
        waitFor(app, "live-edge-2-3")
        XCTAssertEqual(element(app, "live-edge-2-3").label, "От 2 до 3: на машине 21 минута")
        waitForAnswer(app)
        capture("live-3-stops-dark")
        alternatives(app).firstMatch.tap()
        waitFor(app, "live-choose-card")
        element(app, "live-choose-confirm").tap()
        waitForLabel(element(app, "live-stop-1"), contains: "Dragon Pearl")
        waitForAnswer(app)
        capture("live-after-choose-dark")
    }

    func testTappingAStopOpensThePlaceCard() {
        let app = launch()
        send(app, "Chinese restaurant live1")
        waitForAnswer(app)
        waitFor(app, "live-stop-1")
        element(app, "live-stop-1").tap()
        XCTAssertTrue(app.descendants(matching: .any)["place-card"].firstMatch.waitForExistence(timeout: 10)
                      || app.staticTexts["Lan Zhou Noodle House"].waitForExistence(timeout: 10))
    }
}
