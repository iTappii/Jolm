import XCTest

/// Ш-62. The owner's scenario on RECORDED chat turns (`chat-icity-1…5.sse`, tags "icity1" … "icity5"): Shymbulak →
/// Charyn → Kolsai → Turkestan builds the live route with long dashed edges and «~N h» labels; the finished trip
/// (`IntercityStub`) shows its travel days and where each night is spent.
///
/// Screenshots go to `docs/reviews/img/Ш-62/`.
@MainActor
final class IntercityUITests: XCTestCase {
    private func launch(dark: Bool, language: String) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-JolForceTheme", dark ? "dark" : "light",
                               "-AppleLanguages", "(\(language))", "-AppleLocale",
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

    private func waitFor(_ app: XCUIApplication, _ identifier: String, timeout: TimeInterval = 20,
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

    private func settle() {
        Thread.sleep(forTimeInterval: 1.5)
    }

    private func capture(_ name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<3 { url.deleteLastPathComponent() }
        url.appendPathComponent("docs/reviews/img/Ш-62", isDirectory: true)
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        try? screenshot.pngRepresentation.write(to: url.appendingPathComponent("\(name).png"))
    }

    /// The four turns of the live route, then `route_ready` and the full map.
    private func buildScenario(_ app: XCUIApplication) {
        send(app, "Shymbulak icity1")
        waitFor(app, "live-stop-1")
        send(app, "Charyn icity2")
        waitFor(app, "live-edge-1-2")
        send(app, "Kolsai icity3")
        waitFor(app, "live-edge-2-3")
        send(app, "Turkestan icity4")
        waitFor(app, "live-edge-3-4")
    }

    private func openTrip(_ app: XCUIApplication) {
        send(app, "Build the route icity5")
        waitFor(app, "chat-open-route", timeout: 40)
        element(app, "chat-open-route").tap()
        waitFor(app, "trip-map")
        waitFor(app, "trip-stop-1")
    }

    func testLiveRouteShowsIntercityEdgesAndTheTripShowsTravelDaysAndNights() {
        let app = launch(dark: false, language: "en")
        buildScenario(app)

        // The edges: a long drive, a long drive, a flight — labelled with the hours.
        XCTAssertEqual(element(app, "live-edge-1-2").label, "From 1 to 2: by car about 4 hours")
        XCTAssertEqual(element(app, "live-edge-2-3").label, "From 2 to 3: by car about 3 hours, 30 minutes")
        XCTAssertEqual(element(app, "live-edge-3-4").label, "From 3 to 4: by plane about 2 hours")
        XCTAssertTrue(element(app, "live-stop-4").exists)
        settle()
        capture("intercity-live-light")

        // The finished trip: day 3 sleeps in Saty, day 5 is a flight to Turkestan.
        openTrip(app)
        element(app, "trip-day-chip-3").tap()
        waitFor(app, "trip-overnight")
        XCTAssertEqual(element(app, "trip-overnight").label, "Overnight: Saty")
        waitFor(app, "trip-intercity-leg")
        XCTAssertFalse(element(app, "trip-transfer").exists, "day 3 is a regular day")
        settle()
        capture("intercity-day-overnight-light")

        element(app, "trip-day-chip-5").tap()
        waitFor(app, "trip-transfer")
        XCTAssertEqual(element(app, "trip-transfer").label, "Travel to Turkestan")
        XCTAssertEqual(element(app, "trip-overnight").label, "Overnight: Turkestan")
        let leg = element(app, "trip-intercity-leg")
        waitFor(app, "trip-intercity-leg")
        XCTAssertTrue(leg.label.hasPrefix("Flight to Turkestan, about 2 hours"), leg.label)
        let chipValue = element(app, "trip-day-chip-5").value as? String
        XCTAssertEqual(chipValue?.hasPrefix("Flight to Turkestan, about 2 hours"), true, "\(chipValue ?? "nil")")
        settle()
        capture("intercity-transfer-day-light")

        // The leg card: way, time, price range and «approximate».
        leg.tap()
        waitFor(app, "trip-leg-intercity")
        XCTAssertTrue(element(app, "trip-leg-intercity").label.contains("about 2 hours"))
        capture("intercity-leg-sheet-light")
    }

    func testRussianAndDarkTheme() {
        let app = launch(dark: true, language: "ru")
        buildScenario(app)
        XCTAssertEqual(element(app, "live-edge-3-4").label, "От 3 до 4: на самолёте около 2 часов")
        XCTAssertEqual(element(app, "live-edge-1-2").label, "От 1 до 2: на машине около 4 часов")
        settle()
        capture("intercity-live-dark")
        openTrip(app)
        element(app, "trip-day-chip-5").tap()
        waitFor(app, "trip-transfer")
        XCTAssertEqual(element(app, "trip-transfer").label, "Переезд в Туркестан")
        XCTAssertEqual(element(app, "trip-overnight").label, "Ночёвка: Туркестан")
        waitForLabel(element(app, "trip-intercity-leg"), contains: "Перелёт в Туркестан, около 2 часов")
        settle()
        capture("intercity-transfer-day-dark")
        element(app, "trip-day-chip-3").tap()
        waitFor(app, "trip-overnight")
        XCTAssertEqual(element(app, "trip-overnight").label, "Ночёвка: Саты")
        settle()
        capture("intercity-day-overnight-dark")
    }
}
