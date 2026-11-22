@testable import Jol
import XCTest

/// «All days» draws each day in its own colour: features carry `#RRGGBB` that MapLibre casts to a colour.
@MainActor
final class TripMapColorTests: XCTestCase {
    func testHexStringIsSixUppercaseDigitsWithHash() {
        XCTAssertEqual(MapCoordinator.hexString(0xFF7A00), "#FF7A00")
        XCTAssertEqual(MapCoordinator.hexString(0x0000AB), "#0000AB")
        XCTAssertEqual(MapCoordinator.hexString(0xFF123456), "#123456", "alpha bits are dropped")
    }
}
