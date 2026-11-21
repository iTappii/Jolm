import CoreGraphics
@testable import Jol
import XCTest

/// Ш-32b: geometry of the answer chain — centring, the wave, overflow, connectors.
final class ChainGeometryTests: XCTestCase {
    private let viewport: CGFloat = 320

    private func xs(_ count: Int) -> [CGFloat] {
        (0..<count).map { ChainGeometry.nodeCenter(index: Double($0), count: Double(count), viewport: viewport).x }
    }

    func testOneNodeIsCentred() {
        XCTAssertEqual(xs(1), [viewport / 2])
    }

    func testTwoNodesAreLeftAndRightOfTheCentre() {
        let points = xs(2)
        XCTAssertEqual(points[1] - points[0], ChainGeometry.step, accuracy: 1e-6)
        XCTAssertEqual((points[0] + points[1]) / 2, viewport / 2, accuracy: 1e-6)
    }

    func testAChainThatFitsIsCentred() {
        for count in 1...4 {
            let points = xs(count)
            XCTAssertEqual((points.first! + points.last!) / 2, viewport / 2, accuracy: 1e-6, "\(count) nodes")
            XCTAssertEqual(points, points.sorted(), "left to right")
        }
    }

    func testNodesAlternateAboveAndBelowTheMidline() {
        let mid = ChainGeometry.height / 2
        for index in 0..<6 {
            let center = ChainGeometry.nodeCenter(index: Double(index), count: 6, viewport: 1000)
            if index % 2 == 0 {
                XCTAssertEqual(center.y, mid - ChainGeometry.amplitude, accuracy: 1e-6)
            } else {
                XCTAssertEqual(center.y, mid + ChainGeometry.amplitude, accuracy: 1e-6)
            }
        }
    }

    func testLabelsStandAboveHighNodesAndBelowLowOnes() {
        for index in 0..<6 {
            let node = ChainGeometry.nodeCenter(index: Double(index), count: 6, viewport: 1000)
            let label = ChainGeometry.labelCenter(index: index, count: 6, viewport: 1000)
            XCTAssertEqual(label.x, node.x, accuracy: 1e-6)
            if ChainGeometry.isHigh(index: index) {
                XCTAssertLessThan(label.y + ChainGeometry.labelHeight / 2, node.y - ChainGeometry.nodeRadius + 0.001)
            } else {
                XCTAssertGreaterThan(label.y - ChainGeometry.labelHeight / 2, node.y + ChainGeometry.nodeRadius - 0.001)
            }
            XCTAssertGreaterThanOrEqual(label.y - ChainGeometry.labelHeight / 2, -0.001, "inside the strip: top")
            XCTAssertLessThanOrEqual(label.y + ChainGeometry.labelHeight / 2, ChainGeometry.height + 0.001, "bottom")
        }
    }

    func testNeighbourLabelsNeverOverlap() {
        for count in 2...12 {
            let boxes = (0..<count).map { index -> CGRect in
                let center = ChainGeometry.labelCenter(index: index, count: Double(count), viewport: viewport)
                return CGRect(
                    x: center.x - ChainGeometry.labelWidth / 2, y: center.y - ChainGeometry.labelHeight / 2,
                    width: ChainGeometry.labelWidth, height: ChainGeometry.labelHeight
                )
            }
            for first in 0..<count {
                for second in (first + 1)..<count {
                    XCTAssertFalse(boxes[first].intersects(boxes[second]), "labels \(first)/\(second) of \(count)")
                }
            }
        }
    }

    func testLabelsClearTheirOwnAndNeighbouringNodes() {
        for count in 2...8 {
            let nodes = (0..<count).map {
                ChainGeometry.nodeCenter(index: Double($0), count: Double(count), viewport: viewport)
            }
            for index in 0..<count {
                let center = ChainGeometry.labelCenter(index: index, count: Double(count), viewport: viewport)
                let box = CGRect(
                    x: center.x - ChainGeometry.labelWidth / 2, y: center.y - ChainGeometry.labelHeight / 2,
                    width: ChainGeometry.labelWidth, height: ChainGeometry.labelHeight
                )
                for node in nodes {
                    let circle = CGRect(
                        x: node.x - ChainGeometry.nodeRadius, y: node.y - ChainGeometry.nodeRadius,
                        width: 2 * ChainGeometry.nodeRadius, height: 2 * ChainGeometry.nodeRadius
                    )
                    XCTAssertFalse(box.intersects(circle), "label \(index) hits a node, \(count) nodes")
                }
            }
        }
    }

    func testOverflowKeepsTheFirstNodeAtTheEdgeAndWidensTheContent() {
        let fits = ChainGeometry.contentWidth(count: 3, viewport: viewport)
        XCTAssertEqual(fits, viewport, "a chain that fits does not scroll")
        let many = ChainGeometry.contentWidth(count: 9, viewport: viewport)
        XCTAssertGreaterThan(many, viewport)
        let first = ChainGeometry.nodeCenter(index: 0, count: 9, viewport: viewport).x
        XCTAssertEqual(first, ChainGeometry.labelWidth / 2 + ChainGeometry.edgePadding, accuracy: 1e-6)
        let last = ChainGeometry.nodeCenter(index: 8, count: 9, viewport: viewport).x
        XCTAssertLessThanOrEqual(last + ChainGeometry.labelWidth / 2, many)
        XCTAssertGreaterThanOrEqual(
            ChainGeometry.contentWidth(count: 10, viewport: viewport), many + ChainGeometry.step - 0.001
        )
    }

    func testPositionsAreContinuousWhileANodeIsAdded() {
        // The new node (index 2 of 3) comes in from the right: at count 2 it is one step right of the last node.
        let before = ChainGeometry.nodeCenter(index: 2, count: 2, viewport: viewport).x
        let after = ChainGeometry.nodeCenter(index: 2, count: 3, viewport: viewport).x
        XCTAssertGreaterThan(before, after, "existing nodes slide left to re-centre, the new one follows")
    }

    func testConnectorsAreStraightSegmentsBetweenNodeEdges() {
        XCTAssertEqual(ChainGeometry.connectorCount(nodes: 0), 0)
        XCTAssertEqual(ChainGeometry.connectorCount(nodes: 1), 0)
        XCTAssertEqual(ChainGeometry.connectorCount(nodes: 4), 3)
        let gap = ChainGeometry.nodeRadius + ChainGeometry.connectorGap
        for index in 0..<3 {
            let from = ChainGeometry.nodeCenter(index: Double(index), count: 4, viewport: viewport)
            let to = ChainGeometry.nodeCenter(index: Double(index + 1), count: 4, viewport: viewport)
            let edge = ChainGeometry.connector(index: index, count: 4, viewport: viewport)
            // Both ends lie on the line between the centres (a straight edge, no curve)...
            let cross1 = (to.x - from.x) * (edge.start.y - from.y) - (to.y - from.y) * (edge.start.x - from.x)
            let cross2 = (to.x - from.x) * (edge.end.y - from.y) - (to.y - from.y) * (edge.end.x - from.x)
            XCTAssertEqual(cross1, 0, accuracy: 1e-3)
            XCTAssertEqual(cross2, 0, accuracy: 1e-3)
            // ... just outside the node circles, and it runs from the earlier node to the later one.
            XCTAssertEqual(hypot(edge.start.x - from.x, edge.start.y - from.y), gap, accuracy: 1e-3)
            XCTAssertEqual(hypot(edge.end.x - to.x, edge.end.y - to.y), gap, accuracy: 1e-3)
            XCTAssertLessThan(edge.start.x, edge.end.x)
        }
    }

    func testStripIsCompact() {
        XCTAssertGreaterThanOrEqual(ChainGeometry.height, 60)
        XCTAssertLessThanOrEqual(ChainGeometry.height, 90)
    }
}
