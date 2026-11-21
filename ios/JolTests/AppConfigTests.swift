@testable import Jol
import XCTest

final class AppConfigTests: XCTestCase {
    func testEmptyConfigFallsBackToBundledStyle() {
        let url = AppConfig.resolveStyleURL(configured: "", bundle: .main)
        XCTAssertTrue(url.isFileURL)
        XCTAssertEqual(url.lastPathComponent, "placeholder-style.json")
    }

    func testConfiguredURLIsUsed() {
        let url = AppConfig.resolveStyleURL(configured: "https://example.com/style.json", bundle: .main)
        XCTAssertEqual(url.absoluteString, "https://example.com/style.json")
    }

    func testAlmatyCamera() {
        XCTAssertEqual(AlmatyCamera.center.latitude, 43.2380, accuracy: 0.001)
    }
}
