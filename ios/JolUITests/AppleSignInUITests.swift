import XCTest

/// Needs a real Apple ID in the simulator (and a paid developer account for the capability); not part of CI.
@MainActor
final class AppleSignInUITests: XCTestCase {
    func testProfileMenuOpensAppleSignIn() {
        let app = XCUIApplication()
        app.launch()

        let profile = app.buttons["open-profile-menu"]
        XCTAssertTrue(profile.waitForExistence(timeout: 10))
        profile.tap()

        let signIn = app.buttons["profile-sign-in"]
        XCTAssertTrue(signIn.waitForExistence(timeout: 5))
        signIn.tap()

        let sheet = app.descendants(matching: .any)["apple-sign-in"].firstMatch
        XCTAssertTrue(sheet.waitForExistence(timeout: 5))
    }
}
