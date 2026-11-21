@testable import Jol
import XCTest

final class SessionStoreTests: XCTestCase {
    func testKeychainRoundTripAndRotation() throws {
        let store = SessionStore(service: "kz.jol.tests.\(UUID().uuidString)")
        defer { try? store.clear() }
        XCTAssertNil(try store.load())
        let original = SessionTokens(accessToken: "first-access", refreshToken: "first-refresh")
        try store.save(original)
        XCTAssertEqual(try store.load(), original)
        let rotated = SessionTokens(accessToken: "new-access", refreshToken: "new-refresh")
        try store.save(rotated)
        XCTAssertEqual(try store.load(), rotated)
        try store.clear()
        XCTAssertNil(try store.load())
    }
}
