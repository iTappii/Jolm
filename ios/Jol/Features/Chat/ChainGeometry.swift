import CoreGraphics
import Foundation

/// Geometry of the answer chain (SSOT §11.2): nodes go left to right with a gentle wave (even nodes sit a little
/// above the midline, odd ones below), the whole chain is centred while it fits, otherwise it keeps its left edge and
/// the strip scrolls. A node's value stands above a high node and below a low one, so neighbours' labels never meet.
/// Pure maths, no SwiftUI: `count` is a `Double`, so the same functions drive the animation (while a node is being
/// added the count is interpolated: old nodes slide towards the new centre, the new node comes in from the right).
enum ChainGeometry {
    /// Radius of a node dot.
    static let nodeRadius: CGFloat = 10
    /// Horizontal distance between the centres of neighbouring nodes.
    static let step: CGFloat = 66
    /// Distance of a node from the midline: even nodes up, odd nodes down.
    static let amplitude: CGFloat = 9
    /// The value label next to a node: its box, and the air between the node and the box.
    static let labelWidth: CGFloat = 96
    static let labelHeight: CGFloat = 12
    static let labelGap: CGFloat = 2
    /// Side padding of the strip.
    static let edgePadding: CGFloat = 4
    /// Air between a node edge and the start / end of a connector.
    static let connectorGap: CGFloat = 1.5

    /// Height of the strip: the two label rows, the nodes between them.
    static var height: CGFloat { 2 * (amplitude + nodeRadius + labelGap + labelHeight) }

    /// A high node (it sits above the midline, its label above it).
    static func isHigh(index: Int) -> Bool { index % 2 == 0 }

    /// Left edge (x of node 0) for a (fractional) node count in a strip `viewport` wide: centred, but never closer to
    /// the edge than the first label needs.
    static func firstNodeX(count: Double, viewport: CGFloat) -> CGFloat {
        let chain = CGFloat(max(count - 1, 0)) * step
        return max(labelWidth / 2 + edgePadding, viewport / 2 - chain / 2)
    }

    /// Width of the scrolled content: at least the viewport, wider when the chain does not fit.
    static func contentWidth(count: Double, viewport: CGFloat) -> CGFloat {
        let chain = CGFloat(max(count - 1, 0)) * step
        return max(viewport, firstNodeX(count: count, viewport: viewport) + chain + labelWidth / 2 + edgePadding)
    }

    /// Centre of node `index` in strip coordinates (y measured from the top of the strip).
    static func nodeCenter(index: Double, count: Double, viewport: CGFloat) -> CGPoint {
        let high = Int(index.rounded()).isMultiple(of: 2)
        return CGPoint(
            x: firstNodeX(count: count, viewport: viewport) + CGFloat(index) * step,
            y: height / 2 + (high ? -amplitude : amplitude)
        )
    }

    /// Centre of the label box of node `index`: above a high node, below a low one.
    static func labelCenter(index: Int, count: Double, viewport: CGFloat) -> CGPoint {
        let node = nodeCenter(index: Double(index), count: count, viewport: viewport)
        let shift = nodeRadius + labelGap + labelHeight / 2
        return CGPoint(x: node.x, y: node.y + (isHigh(index: index) ? -shift : shift))
    }

    struct Connector: Equatable {
        let start: CGPoint
        let end: CGPoint
    }

    /// Straight segment from node `index` to the next one, trimmed at both ends to the node edges (plus a hair of
    /// air). The wave of the chain comes only from the node positions, the edges are never curved.
    static func connector(index: Int, count: Double, viewport: CGFloat) -> Connector {
        let from = nodeCenter(index: Double(index), count: count, viewport: viewport)
        let to = nodeCenter(index: Double(index + 1), count: count, viewport: viewport)
        let length = max(hypot(to.x - from.x, to.y - from.y), 0.001)
        let inset = nodeRadius + connectorGap
        let unit = CGPoint(x: (to.x - from.x) / length, y: (to.y - from.y) / length)
        return Connector(
            start: CGPoint(x: from.x + unit.x * inset, y: from.y + unit.y * inset),
            end: CGPoint(x: to.x - unit.x * inset, y: to.y - unit.y * inset)
        )
    }

    /// Number of connectors for `nodes` nodes (the finish node counts as one).
    static func connectorCount(nodes: Int) -> Int { max(nodes - 1, 0) }
}
