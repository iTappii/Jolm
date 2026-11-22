import XCTest

/// Ш-55: «My bookings» (list, detail, cancel with a confirmation, 409 `not_cancellable`) and the accessibility pass
/// over the side panel and the profile screens: dark theme and Dynamic Type AX3, on the stub API. The theme is the
/// device's (`XCUIDevice.shared.appearance`, reset to light afterwards).
@MainActor
final class ProfileBookingsUITests: XCTestCase {
    private enum Look: String, CaseIterable {
        case light
        case dark
        case lightAX3 = "light-ax3"
        case darkAX3 = "dark-ax3"

        var isDark: Bool { self == .dark || self == .darkAX3 }
        var isLarge: Bool { self == .lightAX3 || self == .darkAX3 }
    }

    private func launch(dark: Bool = false, large: Bool = false, signedIn: Bool = true,
                        language: String = "en") -> XCUIApplication {
        XCUIDevice.shared.appearance = dark ? .dark : .light
        addTeardownBlock { XCUIDevice.shared.appearance = .light }
        let app = XCUIApplication()
        app.launchArguments = ["-JolStubAPI", "-AppleLanguages", "(\(language))", "-AppleLocale",
                               language == "ru" ? "ru_RU" : "en_US", "-jol.language", "system"]
        if large {
            // Accessibility 3 (AX3).
            app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXL"]
        }
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

    private func waitGone(_ app: XCUIApplication, _ identifier: String, timeout: TimeInterval = 10,
                          file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(app.buttons[identifier].firstMatch.waitForNonExistence(timeout: timeout),
                      "\(identifier) is still there", file: file, line: line)
    }

    private func shot(_ app: XCUIApplication, _ name: String, _ suffix: String) {
        let screenshot = app.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "\(name)-\(suffix)"
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = ProcessInfo.processInfo.environment["SHOTS_DIR"], !dir.isEmpty {
            try? FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            let file = URL(fileURLWithPath: dir).appendingPathComponent("\(name)-\(suffix).png")
            try? screenshot.pngRepresentation.write(to: file)
        }
    }

    /// A control a finger can hit: exists, hittable and at least 44 × 44 pt (42 allows for the sheet drag).
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

    /// Swipes the container up until the element is on screen (large type pushes rows below the fold).
    private func reveal(_ app: XCUIApplication, _ identifier: String, in container: String) {
        let target = element(app, identifier)
        for _ in 0..<6 where !(target.exists && target.isHittable) {
            element(app, container).swipeUp()
        }
    }

    /// A button of the confirmation dialog by its identifier, waiting for the dialog to come up.
    private func dialogButton(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        let button = app.buttons[identifier].firstMatch
        _ = button.waitForExistence(timeout: 5)
        return button
    }

    /// Closes the dialog without choosing: on this iOS it is a popover with no cancel button (tap outside it), on a
    /// sheet there is a «Cancel» button.
    private func dismissDialog(_ app: XCUIApplication) {
        let outside = app.otherElements["PopoverDismissRegion"].firstMatch
        if outside.waitForExistence(timeout: 3) {
            outside.tap()
        } else {
            app.buttons["Cancel"].firstMatch.tap()
        }
    }

    private func openProfile(_ app: XCUIApplication) {
        let profile = app.buttons["open-profile-menu"]
        XCTAssertTrue(profile.waitForExistence(timeout: 10))
        profile.tap()
        waitFor(app, "profile-menu")
    }

    private func rows(_ app: XCUIApplication) -> XCUIElementQuery {
        app.descendants(matching: .any).matching(identifier: "bookings-row")
    }

    private func openBookings(_ app: XCUIApplication) {
        openProfile(app)
        let entry = element(app, "profile-bookings")
        XCTAssertTrue(entry.waitForExistence(timeout: 10), app.debugDescription)
        entry.tap()
        waitFor(app, "bookings-screen")
        XCTAssertTrue(rows(app).firstMatch.waitForExistence(timeout: 10), app.debugDescription)
    }

    // MARK: - Bookings

    func testBookingsListShowsStatusPlaceAndTimeAndGuestsHaveNoEntry() {
        let guest = launch(signedIn: false)
        openProfile(guest)
        XCTAssertFalse(element(guest, "profile-bookings").exists, "a guest has no bookings")
        guest.terminate()

        let app = launch()
        openBookings(app)
        XCTAssertEqual(rows(app).count, 3)
        let first = rows(app).element(boundBy: 0).label
        XCTAssertTrue(first.contains("Fixture Cafe"), first)
        XCTAssertTrue(first.contains("Table"), first)
        XCTAssertTrue(first.contains("19:00"), first)
        XCTAssertTrue(first.contains("Confirmed"), first)
        let second = rows(app).element(boundBy: 1).label
        XCTAssertTrue(second.contains("Fixture Museum") && second.contains("Waiting for the venue"), second)
    }

    func testCancellingABookingAsksFirstThenShowsItCancelled() {
        let app = launch()
        openBookings(app)
        rows(app).element(boundBy: 0).tap()
        waitFor(app, "booking-detail")
        XCTAssertEqual(element(app, "booking-detail-status").label, "Confirmed")
        XCTAssertTrue(element(app, "booking-detail-when").label.contains("19:00"))
        shot(app, "booking-detail", "light")

        element(app, "booking-cancel").tap()
        XCTAssertTrue(dialogButton(app, "booking-cancel-confirm").exists, app.debugDescription)
        dismissDialog(app)
        waitGone(app, "booking-cancel-confirm")
        XCTAssertEqual(element(app, "booking-detail-status").label, "Confirmed", "keeping it changes nothing")

        element(app, "booking-cancel").tap()
        dialogButton(app, "booking-cancel-confirm").tap()
        let status = element(app, "booking-detail-status")
        let deadline = Date().addingTimeInterval(10)
        while status.label != "Cancelled", Date() < deadline { usleep(200_000) }
        XCTAssertEqual(status.label, "Cancelled")
        XCTAssertFalse(element(app, "booking-cancel").exists, "a cancelled booking has no cancel button")

        app.navigationBars.buttons.firstMatch.tap()
        waitFor(app, "bookings-screen")
        XCTAssertTrue(rows(app).element(boundBy: 0).label.contains("Cancelled"), rows(app).element(boundBy: 0).label)
    }

    func testABookingThatCannotBeCancelledAnyMoreExplainsWhy() {
        let app = launch()
        openBookings(app)
        rows(app).element(boundBy: 2).tap()
        waitFor(app, "booking-detail")
        element(app, "booking-cancel").tap()
        dialogButton(app, "booking-cancel-confirm").tap()
        waitFor(app, "booking-cancel-problem")
        let message = element(app, "booking-cancel-problem").label
        XCTAssertTrue(message.contains("can't be cancelled any more"), message)
        XCTAssertEqual(element(app, "booking-detail-status").label, "Confirmed", "the booking stays as it is")
        shot(app, "booking-not-cancellable", "light")
    }

    func testBookingsAreLocalizedInRussian() {
        let app = launch(language: "ru")
        openBookings(app)
        XCTAssertTrue(app.navigationBars["Мои брони"].exists, app.debugDescription)
        XCTAssertTrue(rows(app).element(boundBy: 0).label.contains("Подтверждено"), rows(app).element(boundBy: 0).label)
    }

    // MARK: - Accessibility: dark theme and AX3

    func testBookingsAtLargeTypeAndDark() {
        for look in Look.allCases {
            let app = launch(dark: look.isDark, large: look.isLarge)
            openBookings(app)
            let row = rows(app).element(boundBy: 0)
            XCTAssertTrue(row.isHittable)
            XCTAssertGreaterThanOrEqual(row.frame.height, 44)
            shot(app, "bookings", look.rawValue)
            row.tap()
            waitFor(app, "booking-detail")
            reveal(app, "booking-cancel", in: "booking-detail")
            assertTarget(app, "booking-cancel")
            shot(app, "booking-detail", look.rawValue)
            app.terminate()
        }
    }

    func testProfileMenuAndScreensAtLargeTypeAndDark() {
        for look in Look.allCases {
            let app = launch(dark: look.isDark, large: look.isLarge)
            openProfile(app)
            for identifier in ["profile-bookings", "profile-settings"] {
                assertTarget(app, identifier)
            }
            XCTAssertTrue(element(app, "profile-identity").label.contains("tourist@example.com"))
            shot(app, "profile-menu", look.rawValue)
            for identifier in ["profile-language", "profile-help", "profile-about"] {
                reveal(app, identifier, in: "profile-menu")
                assertTarget(app, identifier)
            }
            reveal(app, "profile-delete-account", in: "profile-menu")
            assertTarget(app, "profile-sign-out")
            assertTarget(app, "profile-delete-account")
            shot(app, "profile-menu-bottom", look.rawValue)
            // The deletion flow: the confirmation names what happens and offers a way back.
            element(app, "profile-delete-account").tap()
            XCTAssertTrue(dialogButton(app, "delete-confirm").waitForExistence(timeout: 5), app.debugDescription)
            shot(app, "profile-delete-dialog", look.rawValue)
            dismissDialog(app)
            XCTAssertTrue(element(app, "profile-menu").exists, "cancelling keeps the account and the menu")
            // Sub-screens.
            element(app, "profile-language").tap()
            waitFor(app, "language-en")
            assertTarget(app, "language-en")
            assertTarget(app, "language-ru")
            XCTAssertTrue(element(app, "language-en").isSelected || element(app, "language-system").isSelected)
            shot(app, "profile-language", look.rawValue)
            app.navigationBars.buttons.firstMatch.tap()
            reveal(app, "profile-about", in: "profile-menu")
            element(app, "profile-about").tap()
            waitFor(app, "about-screen")
            shot(app, "profile-about", look.rawValue)
            app.terminate()
        }
    }

    func testSidebarAtLargeTypeAndDark() {
        for look in Look.allCases {
            let app = launch(dark: look.isDark, large: look.isLarge)
            let open = app.buttons["open-sidebar"]
            XCTAssertTrue(open.waitForExistence(timeout: 10))
            open.tap()
            waitFor(app, "sidebar-panel")
            for identifier in ["sidebar-close", "sidebar-new-chat", "sidebar-routes", "sidebar-favorites"] {
                assertTarget(app, identifier)
            }
            reveal(app, "sidebar-trip-row", in: "sidebar-panel")
            let trip = app.buttons.matching(identifier: "sidebar-trip-row").firstMatch
            XCTAssertTrue(trip.waitForExistence(timeout: 10), app.debugDescription)
            XCTAssertGreaterThanOrEqual(trip.frame.height, 42)
            XCTAssertTrue(trip.label.contains("Dec"), "the row reads its dates: \(trip.label)")
            assertTarget(app, "sidebar-trip-download")
            shot(app, "sidebar", look.rawValue)
            reveal(app, "sidebar-chat-row", in: "sidebar-panel")
            let chat = app.buttons.matching(identifier: "sidebar-chat-row").firstMatch
            XCTAssertTrue(chat.waitForExistence(timeout: 10))
            XCTAssertTrue(chat.isHittable)
            XCTAssertGreaterThanOrEqual(chat.frame.height, 42)
            shot(app, "sidebar-chats", look.rawValue)
            app.terminate()
        }
    }

    func testGuestSidebarHintIsATarget() {
        let app = launch(dark: true, large: true, signedIn: false)
        app.buttons["open-sidebar"].tap()
        waitFor(app, "sidebar-panel")
        reveal(app, "sidebar-guest-hint", in: "sidebar-panel")
        assertTarget(app, "sidebar-guest-hint")
        shot(app, "sidebar-guest", "dark-ax3")
    }
}
