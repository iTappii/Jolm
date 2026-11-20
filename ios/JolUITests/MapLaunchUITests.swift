import XCTest

final class MapLaunchUITests: XCTestCase {
    func testLaunchShowsAttribution() {
        let app = XCUIApplication()
        app.launch()
        XCTAssertTrue(app.staticTexts["osm-attribution"].waitForExistence(timeout: 10))
    }
}
