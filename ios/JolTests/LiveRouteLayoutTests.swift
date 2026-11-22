@testable import Jol
import XCTest

/// Ш-54: the collision rules of the live route overlay.
final class LiveRouteLayoutTests: XCTestCase {
    private let caption = CGSize(width: 100, height: 20)

    func testCaptionGoesBelowItsPinWhenNothingIsThere() {
        let sides = LiveRouteLayout.captionSides(
            [.init(pin: CGPoint(x: 200, y: 200), size: caption)], blockers: [])
        XCTAssertEqual(sides, [.below])
    }

    func testAlternativeUnderTheCaptionMovesItAbove() {
        let pin = CGPoint(x: 200, y: 200)
        let below = LiveRouteLayout.captionRect(.init(pin: pin, size: caption), side: .below)
        let alternative = LiveRouteLayout.rect(
            center: CGPoint(x: below.minX + 10, y: below.midY), size: CGSize(width: 28, height: 28))
        let sides = LiveRouteLayout.captionSides([.init(pin: pin, size: caption)], blockers: [alternative])
        XCTAssertEqual(sides, [.above])
        let above = LiveRouteLayout.captionRect(.init(pin: pin, size: caption), side: .above)
        XCTAssertFalse(above.intersects(alternative))
        XCTAssertLessThan(above.maxY, pin.y - LiveRouteLayout.pinRadius, "above the pin, not on it")
    }

    func testBothSidesBlockedHidesTheCaption() {
        let pin = CGPoint(x: 200, y: 200)
        let blockers = [LiveRouteLayout.captionRect(.init(pin: pin, size: caption), side: .below),
                        LiveRouteLayout.captionRect(.init(pin: pin, size: caption), side: .above)]
        XCTAssertEqual(LiveRouteLayout.captionSides([.init(pin: pin, size: caption)], blockers: blockers), [.hidden])
    }

    func testCaptionsDoNotCoverEachOther() {
        let first = LiveRouteLayout.Caption(pin: CGPoint(x: 100, y: 100), size: caption)
        let second = LiveRouteLayout.Caption(pin: CGPoint(x: 110, y: 115), size: caption)
        let sides = LiveRouteLayout.captionSides([first, second], blockers: [])
        XCTAssertEqual(sides[0], .below)
        XCTAssertNotEqual(sides[1], .below, "its slot is taken by the first caption")
    }

    func testCapsuleSlidesAlongTheEdgeAwayFromAStopPin() {
        let from = CGPoint(x: 100, y: 400)
        let to = CGPoint(x: 300, y: 400)
        let size = CGSize(width: 80, height: 28)
        let free = LiveRouteLayout.capsuleCenter(from: from, to: to, offset: 20, size: size, avoiding: [])
        XCTAssertEqual(free.x, 200, accuracy: 0.001, "no obstacle: the middle")
        // A third stop sits right where the capsule would be.
        let pin = CGPoint(x: 200, y: 380)
        let moved = LiveRouteLayout.capsuleCenter(from: from, to: to, offset: 20, size: size, avoiding: [pin])
        XCTAssertNotEqual(moved.x, 200, accuracy: 1)
        XCTAssertFalse(LiveRouteLayout.rect(center: moved, size: size).intersects(LiveRouteLayout.pinRect(pin)))
        XCTAssertEqual(moved.y, 380, accuracy: 0.001, "still beside the edge, only slid along it")
    }

    func testCapsuleAlsoAvoidsAnAlternativePin() {
        let from = CGPoint(x: 100, y: 400)
        let to = CGPoint(x: 300, y: 400)
        let size = CGSize(width: 80, height: 28)
        let alternative = CGPoint(x: 200, y: 380)
        let center = LiveRouteLayout.capsuleCenter(
            from: from, to: to, offset: 20, size: size, avoiding: [], alternatives: [alternative])
        let frame = LiveRouteLayout.rect(center: center, size: size)
        XCTAssertFalse(frame.intersects(LiveRouteLayout.rect(center: alternative, size: CGSize(width: 28, height: 28))))
    }

    func testCapsuleAvoidsAnotherCapsule() {
        let from = CGPoint(x: 100, y: 400)
        let to = CGPoint(x: 500, y: 400)
        let size = CGSize(width: 80, height: 28)
        let other = LiveRouteLayout.rect(center: CGPoint(x: 300, y: 380), size: size)
        let center = LiveRouteLayout.capsuleCenter(
            from: from, to: to, offset: 20, size: size, avoiding: [], otherCapsules: [other])
        XCTAssertFalse(LiveRouteLayout.rect(center: center, size: size).intersects(other))
    }

    func testCapsuleKeepsTheMiddleWhenNoPositionIsFree() {
        let from = CGPoint(x: 100, y: 400)
        let to = CGPoint(x: 160, y: 400)
        let pins = [from, to, CGPoint(x: 130, y: 385)]
        let center = LiveRouteLayout.capsuleCenter(
            from: from, to: to, offset: 20, size: CGSize(width: 80, height: 28), avoiding: pins)
        XCTAssertEqual(center.x, 130, accuracy: 0.001)
    }

    func testCapsuleSizeGrowsWithTheText() {
        XCTAssertGreaterThan(
            LiveRouteLayout.capsuleSize(text: "1 h 5 min").width, LiveRouteLayout.capsuleSize(text: "5 min").width)
    }
}
