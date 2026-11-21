import CoreGraphics
@testable import Jol
import XCTest

/// Ш-32a: geometry of the thesis ring — angles, node positions, arrow trimming, the closing arrow.
final class RingGeometryTests: XCTestCase {
    func testNodesStartAtTwelveOClockAndGoClockwise() {
        XCTAssertEqual(RingGeometry.angle(index: 0, count: 4), 0, accuracy: 1e-9)
        XCTAssertEqual(RingGeometry.angle(index: 1, count: 4), .pi / 2, accuracy: 1e-9)
        XCTAssertEqual(RingGeometry.angle(index: 4, count: 4), 2 * .pi, accuracy: 1e-9)
        let first = RingGeometry.nodeOffset(index: 0, count: 4)
        XCTAssertEqual(first.x, 0, accuracy: 1e-6)
        XCTAssertLessThan(first.y, 0, "the first node is above the centre")
        let second = RingGeometry.nodeOffset(index: 1, count: 4)
        XCTAssertGreaterThan(second.x, 0, "clockwise: the second of four is on the right")
        XCTAssertEqual(second.y, 0, accuracy: 1e-6)
        XCTAssertGreaterThan(RingGeometry.nodeOffset(index: 2, count: 4).y, 0)
    }

    func testNodesAreSpreadEvenlyOnOneCircle() {
        for count in 2...9 {
            let radius = RingGeometry.ringRadius(count: Double(count))
            let points = (0..<count).map { RingGeometry.nodeOffset(index: $0, count: Double(count)) }
            for point in points {
                XCTAssertEqual(hypot(point.x, point.y), radius, accuracy: 1e-4)
            }
            let gaps = (0..<count).map { distance(points[$0], points[($0 + 1) % count]) }
            for gap in gaps { XCTAssertEqual(gap, gaps[0], accuracy: 1e-4, "even spread for \(count) nodes") }
        }
    }

    func testSingleNodeSitsInTheCentreAndTwoAreADiameterApart() {
        let single = RingGeometry.nodeOffset(index: 0, count: 1)
        XCTAssertEqual(hypot(single.x, single.y), 0, accuracy: 1e-9)
        let left = RingGeometry.nodeOffset(index: 0, count: 2)
        let right = RingGeometry.nodeOffset(index: 1, count: 2)
        XCTAssertEqual(distance(left, right), 2 * RingGeometry.ringRadius(count: 2), accuracy: 1e-4)
        XCTAssertEqual(RingGeometry.arrowCount(nodes: 1, closed: true), 0, "one node has no arrows")
    }

    func testRadiusGrowsContinuouslyAndIsCapped() {
        var previous: CGFloat = -1
        for step in stride(from: 1.0, through: 8.0, by: 0.25) {
            let radius = RingGeometry.ringRadius(count: step)
            XCTAssertGreaterThanOrEqual(radius, previous)
            XCTAssertLessThanOrEqual(radius, RingGeometry.maxRadius)
            previous = radius
        }
        XCTAssertEqual(RingGeometry.ringRadius(count: 8), RingGeometry.maxRadius)
    }

    func testArrowsStartAndEndOutsideTheNodes() throws {
        let clearance = RingGeometry.nodeRadius
        for count in 2...8 {
            let radius = RingGeometry.ringRadius(count: Double(count))
            for index in 0..<count {
                let arc = try XCTUnwrap(RingGeometry.arc(index: index, count: Double(count)), "\(count) nodes")
                let from = RingGeometry.nodeOffset(index: index, count: Double(count))
                let to = RingGeometry.nodeOffset(index: index + 1, count: Double(count))
                let start = RingGeometry.offset(angle: arc.start, radius: radius)
                let end = RingGeometry.offset(angle: arc.end, radius: radius)
                XCTAssertGreaterThan(distance(start, from), clearance, "arrow start overlaps its node")
                XCTAssertGreaterThan(distance(end, to), clearance, "arrow tip overlaps the next node")
                XCTAssertLessThan(distance(start, from), clearance + 4, "arrow starts at the node edge")
                XCTAssertLessThan(distance(end, to), clearance + 4, "arrow ends at the node edge")
                XCTAssertGreaterThan(arc.end, arc.start)
                // No overlap with any other node either.
                for other in 0..<count {
                    let centre = RingGeometry.nodeOffset(index: other, count: Double(count))
                    for point in RingGeometry.arcPoints(start: arc.start, end: arc.end, radius: radius) {
                        XCTAssertGreaterThan(distance(point, centre), clearance - 0.01)
                    }
                }
            }
        }
    }

    func testClosingArrowOnlyWhenClosed() {
        XCTAssertEqual(RingGeometry.arrowCount(nodes: 3, closed: false), 2)
        XCTAssertEqual(RingGeometry.arrowCount(nodes: 3, closed: true), 3)
        XCTAssertEqual(RingGeometry.arrowCount(nodes: 2, closed: false), 1)
        XCTAssertEqual(RingGeometry.arrowCount(nodes: 2, closed: true), 2)
        XCTAssertEqual(RingGeometry.arrowCount(nodes: 0, closed: true), 0)
        // The closing arrow of N nodes (index N-1) runs from the last node to the first: it ends before 2π.
        let closing = RingGeometry.arc(index: 4, count: 5)
        XCTAssertNotNil(closing)
        XCTAssertLessThan(closing?.end ?? 99, 2 * .pi)
        XCTAssertGreaterThan(closing?.end ?? 0, 2 * .pi - 2 * .pi / 5)
    }

    func testArrowheadTipTouchesTheArcEndAndPointsClockwise() {
        let radius: CGFloat = 40
        let end = 1.0
        let head = RingGeometry.head(end: end, radius: radius)
        let tip = RingGeometry.offset(angle: end, radius: radius)
        XCTAssertEqual(distance(head[0], tip), 0, accuracy: 1e-6)
        // The base lies behind the tip along the circle (smaller angle = counter-clockwise of the tip).
        let baseCentre = CGPoint(x: (head[1].x + head[2].x) / 2, y: (head[1].y + head[2].y) / 2)
        let behind = RingGeometry.offset(angle: end - 0.1, radius: radius)
        let ahead = RingGeometry.offset(angle: end + 0.3, radius: radius)
        XCTAssertLessThan(distance(baseCentre, behind), distance(baseCentre, ahead))
    }

    func testRingSideGrowsWithNodes() {
        XCTAssertLessThan(RingGeometry.side(nodes: 1), RingGeometry.side(nodes: 3))
        XCTAssertLessThan(RingGeometry.side(nodes: 3), RingGeometry.side(nodes: 6))
        XCTAssertEqual(RingGeometry.side(nodes: 6), RingGeometry.side(nodes: 9))
    }

    private func distance(_ from: CGPoint, _ to: CGPoint) -> CGFloat { hypot(from.x - to.x, from.y - to.y) }
}
