@testable import Jol
import XCTest

/// Ш-43: the side panel's wire shapes match `GET /v1/chats` and `GET /v1/trips` (server/app/chat/api.py,
/// server/app/trips/read.py). Ш-52: privacy manifest, permission strings in RU+EN, privacy link.
final class SidebarAndLegalTests: XCTestCase {
    func testChatsListDecodesTheServerShape() throws {
        let json = """
        {"items":[
          {"id":"11111111-1111-1111-1111-111111111111","title":null,"locale":"ru",
           "created_at":"2026-11-21T10:00:00+05:00","updated_at":"2026-11-21T10:05:00+05:00","preview":"Хочу в горы"},
          {"id":"22222222-2222-2222-2222-222222222222","title":"3 days in Almaty","locale":"en",
           "created_at":"2026-11-20T10:00:00+05:00","updated_at":"2026-11-20T10:05:00+05:00","preview":null},
          {"id":"33333333-3333-3333-3333-333333333333","title":null,"locale":"en",
           "created_at":"2026-11-19T10:00:00+05:00","updated_at":"2026-11-19T10:05:00+05:00","preview":null}
        ]}
        """
        let list = try JSONDecoder().decode(ChatsList.self, from: Data(json.utf8))
        XCTAssertEqual(list.items.count, 3)
        XCTAssertEqual(list.items[0].displayTitle, "Хочу в горы", "no title: the first words of the chat")
        XCTAssertEqual(list.items[1].displayTitle, "3 days in Almaty")
        XCTAssertNil(list.items[2].displayTitle, "an empty chat shows the localized \"New chat\"")
    }

    func testTripsListDecodesTheServerShape() throws {
        let json = """
        {"items":[{"id":"44444444-4444-4444-4444-444444444444","title":"Dec 5-7",
          "chat_id":"22222222-2222-2222-2222-222222222222","start_date":"2026-12-05","end_date":"2026-12-07",
          "days":3,"version":2,"status":"active",
          "budget":{"status":"ok","budget_kzt":900000,"total_kzt":640000},
          "updated_at":"2026-11-21T10:00:00+05:00"}]}
        """
        let list = try JSONDecoder().decode(TripSummaries.self, from: Data(json.utf8))
        XCTAssertEqual(list.items.first?.days, 3)
        XCTAssertEqual(list.items.first?.startDate, "2026-12-05")
        XCTAssertEqual(list.items.first?.budget?.totalKzt, 640_000)
    }

    func testPrivacyURLMustBeHTTPS() {
        XCTAssertEqual(AppConfig.resolvePrivacyURL(configured: " https://jol.kz/privacy ")?.host, "jol.kz")
        XCTAssertNil(AppConfig.resolvePrivacyURL(configured: "http://jol.kz/privacy"))
        XCTAssertNil(AppConfig.resolvePrivacyURL(configured: ""))
        XCTAssertNil(AppConfig.resolvePrivacyURL(configured: nil))
        XCTAssertNotNil(AppConfig.privacyPolicyURL, "the build configures JOL_PRIVACY_URL")
    }

    func testEveryPermissionStringExistsInRussianAndEnglish() throws {
        let info = try XCTUnwrap(Bundle.main.infoDictionary)
        let keys = info.keys.filter { $0.hasPrefix("NS") && $0.hasSuffix("UsageDescription") }
        XCTAssertTrue(keys.contains("NSLocationWhenInUseUsageDescription"))
        for key in keys {
            XCTAssertFalse((info[key] as? String ?? "").isEmpty, "\(key) is empty in Info.plist")
            for language in ["en", "ru"] {
                let path = try XCTUnwrap(
                    Bundle.main.path(forResource: "InfoPlist", ofType: "strings", inDirectory: nil,
                                     forLocalization: language), "InfoPlist.strings (\(language)) is missing")
                let table = NSDictionary(contentsOfFile: path)
                XCTAssertFalse((table?[key] as? String ?? "").isEmpty, "\(key) has no \(language) text")
            }
        }
    }

    func testPrivacyManifestDeclaresNoTrackingAndUserDefaultsReason() throws {
        let url = try XCTUnwrap(Bundle.main.url(forResource: "PrivacyInfo", withExtension: "xcprivacy"))
        let manifest = try XCTUnwrap(NSDictionary(contentsOf: url) as? [String: Any])
        XCTAssertEqual(manifest["NSPrivacyTracking"] as? Bool, false)
        let apis = manifest["NSPrivacyAccessedAPITypes"] as? [[String: Any]] ?? []
        let category = "NSPrivacyAccessedAPICategoryUserDefaults"
        let defaults = apis.first { $0["NSPrivacyAccessedAPIType"] as? String == category }
        XCTAssertEqual(defaults?["NSPrivacyAccessedAPITypeReasons"] as? [String], ["CA92.1"])
        let collected = manifest["NSPrivacyCollectedDataTypes"] as? [[String: Any]] ?? []
        XCTAssertTrue(collected.allSatisfy { ($0["NSPrivacyCollectedDataTypeTracking"] as? Bool) == false })
        XCTAssertFalse(collected.isEmpty)
    }
}
