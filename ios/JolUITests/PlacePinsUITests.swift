import XCTest

/// Ш-70. Ordinary place pins only from street zoom (a logo where the venue has one), no clusters at mid zoom, and the
/// card with rating, today's hours, address and the distance from the person. The stub API answers; the stub "user"
/// stands at (43.231, 76.935), the fixture museum at the map centre. The map reports what it draws as the value of
/// `map-drawn-pins` (`pins:N,logos:M,clusters:K`).
@MainActor
final class PlacePinsUITests: XCTestCase {
    private let museumCamera = "43.2380,76.9450"  // ≈ Region.current.center; see UITestSupport.placesJSON

    private func launch(camera: String? = nil, language: String = "en", dark: Bool = false,
                        extra: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolForceTheme", dark ? "dark" : "light",
                               "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"] + extra
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

    struct Drawn {
        let pins: Int
        let logos: Int
        let clusters: Int
    }

    /// `pins:N,logos:M,clusters:K` as numbers.
    private func drawn(_ app: XCUIApplication) -> Drawn? {
        let value = element(app, "map-drawn-pins").value as? String ?? ""
        let numbers = value.split(separator: ",").compactMap { $0.split(separator: ":").last.flatMap { Int($0) } }
        guard numbers.count == 3 else { return nil }
        return Drawn(pins: numbers[0], logos: numbers[1], clusters: numbers[2])
    }

    private func waitForDrawn(_ app: XCUIApplication, timeout: TimeInterval = 20,
                              _ condition: @escaping (Drawn) -> Bool) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if let value = drawn(app), condition(value) { return true }
            Thread.sleep(forTimeInterval: 0.5)
        }
        return false
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = ProcessInfo.processInfo.environment["PIN_SHOTS"], !dir.isEmpty {
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            try? screenshot.pngRepresentation.write(to: URL(fileURLWithPath: dir).appendingPathComponent("\(name).png"))
        }
    }

    func testMidZoomShowsSightsButNoPinsAndNoClusters() throws {
        let app = launch(camera: "43.157,77.059,12.5")
        XCTAssertTrue(element(app, "landmark-a0000000-0000-4000-8000-000000000001").waitForExistence(timeout: 15),
                      app.debugDescription)
        Thread.sleep(forTimeInterval: 3)  // the places of the area have been loaded by now
        let state = try XCTUnwrap(drawn(app), "the map reports what it draws")
        XCTAssertEqual(state.pins, 0)
        XCTAssertEqual(state.clusters, 0)
        shot(app, "mid-light")
    }

    func testStreetZoomShowsPinsWithALogoAndTheCardHasTheNewLines() throws {
        let app = launch(camera: "\(museumCamera),15.5")
        let settled = waitForDrawn(app) { $0.pins >= 2 && $0.logos == 1 }
        shot(app, "street-light")
        XCTAssertTrue(settled, "pins and the bakery's logo: \(drawn(app) as Any)")
        XCTAssertEqual(drawn(app)?.clusters, 0)

        // The museum sits at the centre of the screen.
        let card = element(app, "place-card")
        for _ in 0..<8 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
        XCTAssertEqual(app.staticTexts["place-name"].label, "Fixture Museum")
        let rating = element(app, "place-rating")
        XCTAssertTrue(rating.waitForExistence(timeout: 8), app.debugDescription)
        XCTAssertEqual(rating.label, "Rating 4.6 out of 5, 23 reviews")
        XCTAssertEqual(element(app, "place-today").label, "Today 10:00–23:00 · Open")
        XCTAssertEqual(element(app, "place-address").label, "1 Test Street, Almaty")
        let distance = element(app, "place-distance")
        XCTAssertTrue(distance.waitForExistence(timeout: 8), "the stub user has granted access")
        XCTAssertTrue(distance.label.hasSuffix(" away"), distance.label)
        XCTAssertTrue(element(app, "place-directions").isHittable)
        XCTAssertTrue(element(app, "place-favorite").isHittable)
        shot(app, "card-light")
    }

    func testNoDistanceWithoutLocationAccess() throws {
        let app = launch(camera: "\(museumCamera),15.5", extra: ["-JolStubLocation", "denied"])
        let card = element(app, "place-card")
        for _ in 0..<8 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(element(app, "place-rating").waitForExistence(timeout: 8))
        Thread.sleep(forTimeInterval: 2)
        XCTAssertFalse(element(app, "place-distance").exists)
    }

    func testRussianCardInDarkTheme() throws {
        let app = launch(camera: "\(museumCamera),15.5", language: "ru", dark: true)
        let card = element(app, "place-card")
        for _ in 0..<8 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        let rating = element(app, "place-rating")
        XCTAssertTrue(rating.waitForExistence(timeout: 8), app.debugDescription)
        XCTAssertEqual(rating.label, "Рейтинг 4,6 из 5, 23 отзыва")
        XCTAssertEqual(element(app, "place-today").label, "Сегодня 10:00–23:00 · Открыто")
        XCTAssertTrue(element(app, "place-distance").waitForExistence(timeout: 8))
        XCTAssertTrue(element(app, "place-distance").label.hasSuffix(" от вас"))
        shot(app, "card-dark-ru")
    }
}
