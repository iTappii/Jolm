import XCTest

/// Ш-23. Directions and location are stubbed (`-JolStubAPI`, `-JolStubLocation`), so no server or GPS is needed.
@MainActor
final class DirectionsUITests: XCTestCase {
    private func launch(language: String = "en", location: String? = nil) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))",
                               "-AppleLocale", language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if let location { app.launchArguments += ["-JolStubLocation", location] }
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func openDirections(_ app: XCUIApplication) {
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
        let button = element(app, "place-directions")
        XCTAssertTrue(button.waitForExistence(timeout: 5))
        button.tap()
        XCTAssertTrue(element(app, "directions-panel").waitForExistence(timeout: 5), app.debugDescription)
    }

    func testCarouselLoopsAndVariantSelection() {
        let app = launch()
        openDirections(app)

        // Always opens on walking (not on the recommended page); the origin is the user's location.
        XCTAssertTrue(element(app, "directions-page-walk").waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(element(app, "directions-origin").label, "From: your location")
        XCTAssertTrue(element(app, "direction-variant-walk-2").exists, "several variants per page")
        XCTAssertTrue(element(app, "direction-variant-walk-1").label.contains("Free"))
        XCTAssertTrue(element(app, "direction-variant-walk-1").isSelected, "the first variant is selected")
        element(app, "direction-variant-walk-2").tap()
        XCTAssertTrue(element(app, "direction-variant-walk-2").isSelected)

        // Swipe left: walk → transit → taxi → walk (loops around).
        let carousel = element(app, "directions-carousel")
        carousel.swipeLeft()
        XCTAssertTrue(element(app, "directions-page-transit").waitForExistence(timeout: 5), app.debugDescription)
        let bus = element(app, "direction-variant-transit-1")
        let metro = element(app, "direction-variant-transit-2")
        XCTAssertTrue(bus.exists)
        XCTAssertTrue(metro.exists, "bus and metro share a page")
        XCTAssertTrue(bus.label.contains("≈ 13 min"), bus.label)
        XCTAssertTrue(bus.label.contains("Arrive 14:35"), bus.label)
        XCTAssertTrue(bus.label.contains("92"))
        XCTAssertTrue(bus.label.contains("≈ 120"), "price")
        XCTAssertTrue(bus.label.contains("Recommended"), "the badge stays on the recommended variant: \(bus.label)")
        XCTAssertTrue(metro.label.contains("Fairly busy"), "congestion shows only when the server sends it")
        XCTAssertFalse(bus.label.contains("traffic"), "no invented congestion")
        XCTAssertTrue(bus.isSelected, "the optimal variant is selected first")
        metro.tap()
        XCTAssertTrue(metro.isSelected)
        XCTAssertFalse(bus.isSelected)

        element(app, "directions-carousel").swipeLeft()
        XCTAssertTrue(element(app, "directions-page-taxi").waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertTrue(element(app, "direction-variant-taxi-1").label.contains("7–11 min"))
        XCTAssertFalse(element(app, "directions-chip-scooter").exists, "modes the server did not return are skipped")
        element(app, "directions-carousel").swipeLeft()
        XCTAssertTrue(element(app, "directions-page-walk").waitForExistence(timeout: 5), "after the last: first")
        XCTAssertTrue(element(app, "direction-variant-walk-2").isSelected, "the choice is kept per page")

        // And back the other way: walk → taxi (wraps backwards) → transit.
        element(app, "directions-carousel").swipeRight()
        XCTAssertTrue(element(app, "directions-page-taxi").waitForExistence(timeout: 5))
        element(app, "directions-carousel").swipeRight()
        XCTAssertTrue(element(app, "directions-page-transit").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "direction-variant-transit-2").isSelected)

        // Chips jump to a page; the pinned buttons are still there.
        element(app, "directions-chip-walk").tap()
        XCTAssertTrue(element(app, "directions-page-walk").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "place-directions").isHittable)
        XCTAssertTrue(element(app, "place-favorite").isHittable)

        element(app, "directions-use-center").tap()
        XCTAssertTrue(element(app, "directions-use-location").waitForExistence(timeout: 5))
        XCTAssertEqual(element(app, "directions-origin").label, "From: map centre")

        element(app, "directions-back").tap()
        XCTAssertTrue(element(app, "place-tab-overview").waitForExistence(timeout: 5))
    }

    func testDeniedLocationFallsBackToMapCenterWithNotice() {
        let app = launch(location: "denied")
        openDirections(app)
        XCTAssertTrue(element(app, "directions-notice-denied").waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(element(app, "directions-origin").label, "From: map centre")
        XCTAssertTrue(element(app, "directions-settings").exists)
        XCTAssertTrue(element(app, "directions-carousel").waitForExistence(timeout: 10))
    }

    func testLocationOutsideAlmatyFallsBack() {
        let app = launch(location: "outside")
        openDirections(app)
        XCTAssertTrue(element(app, "directions-notice-outside").waitForExistence(timeout: 10), app.debugDescription)
    }

    func testRussianStrings() {
        let app = launch(language: "ru")
        openDirections(app)
        XCTAssertTrue(element(app, "directions-page-walk").waitForExistence(timeout: 10), "opens on walking")
        XCTAssertEqual(element(app, "directions-origin").label, "Откуда: ваше местоположение")
        XCTAssertTrue(element(app, "direction-variant-walk-1").label.contains("Бесплатно"),
                      element(app, "direction-variant-walk-1").label)
        element(app, "directions-carousel").swipeLeft()
        XCTAssertTrue(element(app, "direction-variant-transit-1").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "direction-variant-transit-1").label.contains("Будете в 14:35"),
                      element(app, "direction-variant-transit-1").label)
        XCTAssertTrue(element(app, "direction-variant-transit-1").label.contains("Автобус"))
        element(app, "directions-carousel").swipeLeft()
        XCTAssertTrue(element(app, "direction-variant-taxi-1").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "direction-variant-taxi-1").label.contains("7–11 мин"))
        XCTAssertTrue(element(app, "place-directions").label.contains("Маршрут"))
    }
}
