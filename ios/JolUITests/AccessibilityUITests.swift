import XCTest

/// Ш-52 accessibility pass over the full route map, directions, events, booking and ready-made routes: dark theme
/// and the largest Dynamic Type sizes (accessibility XXXL), on the stub API. Each test checks that the key controls
/// are on screen, hittable, at least 44 pt, and that the VoiceOver labels carry what the sighted user reads;
/// screenshots are attached (light / dark / large type) for the review.
@MainActor
final class AccessibilityUITests: XCTestCase {
    private enum Look: String, CaseIterable {
        case lightLarge = "light-axxxl"
        case darkLarge = "dark-axxxl"
        case dark = "dark"

        var arguments: [String] {
            switch self {
            case .lightLarge:
                ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
            case .darkLarge:
                ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
            case .dark:
                []
            }
        }

        var appearance: XCUIDevice.Appearance { self == .lightLarge ? .light : .dark }
    }

    private func launch(_ look: Look, extra: [String] = [], signedIn: Bool = true) -> XCUIApplication {
        // The system appearance is switched on the device: the app has no override of its own.
        XCUIDevice.shared.appearance = look.appearance
        addTeardownBlock { XCUIDevice.shared.appearance = .light }
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(en)", "-AppleLocale", "en_US", "-jol.language",
                               "system"] + look.arguments + extra
        if signedIn { app.launchArguments.append("-JolStubSignedIn") }
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

    private func capture(_ name: String, _ look: Look) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = "\(name)-\(look.rawValue)"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// A control a finger can hit: on screen, hittable and 44 × 44 pt. The floor is 42: inside a sheet that is being
    /// dragged the simulator reports 44-pt frames as 42.4 (seen on `directions-back`, a plain 44-pt frame).
    private func assertTarget(_ app: XCUIApplication, _ identifier: String,
                              file: StaticString = #filePath, line: UInt = #line) {
        let item = element(app, identifier)
        XCTAssertTrue(item.waitForExistence(timeout: 10), "\(identifier) missing", file: file, line: line)
        XCTAssertTrue(item.isHittable, "\(identifier) is not hittable", file: file, line: line)
        XCTAssertGreaterThanOrEqual(item.frame.height, 42, "\(identifier) is \(item.frame.height) pt high",
                                    file: file, line: line)
        XCTAssertGreaterThanOrEqual(item.frame.width, 42, "\(identifier) is \(item.frame.width) pt wide",
                                    file: file, line: line)
    }

    /// Text that is not cut off horizontally: its frame stays inside the window.
    private func assertInsideScreen(_ app: XCUIApplication, _ identifier: String,
                                    file: StaticString = #filePath, line: UInt = #line) {
        let item = element(app, identifier)
        XCTAssertTrue(item.exists, "\(identifier) missing", file: file, line: line)
        let window = app.windows.firstMatch.frame
        XCTAssertGreaterThanOrEqual(item.frame.minX, window.minX - 1, "\(identifier) sticks out left",
                                    file: file, line: line)
        XCTAssertLessThanOrEqual(item.frame.maxX, window.maxX + 1, "\(identifier) sticks out right",
                                 file: file, line: line)
    }

    /// Drags the panel / sheet up until the element shows (large type pushes content below the fold).
    private func raise(_ app: XCUIApplication, _ container: String, until identifier: String) {
        let target = element(app, identifier)
        for _ in 0..<4 where !(target.exists && target.isHittable) {
            element(app, container).swipeUp()
        }
    }

    private func openTrip(_ app: XCUIApplication) {
        let open = app.buttons["open-sidebar"]
        XCTAssertTrue(open.waitForExistence(timeout: 10))
        open.tap()
        let row = element(app, "sidebar-trip-row")
        XCTAssertTrue(row.waitForExistence(timeout: 10), app.debugDescription)
        row.tap()
        waitFor(app, "trip-map")
        waitFor(app, "trip-stop-1")
    }

    private func openMuseum(_ app: XCUIApplication) {
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
    }

    // MARK: - Full route map

    func testTripMapAndLegSheet() {
        for look in Look.allCases {
            let app = launch(look)
            openTrip(app)
            assertTarget(app, "trip-map-close")
            assertTarget(app, "trip-day-chip-1")
            assertTarget(app, "trip-budget-chip")
            raise(app, "trip-panel", until: "trip-stop-remove-1")
            assertTarget(app, "trip-stop-remove-1")
            let budget = element(app, "trip-budget-chip").label
            XCTAssertTrue(budget.contains("Budget"), budget)
            XCTAssertTrue(element(app, "trip-stop-1").label.contains("Fixture Museum"))
            assertInsideScreen(app, "trip-stop-1")
            capture("trip-map", look)

            let leg = element(app, "trip-leg-row")
            raise(app, "trip-panel", until: "trip-leg-row")
            XCTAssertTrue(leg.waitForExistence(timeout: 10))
            let spoken = leg.label
            XCTAssertTrue(spoken.contains("min"), "a leg reads its time: \(spoken)")
            leg.tap()
            waitFor(app, "trip-leg-sheet")
            raise(app, "trip-leg-sheet", until: "trip-leg-option-bus")
            assertTarget(app, "trip-leg-option-bus")
            XCTAssertTrue(element(app, "trip-leg-option-bus").label.contains("min"))
            XCTAssertTrue(element(app, "trip-leg-option-bus").isSelected)
            assertInsideScreen(app, "trip-leg-option-bus")
            capture("trip-leg-sheet", look)
            app.terminate()
        }
    }

    func testBudgetSheetAtLargeType() {
        let look = Look.darkLarge
        let app = launch(look)
        openTrip(app)
        let warning = element(app, "trip-over-budget")
        raise(app, "trip-panel", until: "trip-over-budget")
        waitFor(app, "trip-over-budget")
        capture("trip-over-budget", look)
        warning.tap()
        waitFor(app, "trip-budget-sheet")
        assertInsideScreen(app, "trip-budget-over")
        capture("trip-budget-sheet", look)
    }

    // MARK: - Directions

    func testDirectionsPanel() {
        for look in Look.allCases {
            let app = launch(look, signedIn: false)
            openMuseum(app)
            let button = element(app, "place-directions")
            XCTAssertTrue(button.waitForExistence(timeout: 10), app.debugDescription)
            if !button.isHittable { element(app, "place-card").swipeUp() }
            button.tap()
            waitFor(app, "directions-panel")
            waitFor(app, "directions-page-walk")
            raise(app, "directions-panel", until: "directions-use-center")
            assertTarget(app, "directions-back")
            assertTarget(app, "directions-chip-walk")
            assertTarget(app, "directions-use-center")
            let chip = element(app, "directions-chip-walk").label
            XCTAssertTrue(chip.contains("Walk") && chip.contains("min"), "a chip reads mode and time: \(chip)")
            let variant = element(app, "direction-variant-walk-1")
            let spoken = variant.label
            XCTAssertTrue(spoken.contains("Walk") && spoken.contains("min") && spoken.contains("Free"), spoken)
            XCTAssertTrue(spoken.contains("Arrive"), "a variant reads the arrival time: \(spoken)")
            XCTAssertTrue(variant.isSelected)
            assertInsideScreen(app, "direction-variant-walk-1")
            capture("directions", look)
            app.terminate()
        }
    }

    // MARK: - Events

    func testEventCard() {
        for look in Look.allCases {
            let app = launch(look, extra: ["-JolStubSelectEvent"])
            waitFor(app, "event-card")
            XCTAssertEqual(element(app, "event-title").label, "Fixture Jazz Night")
            XCTAssertEqual(element(app, "event-ad-label").label, "Ad")
            assertInsideScreen(app, "event-title")
            assertInsideScreen(app, "event-when")
            capture("event-card", look)
            app.terminate()
        }
    }

    // MARK: - Booking

    func testBookingSheet() {
        for look in Look.allCases {
            let app = launch(look)
            openTrip(app)
            raise(app, "trip-panel", until: "trip-stop-2")
            element(app, "trip-stop-2").tap()
            waitFor(app, "place-card")
            let book = element(app, "place-book")
            if !book.isHittable { element(app, "place-card").swipeUp() }
            book.tap()
            waitFor(app, "booking-sheet")
            XCTAssertTrue(element(app, "booking-close").isHittable, "the system close button")
            capture("booking-form", look)
            let submit = element(app, "booking-submit")
            for _ in 0..<4 where !submit.isHittable { element(app, "booking-sheet").swipeUp() }
            assertTarget(app, "booking-submit")
            submit.tap()
            waitFor(app, "booking-result")
            XCTAssertEqual(element(app, "booking-status").label, "Confirmed")
            assertInsideScreen(app, "booking-status")
            capture("booking-result", look)
            app.terminate()
        }
    }

    // MARK: - Ready-made routes

    func testReadyMadeRoutes() {
        for look in Look.allCases {
            let app = launch(look)
            let open = app.buttons["open-sidebar"]
            XCTAssertTrue(open.waitForExistence(timeout: 10))
            open.tap()
            let entry = app.buttons["sidebar-routes"]
            XCTAssertTrue(entry.waitForExistence(timeout: 5))
            entry.tap()
            let row = app.buttons["route-row"].firstMatch
            XCTAssertTrue(row.waitForExistence(timeout: 10), app.debugDescription)
            XCTAssertTrue(element(app, "routes-done").isHittable, "the system «Done» button")
            capture("routes-list", look)
            row.tap()
            waitFor(app, "route-bar")
            assertTarget(app, "route-close")
            assertTarget(app, "route-stop-1")
            assertInsideScreen(app, "route-title")
            capture("route-bar", look)
            app.terminate()
        }
    }
}
