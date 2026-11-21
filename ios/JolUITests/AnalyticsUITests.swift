import XCTest

/// Ш-50: starting a route in a navigator must not disturb the app (the event itself is queued and flushed in the
/// background; its content is checked by `AnalyticsTests`). The stub API logs every `/v1/analytics/events` call as
/// `JolStub …` (readable with `xcrun simctl spawn booted log show`), which is how the wiring was checked by hand.
@MainActor
final class AnalyticsUITests: XCTestCase {
    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    func testOpeningTheNavigatorFromDirectionsKeepsTheAppWorking() {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "-jol.language", "system"]
        app.launch()
        let collapse = app.buttons["chat-collapse"]
        XCTAssertTrue(collapse.waitForExistence(timeout: 10))
        collapse.tap()
        let card = element(app, "place-card")
        for _ in 0..<12 where !card.exists {
            app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
            _ = card.waitForExistence(timeout: 1.5)
        }
        XCTAssertTrue(card.exists, app.debugDescription)
        element(app, "place-directions").tap()
        XCTAssertTrue(element(app, "directions-panel").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "directions-page-walk").waitForExistence(timeout: 10))

        let navigator = element(app, "place-navigator")
        XCTAssertTrue(navigator.waitForExistence(timeout: 5))
        navigator.tap()
        app.activate()
        XCTAssertTrue(element(app, "directions-panel").waitForExistence(timeout: 10), "the app is still there")
    }
}
