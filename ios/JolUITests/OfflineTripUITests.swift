import XCTest

/// Ш-42 (SSOT §7.4): a trip downloaded while online opens without a network, with all its days and times.
/// The first launch downloads the trip from the stub API; the second launch makes every request fail like a missing
/// connection (`-JolStubOffline`), so everything on screen comes from the copy kept on the device.
@MainActor
final class OfflineTripUITests: XCTestCase {
    private func launch(_ extra: [String]) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-JolStubSignedIn", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "-jol.language", "system"] + extra
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

    private func openSidebar(_ app: XCUIApplication) {
        let open = app.buttons["open-sidebar"]
        XCTAssertTrue(open.waitForExistence(timeout: 10))
        open.tap()
    }

    func testADownloadedTripOpensWithoutANetworkWithAllItsTimes() {
        // Online: download from "My trips".
        let online = launch(["-JolResetOffline"])
        openSidebar(online)
        let download = element(online, "sidebar-trip-download")
        XCTAssertTrue(download.waitForExistence(timeout: 10), online.debugDescription)
        XCTAssertEqual(download.label, "Download route")
        download.tap()
        let saved = NSPredicate(format: "label == %@", "Route downloaded")
        XCTAssertEqual(XCTWaiter().wait(for: [XCTNSPredicateExpectation(predicate: saved, object: download)],
                                        timeout: 10), .completed, "the trip was never marked as downloaded")
        online.terminate()

        // Offline: the saved trip is listed and opens from the copy.
        let app = launch(["-JolStubOffline"])
        openSidebar(app)
        let row = element(app, "sidebar-trip-row")
        XCTAssertTrue(row.waitForExistence(timeout: 10), "a saved trip is listed without a network")
        row.tap()
        waitFor(app, "trip-map")
        waitFor(app, "trip-stop-1")
        waitFor(app, "trip-offline-note")

        // Day 1: both stops with their times, and the leg between them.
        let first = element(app, "trip-stop-1").label
        XCTAssertTrue(first.contains("Fixture Museum") && first.contains("09:30–11:00"), first)
        let second = element(app, "trip-stop-2").label
        XCTAssertTrue(second.contains("Fixture Cafe") && second.contains("12:00–13:30"), second)
        waitFor(app, "trip-leg-row")
        XCTAssertFalse(element(app, "trip-stop-remove-1").exists, "a saved copy is read-only")

        // Day 2 is there too.
        element(app, "trip-day-chip-2").tap()
        let other = element(app, "trip-stop-1").label
        XCTAssertTrue(other.contains("Fixture Cafe") && other.contains("10:00–11:30"), other)
        element(app, "trip-day-chip-1").tap()

        // The place card comes from the saved copy as well.
        element(app, "trip-stop-1").tap()
        waitFor(app, "offline-place-name")
        XCTAssertEqual(element(app, "offline-place-name").label, "Fixture Museum")
        waitFor(app, "offline-place-address")
        XCTAssertTrue(element(app, "offline-place-address").label.contains("1 Test Street"))
        XCTAssertTrue(element(app, "offline-place-hours").label.contains("10:00–18:00"))
        XCTAssertTrue(element(app, "offline-place-time").label.contains("09:30"))
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = "offline-place-card"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
