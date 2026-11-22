import XCTest

/// Ш-55, the full route map: replacing a stop and the «All days» view, on the trip fixture of the stub API. The trip
/// is a three-day plan; the alternatives are the stub's gallery, park and a "closed" place that never fits.
@MainActor
final class TripEditUITests: XCTestCase {
    private func launch(dark: Bool = false) -> XCUIApplication {
        XCUIDevice.shared.appearance = dark ? .dark : .light
        addTeardownBlock { XCUIDevice.shared.appearance = .light }
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "-jol.language", "system"]
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

    private func waitGone(_ app: XCUIApplication, _ identifier: String, timeout: TimeInterval = 10,
                          file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(element(app, identifier).waitForNonExistence(timeout: timeout), "\(identifier) is still there",
                      file: file, line: line)
    }

    /// Screenshot into the report and, with `TEST_RUNNER_SHOTS_DIR=<dir>`, into that folder.
    private func shot(_ app: XCUIApplication, _ name: String, dark: Bool = false) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "\(name)-\(dark ? "dark" : "light")"
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = ProcessInfo.processInfo.environment["SHOTS_DIR"], !dir.isEmpty {
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            let file = URL(fileURLWithPath: dir).appendingPathComponent("\(attachment.name ?? name).png")
            try? screenshot.pngRepresentation.write(to: file)
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

    private func openReplace(_ app: XCUIApplication, stop: Int) {
        let button = element(app, "trip-stop-replace-\(stop)")
        XCTAssertTrue(button.waitForExistence(timeout: 10))
        XCTAssertTrue(button.label.contains("Replace"), button.label)
        button.tap()
        waitFor(app, "trip-replace-sheet")
        let options = app.descendants(matching: .any).matching(identifier: "trip-replace-option")
        XCTAssertTrue(options.firstMatch.waitForExistence(timeout: 10), app.debugDescription)
    }

    private func option(_ app: XCUIApplication, _ name: String) -> XCUIElement {
        app.descendants(matching: .any).matching(identifier: "trip-replace-option").matching(
            NSPredicate(format: "label CONTAINS %@", name)
        ).firstMatch
    }

    // MARK: - Replace

    func testReplacingAStopFromItsRow() {
        let app = launch()
        openTrip(app)
        openReplace(app, stop: 2)
        XCTAssertEqual(app.descendants(matching: .any).matching(identifier: "trip-replace-option").count, 3)
        let gallery = option(app, "Fixture Gallery")
        XCTAssertTrue(gallery.label.contains("850 m"), "distance is read: \(gallery.label)")
        XCTAssertTrue(gallery.label.contains("2"), "price is read: \(gallery.label)")
        XCTAssertTrue(element(app, "trip-replace-subject").label.contains("Fixture Cafe"))
        shot(app, "replace-sheet")
        option(app, "Fixture Park").tap()
        waitGone(app, "trip-replace-sheet")
        let stop = element(app, "trip-stop-2")
        let deadline = Date().addingTimeInterval(10)
        while !stop.label.contains("Fixture Park"), Date() < deadline { usleep(200_000) }
        XCTAssertTrue(stop.label.contains("Fixture Park"), "the day reloads with the new place: \(stop.label)")
        XCTAssertFalse(stop.label.contains("Fixture Cafe"))
    }

    func testReplacingAMustHaveAsksFirst() {
        let app = launch()
        openTrip(app)
        openReplace(app, stop: 1)
        option(app, "Fixture Gallery").tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertTrue(app.alerts.firstMatch.label.contains("must-have"), app.alerts.firstMatch.label)
        app.alerts.buttons["Keep it"].firstMatch.tap()
        XCTAssertTrue(element(app, "trip-replace-sheet").exists, "keeping it leaves the sheet open")
        option(app, "Fixture Gallery").tap()
        XCTAssertTrue(app.alerts.firstMatch.waitForExistence(timeout: 10))
        app.alerts.buttons["Replace anyway"].firstMatch.tap()
        waitGone(app, "trip-replace-sheet")
        let stop = element(app, "trip-stop-1")
        let deadline = Date().addingTimeInterval(10)
        while !stop.label.contains("Fixture Gallery"), Date() < deadline { usleep(200_000) }
        XCTAssertTrue(stop.label.contains("Fixture Gallery"), stop.label)
    }

    func testNoReplacementShowsAMessageAndKeepsTheSheet() {
        let app = launch()
        openTrip(app)
        openReplace(app, stop: 2)
        option(app, "Fixture Closed Place").tap()
        waitFor(app, "trip-replace-problem")
        XCTAssertTrue(element(app, "trip-replace-problem").label.contains("No other place"),
                      element(app, "trip-replace-problem").label)
        XCTAssertTrue(element(app, "trip-replace-sheet").exists)
        element(app, "trip-replace-cancel").tap()
        waitGone(app, "trip-replace-sheet")
        XCTAssertTrue(element(app, "trip-stop-2").label.contains("Fixture Cafe"), "nothing changed")
    }

    // MARK: - All days

    func testAllDaysShowsEveryDayGroupedAndLeavesAgain() {
        let app = launch()
        openTrip(app)
        let all = element(app, "trip-day-chip-all")
        XCTAssertTrue(all.waitForExistence(timeout: 10))
        XCTAssertFalse(all.isSelected)
        all.tap()
        waitFor(app, "trip-all-title")
        XCTAssertTrue(element(app, "trip-day-chip-all").isSelected)
        XCTAssertFalse(element(app, "trip-day-chip-1").isSelected)
        XCTAssertTrue(element(app, "trip-all-day-1").exists)
        let firstStop = element(app, "trip-stop-d1-1")
        XCTAssertTrue(firstStop.label.contains("Fixture Museum"), firstStop.label)
        // The second day is under the first: scroll the list to it.
        let list = element(app, "trip-day-list")
        for _ in 0..<5 where !element(app, "trip-stop-d2-2").isHittable { list.swipeUp() }
        XCTAssertTrue(element(app, "trip-all-day-2").exists)
        let dayTwoStop = element(app, "trip-stop-d2-1")
        XCTAssertTrue(dayTwoStop.label.contains("Fixture Cafe"), dayTwoStop.label)
        XCTAssertTrue(element(app, "trip-stop-d2-2").label.contains("Fixture Museum"))
        shot(app, "all-days")

        element(app, "trip-day-chip-2").tap()
        waitGone(app, "trip-all-title")
        XCTAssertTrue(element(app, "trip-day-title").exists)
        XCTAssertTrue(element(app, "trip-stop-1").label.contains("Fixture Cafe"), "day 2 starts with the cafe")
        XCTAssertFalse(element(app, "trip-day-chip-all").isSelected)
    }

    func testEditsWorkFromTheAllDaysList() {
        let app = launch()
        openTrip(app)
        element(app, "trip-day-chip-all").tap()
        waitFor(app, "trip-all-title")
        let replace = element(app, "trip-stop-replace-d1-2")
        XCTAssertTrue(replace.waitForExistence(timeout: 10))
        replace.tap()
        waitFor(app, "trip-replace-sheet")
        XCTAssertTrue(option(app, "Fixture Park").waitForExistence(timeout: 10))
        option(app, "Fixture Park").tap()
        waitGone(app, "trip-replace-sheet")
        let stop = element(app, "trip-stop-d1-2")
        let deadline = Date().addingTimeInterval(10)
        while !stop.label.contains("Fixture Park"), Date() < deadline { usleep(200_000) }
        XCTAssertTrue(stop.label.contains("Fixture Park"), stop.label)
        XCTAssertTrue(element(app, "trip-all-title").exists, "the view stays on «All days»")
    }

    // MARK: - Screenshots (light and dark)

    func testScreenshotsLightAndDark() {
        for dark in [false, true] {
            let app = launch(dark: dark)
            openTrip(app)
            shot(app, "trip-day", dark: dark)
            element(app, "trip-day-chip-all").tap()
            waitFor(app, "trip-all-title")
            shot(app, "trip-all-days", dark: dark)
            element(app, "trip-day-chip-1").tap()
            waitGone(app, "trip-all-title")
            openReplace(app, stop: 2)
            shot(app, "trip-replace", dark: dark)
            app.terminate()
        }
    }
}
