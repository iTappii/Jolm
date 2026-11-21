import XCTest

/// Ш-23c. A tap on a point of the map that is not a pin opens a card with its address; «Route» works from there.
/// `GET /v1/geocode/reverse` is stubbed (`-JolStubAPI`, `-JolStubGeocode point|building|fail`), no server is needed.
@MainActor
final class TapPointUITests: XCTestCase {
    private func launch(language: String = "en", geocode: String? = nil) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))",
                               "-AppleLocale", language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if let geocode { app.launchArguments += ["-JolStubGeocode", geocode] }
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

    /// An empty spot: upper left of the map, away from both fixture pins (the museum is in the middle).
    private func tapEmptySpot(_ app: XCUIApplication) {
        app.coordinate(withNormalizedOffset: CGVector(dx: 0.25, dy: 0.3)).tap()
    }

    func testTapOnAnEmptyPointOpensTheAddressCardAndRouteWorks() {
        let app = launch()
        tapEmptySpot(app)
        XCTAssertTrue(element(app, "point-card").waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(app.staticTexts["place-name"].label, "Test Street 7")
        XCTAssertTrue(element(app, "place-directions").isHittable)
        XCTAssertFalse(element(app, "place-favorite").exists, "favorites only for places of our base")
        XCTAssertFalse(element(app, "place-tab-reviews").exists, "no tabs for an address")
        let shot = XCTAttachment(screenshot: app.screenshot())
        shot.name = "tap-point-address"
        shot.lifetime = .keepAlways
        add(shot)

        element(app, "place-directions").tap()
        XCTAssertTrue(element(app, "directions-panel").waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertEqual(element(app, "directions-title").label, "Test Street 7")
        XCTAssertTrue(element(app, "directions-page-walk").waitForExistence(timeout: 10), app.debugDescription)
    }

    func testBuildingShowsItsNameAndItsStreet() {
        let app = launch(geocode: "building")
        tapEmptySpot(app)
        XCTAssertTrue(element(app, "point-card").waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(app.staticTexts["place-name"].label, "Fixture Hall")
        XCTAssertEqual(element(app, "place-address").label, "Test Street 7")
    }

    func testBarePointShowsCoordinatesInRussian() {
        let app = launch(language: "ru", geocode: "point")
        tapEmptySpot(app)
        XCTAssertTrue(element(app, "point-card").waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(element(app, "point-kind").label, "Точка на карте")
        XCTAssertTrue(app.staticTexts["place-name"].label.contains("43."), "the coordinates are the title")
        XCTAssertTrue(app.buttons["place-directions"].exists)
    }

    func testFailedLookupStillOpensThePointForRoute() {
        let app = launch(geocode: "fail")
        tapEmptySpot(app)
        XCTAssertTrue(element(app, "point-card").waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(element(app, "point-kind").label, "Point on the map")
        element(app, "place-directions").tap()
        XCTAssertTrue(element(app, "directions-page-walk").waitForExistence(timeout: 10), app.debugDescription)
    }

    func testTapNearAPlaceOpensThatPlace() {
        let app = launch()
        // The museum is at the map center: a tap there is a pin hit or, before the pins arrive, a lookup within 30 m.
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertEqual(app.staticTexts["place-name"].label, "Fixture Museum")
        XCTAssertTrue(element(app, "place-favorite").exists, "a place of ours keeps «Add to favorites»")
        XCTAssertFalse(element(app, "point-card").exists)
    }

    func testSwipingTheCardDownClosesItAndAnotherTapReopens() {
        let app = launch()
        tapEmptySpot(app)
        let card = element(app, "point-card")
        XCTAssertTrue(card.waitForExistence(timeout: 10), app.debugDescription)
        element(app, "place-card").swipeDown()
        let gone = NSPredicate(format: "exists == false")
        expectation(for: gone, evaluatedWith: card)
        waitForExpectations(timeout: 5)
        tapEmptySpot(app)
        XCTAssertTrue(card.waitForExistence(timeout: 10), app.debugDescription)
    }
}
