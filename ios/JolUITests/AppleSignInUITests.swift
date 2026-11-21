import XCTest

final class AppleSignInUITests: XCTestCase {
    func testProfileOpensAppleSignIn() {
        let app = XCUIApplication()
        app.launch()

        let profile = app.buttons["open-apple-sign-in"]
        XCTAssertTrue(profile.waitForExistence(timeout: 10))
        profile.tap()

        let sheet = app.descendants(matching: .any)["apple-sign-in"].firstMatch
        XCTAssertTrue(sheet.waitForExistence(timeout: 5))
    }
}
