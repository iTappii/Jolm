import XCTest

/// Ш-69. Main sights on the home map, on the stub API: nothing at the city overview, markers once zoomed in, a tap
/// opens the place card. The camera is set with `-JolStartCamera lat,lon,zoom`. Screenshots go to the
/// report and, with `TEST_RUNNER_LANDMARK_SHOTS=<dir>`, to that folder.
@MainActor
final class LandmarksUITests: XCTestCase {
    private static let medeu = "landmark-a0000000-0000-4000-8000-000000000001"
    private static let kokTobe = "landmark-a0000000-0000-4000-8000-000000000002"
    private static let bazaar = "landmark-a0000000-0000-4000-8000-000000000004"

    private func launch(camera: String? = nil, dark: Bool = false, language: String = "en") -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolForceTheme", dark ? "dark" : "light",
                               "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if let camera { app.launchArguments += ["-JolStartCamera", camera] }
        app.launch()
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        XCTAssertTrue(app.buttons["chat-collapsed-bar"].waitForExistence(timeout: 5))
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func markers(_ app: XCUIApplication) -> XCUIElementQuery {
        app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH 'landmark-'"))
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = ProcessInfo.processInfo.environment["LANDMARK_SHOTS"], !dir.isEmpty {
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
        }
    }

    func testCityOverviewShowsNoMarkers() {
        let app = launch(camera: "43.2,77.0,11")
        // The list arrives within a moment of the launch; give it time, then nothing may be on the map.
        Thread.sleep(forTimeInterval: 3)
        XCTAssertEqual(markers(app).count, 0, app.debugDescription)
        shot(app, "overview-light")
    }

    func testZoomedInShowsMarkersAndTheTapOpensTheCard() {
        let app = launch(camera: "43.157,77.059,12.5")
        let medeu = element(app, Self.medeu)
        XCTAssertTrue(medeu.waitForExistence(timeout: 15), app.debugDescription)
        XCTAssertEqual(medeu.label, "Medeu, landmark")
        XCTAssertTrue(medeu.isHittable)
        XCTAssertFalse(element(app, Self.kokTobe).exists, "Kok-Tobe is 8 km away, off the screen")
        XCTAssertFalse(element(app, "landmark-a0000000-0000-4000-8000-000000000007").exists, "Turkestan is far away")
        shot(app, "zoomed-light")

        medeu.tap()
        XCTAssertTrue(element(app, "place-card").waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(app.staticTexts["place-name"].label, "Medeu")
        XCTAssertTrue(element(app, "place-directions").exists)
        XCTAssertTrue(element(app, "place-favorite").exists)
        shot(app, "card-light")
    }

    func testSeveralSightsOfTheCityAtOnce() {
        let app = launch(camera: "43.248,76.955,13")
        XCTAssertTrue(element(app, Self.kokTobe).waitForExistence(timeout: 15), app.debugDescription)
        XCTAssertTrue(element(app, Self.bazaar).exists)
        XCTAssertEqual(element(app, Self.kokTobe).label, "Kok-Tobe, landmark")
        shot(app, "city-light")
    }

    func testDarkThemeAndRussianLabel() {
        let app = launch(camera: "43.157,77.059,12.5", dark: true, language: "ru")
        let medeu = element(app, Self.medeu)
        XCTAssertTrue(medeu.waitForExistence(timeout: 15), app.debugDescription)
        XCTAssertEqual(medeu.label, "Medeu, достопримечательность")
        shot(app, "zoomed-dark")
    }
}
