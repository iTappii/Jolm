import XCTest

/// Ш-64. The chat does not wait for the map: the stub's message stream sends `live_route_status building` and the text
/// at once, and the stub's events stream delivers the route (and `ready`) about 1.6 s later. While the indicator
/// «Строю маршрут…» is up, the reply is visible and the input accepts the next wish.
///
/// Screenshots go to `docs/reviews/img/Ш-64/`.
@MainActor
final class BackgroundRouteUITests: XCTestCase {
    private func launch(dark: Bool, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-JolStubBuildDelay", "6",
                               "-JolForceTheme", dark ? "dark" : "light",
                               "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func capture(_ name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<3 { url.deleteLastPathComponent() }
        url.appendPathComponent("docs/reviews/img/Ш-64", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        try? screenshot.pngRepresentation.write(to: url.appendingPathComponent("\(name).png"))
    }

    private func runFlow(dark: Bool, language: String, building: String, reply: String) {
        let app = launch(dark: dark, language: language)
        let theme = dark ? "dark" : "light"
        let input = element(app, "chat-input")
        XCTAssertTrue(input.waitForExistence(timeout: 10))
        input.tap()
        input.typeText("Chinese restaurant live1")
        element(app, "chat-send").tap()

        // The answer text arrives right away, the route has not.
        let badge = element(app, "live-route-building")
        XCTAssertTrue(badge.waitForExistence(timeout: 5), "the building indicator never appeared")
        XCTAssertEqual(badge.label, building)
        XCTAssertFalse(element(app, "live-stop-1").exists, "the route is still being built")
        let answer = element(app, "chat-message-assistant")
        XCTAssertTrue(answer.waitForExistence(timeout: 5), "the reply text is visible")
        XCTAssertTrue(answer.label.contains(reply), "reply is \(answer.label)")
        Thread.sleep(forTimeInterval: 0.8) // the badge fades in
        capture("building-\(theme)")

        // The input is free while the map is not ready: the next wish can be typed (and the send button is on).
        input.typeText("hello")
        XCTAssertTrue(element(app, "chat-send").isEnabled, "sending must not wait for the map")

        // Then the route fills in and the indicator goes.
        XCTAssertTrue(element(app, "live-stop-1").waitForExistence(timeout: 20), "the route never appeared")
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"), object: badge)
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 5), .completed, "the indicator stays")
        capture("ready-\(theme)")
    }

    func testIndicatorThenRouteLight() {
        runFlow(
            dark: false, language: "en", building: "Building route…",
            reply: "I found three Chinese places; the first one is on your route.")
    }

    func testIndicatorThenRouteDarkRussian() {
        runFlow(
            dark: true, language: "ru", building: "Строю маршрут…",
            reply: "I found three Chinese places; the first one is on your route.")
    }
}
