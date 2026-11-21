@testable import Jol
import XCTest

final class InstallIDTests: XCTestCase {
    func testGeneratedOnceAndPersisted() throws {
        let suite = "jol.tests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let first = InstallID.current(defaults: defaults)
        XCTAssertNotNil(UUID(uuidString: first))
        XCTAssertEqual(InstallID.current(defaults: defaults), first)
    }

    func testCorruptedValueIsReplaced() throws {
        let suite = "jol.tests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        defaults.set("not-a-uuid", forKey: InstallID.key)
        XCTAssertNotNil(UUID(uuidString: InstallID.current(defaults: defaults)))
    }
}

final class APIBaseURLTests: XCTestCase {
    func testHTTPSAlwaysAllowed() throws {
        let url = try AppConfig.resolveAPIBaseURL(configured: "https://api.jol.kz", allowLocalHTTP: false).get()
        XCTAssertEqual(url.host, "api.jol.kz")
    }

    func testLocalHTTPOnlyWhenAllowed() {
        let local = "http://localhost:8000"
        XCTAssertNotNil(try? AppConfig.resolveAPIBaseURL(configured: local, allowLocalHTTP: true).get())
        XCTAssertNil(try? AppConfig.resolveAPIBaseURL(configured: local, allowLocalHTTP: false).get())
        XCTAssertNil(try? AppConfig.resolveAPIBaseURL(configured: "http://example.com", allowLocalHTTP: true).get())
    }

    func testMissingOrEmpty() {
        XCTAssertNil(try? AppConfig.resolveAPIBaseURL(configured: nil).get())
        XCTAssertNil(try? AppConfig.resolveAPIBaseURL(configured: "").get())
    }
}

@MainActor
final class LanguageTests: XCTestCase {
    private func makeDefaults() throws -> UserDefaults {
        let suite = "jol.tests.\(UUID().uuidString)"
        return try XCTUnwrap(UserDefaults(suiteName: suite))
    }

    func testSystemResolvesToSupportedLanguage() {
        XCTAssertEqual(AppLanguage.system.resolvedCode(preferred: ["ru-KZ", "en-US"]), "ru")
        XCTAssertEqual(AppLanguage.system.resolvedCode(preferred: ["en-GB"]), "en")
        XCTAssertEqual(AppLanguage.system.resolvedCode(preferred: ["de-DE"]), "en", "fallback")
    }

    func testOverridePersistsAndChangesLocale() throws {
        let defaults = try makeDefaults()
        let settings = LanguageSettings(defaults: defaults)
        XCTAssertEqual(settings.selection, .system)
        settings.selection = .russian
        XCTAssertEqual(settings.locale.identifier, "ru")
        XCTAssertEqual(LanguageSettings.acceptLanguage(defaults: defaults), "ru")
        XCTAssertEqual(LanguageSettings(defaults: defaults).selection, .russian)
        settings.selection = .english
        XCTAssertEqual(settings.locale.identifier, "en")
    }

    func testCatalogHasBothLanguagesAndPermissionTextIsLocalized() {
        XCTAssertEqual(L10n.string("Chat", language: "ru"), "Чат")
        XCTAssertEqual(L10n.string("Chat", language: "en"), "Chat")
        XCTAssertEqual(L10n.string("Sign In", table: "AppleSignIn", language: "ru"), "Войти")
        let key = "NSLocationWhenInUseUsageDescription"
        let ru = L10n.string(key, table: "InfoPlist", language: "ru")
        let en = L10n.string(key, table: "InfoPlist", language: "en")
        XCTAssertTrue(ru.hasPrefix("Jol использует"))
        XCTAssertTrue(en.hasPrefix("Jol uses"))
    }
}
