import XCTest

/// Runs against the debug-only feature gallery (`-JolFeatureGallery`).
@MainActor
final class FeatureGalleryUITests: XCTestCase {
    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolFeatureGallery", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "-jol.language", "system"]
        app.launch()
        return app
    }

    func testLanguageSwitchesAtRuntimeWithoutRestart() {
        let app = launch()
        XCTAssertTrue(app.buttons["Chat"].waitForExistence(timeout: 10))

        app.segmentedControls["language-picker"].buttons["Русский"].tap()
        XCTAssertTrue(app.buttons["Чат"].waitForExistence(timeout: 5), "list switched to Russian")
        XCTAssertFalse(app.buttons["Chat"].exists)

        app.buttons["Профиль"].tap()
        XCTAssertTrue(app.navigationBars["Профиль"].waitForExistence(timeout: 5), "pushed screen is Russian too")
        app.navigationBars.buttons.firstMatch.tap()

        app.segmentedControls["language-picker"].buttons["English"].tap()
        XCTAssertTrue(app.buttons["Chat"].waitForExistence(timeout: 5), "back to English")
    }

    /// Needs `make run` (API on localhost:8000); skipped when the server is not reachable.
    func testServerStatusShowsMetaVersion() async throws {
        let probe = URL(string: "http://localhost:8000/v1/meta")!
        guard let (_, response) = try? await URLSession.shared.data(from: probe),
              (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw XCTSkip("local API is not running")
        }
        let app = launch()
        let status = app.staticTexts["server-status"]
        XCTAssertTrue(status.waitForExistence(timeout: 10))
        XCTAssertTrue(status.label.hasPrefix("Server "), "got: \(status.label)")
    }
}
