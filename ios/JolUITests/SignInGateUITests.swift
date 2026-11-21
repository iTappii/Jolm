import XCTest

/// Ш-28. The registration gate and the e-mail code flow on stubbed API (`-JolStubAPI`: any address gets a code,
/// `123456` is the right one, `ratelimit@…` gets a 429).
@MainActor
final class SignInGateUITests: XCTestCase {
    private func launch() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(en)", "-AppleLocale", "en_US",
                               "-jol.language", "system"]
        app.launch()
        return app
    }

    private func element(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier].firstMatch
    }

    private func typeDraft(_ app: XCUIApplication, _ text: String) {
        let input = element(app, "chat-input")
        XCTAssertTrue(input.waitForExistence(timeout: 10))
        input.tap()
        input.typeText(text)
    }

    private func enter(_ app: XCUIApplication, _ identifier: String, _ text: String) {
        let field = element(app, identifier)
        XCTAssertTrue(field.waitForExistence(timeout: 5), app.debugDescription)
        field.tap()
        field.typeText(text)
    }

    func testGuestAskingForAPersonalTripIsAskedToSignInAndDraftSurvives() {
        let app = launch()
        typeDraft(app, "Three days in Almaty")
        element(app, "chat-send").tap()

        XCTAssertTrue(element(app, "account-gate").waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertTrue(element(app, "sign-in-reason").exists)
        XCTAssertTrue(element(app, "sign-in-apple-disabled").exists, "Apple is off in this build, with an explanation")
        XCTAssertFalse(element(app, "apple-sign-in").exists)
        XCTAssertFalse(element(app, "chat-message-user").exists, "the flow does not continue before sign-in")

        // Step 1: e-mail.
        XCTAssertFalse(element(app, "sign-in-send").isEnabled, "empty address")
        enter(app, "sign-in-destination", "tourist@example.com")
        element(app, "sign-in-send").tap()

        // Step 2: code. A wrong one shows an error and stays a guest.
        XCTAssertTrue(element(app, "sign-in-code").waitForExistence(timeout: 5), app.debugDescription)
        XCTAssertTrue(element(app, "sign-in-code-sent").label.contains("tourist@example.com"))
        XCTAssertFalse(element(app, "sign-in-resend").isEnabled, "resend waits for the countdown")
        XCTAssertTrue(element(app, "sign-in-resend").label.contains("Resend in"), element(app, "sign-in-resend").label)
        element(app, "sign-in-code").typeText("000000")
        XCTAssertTrue(element(app, "sign-in-error").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "sign-in-error").label.contains("Wrong code"))

        element(app, "sign-in-code").typeText("111111")
        XCTAssertTrue(element(app, "sign-in-error").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "sign-in-error").label.contains("Code expired"), element(app, "sign-in-error").label)

        // The right code signs in, closes the sheet and continues the flow with the draft intact.
        element(app, "sign-in-code").typeText("123456")
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, "account-gate"))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 10), .completed, app.debugDescription)
        // The flow continues: the draft became the first message of a saved chat and the field is empty again.
        let message = element(app, "chat-message-user")
        XCTAssertTrue(message.waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(message.label, "Three days in Almaty")
        XCTAssertNotEqual(element(app, "chat-input").value as? String, "Three days in Almaty")
    }

    func testCancellingTheGateKeepsDraftAndDoesNotContinue() {
        let app = launch()
        typeDraft(app, "Plan a weekend")
        element(app, "chat-send").tap()
        XCTAssertTrue(element(app, "gate-cancel").waitForExistence(timeout: 5))
        element(app, "gate-cancel").tap()
        let gone = XCTNSPredicateExpectation(predicate: NSPredicate(format: "exists == false"),
                                             object: element(app, "account-gate"))
        XCTAssertEqual(XCTWaiter().wait(for: [gone], timeout: 5), .completed)
        XCTAssertFalse(element(app, "chat-message-user").exists)
        XCTAssertEqual(element(app, "chat-input").value as? String, "Plan a weekend")
    }

    func testRateLimitedAddressShowsCountdownMessage() {
        let app = launch()
        typeDraft(app, "Plan a trip")
        element(app, "chat-send").tap()
        enter(app, "sign-in-destination", "ratelimit@example.com")
        element(app, "sign-in-send").tap()
        XCTAssertTrue(element(app, "sign-in-error").waitForExistence(timeout: 5), app.debugDescription)
        let message = element(app, "sign-in-error").label
        XCTAssertTrue(message.contains("Too many attempts"), message)
    }

    func testSignInFromProfileMenuOffersPhoneAndValidatesLocally() {
        let app = launch()
        let profile = app.buttons["open-profile-menu"]
        XCTAssertTrue(profile.waitForExistence(timeout: 10))
        profile.tap()
        let entry = app.buttons["profile-sign-in"]
        XCTAssertTrue(entry.waitForExistence(timeout: 5))
        entry.tap()
        XCTAssertTrue(element(app, "sign-in-entry").waitForExistence(timeout: 5))

        app.buttons["Phone"].tap()
        enter(app, "sign-in-destination", "12345")
        element(app, "sign-in-send").tap()
        XCTAssertTrue(element(app, "sign-in-error").waitForExistence(timeout: 5))
        XCTAssertTrue(element(app, "sign-in-error").label.contains("doesn't look right"))
    }
}
