import CoreGraphics
import Foundation

/// Geometry of the thesis ring (SSOT §11.2): nodes on a circle starting at 12 o'clock, clockwise, curved arrows between
/// neighbours along the circle, trimmed so they start and end at the node edges. Pure maths, no SwiftUI: the counts are
/// `Double` so the same functions drive the animation (the count is interpolated while a node is being added).
enum RingGeometry {
    /// Radius of a node dot.
    static let nodeRadius: CGFloat = 11
    /// Air between a node edge and the start/end of an arrow.
    static let arrowGap: CGFloat = 3
    /// Largest radius of the circle (reached from five nodes).
    static let maxRadius: CGFloat = 44
    /// Arrowhead size.
    static let headLength: CGFloat = 7
    static let headWidth: CGFloat = 6
    /// Arcs shorter than this (radians) are not drawn: with too many nodes there is no room for an arrow.
    static let minArcSpan = 0.06

    /// Radius of the circle for a (fractional) node count: one node sits in the centre, two are a diameter apart.
    static func ringRadius(count: Double) -> CGFloat {
        if count <= 1 { return 0 }
        if count <= 2 { return 22 * CGFloat(count - 1) }
        return min(maxRadius, 22 + 8 * CGFloat(count - 2))
    }

    /// Side of the square the ring is drawn in, for a whole number of nodes.
    static func side(nodes: Int) -> CGFloat {
        2 * (ringRadius(count: Double(max(nodes, 1))) + nodeRadius + 3)
    }

    /// Angle of node `index` (radians): 0 at 12 o'clock, growing clockwise. `index == count` is the first node again.
    static func angle(index: Double, count: Double) -> Double {
        2 * .pi * index / max(count, 1)
    }

    /// Point on the circle at `angle`, as an offset from the circle's centre.
    static func offset(angle: Double, radius: CGFloat) -> CGPoint {
        CGPoint(x: radius * CGFloat(sin(angle)), y: -radius * CGFloat(cos(angle)))
    }

    /// Offset of node `index` from the centre of the ring.
    static func nodeOffset(index: Int, count: Double) -> CGPoint {
        offset(angle: angle(index: Double(index), count: count), radius: ringRadius(count: count))
    }

    /// Angular trim at each end of an arrow: the angle subtended by the node radius plus the gap.
    static func trim(radius: CGFloat) -> Double {
        guard radius > 0 else { return 0 }
        return 2 * asin(min(1, Double((nodeRadius + arrowGap) / (2 * radius))))
    }

    /// Arrow from node `index` to the next node (the first one again for the closing arrow), trimmed at both ends.
    /// `nil` when there is no room for it.
    static func arc(index: Int, count: Double) -> (start: Double, end: Double)? {
        let radius = ringRadius(count: count)
        guard radius > 0 else { return nil }
        let cut = trim(radius: radius)
        let start = angle(index: Double(index), count: count) + cut
        let end = angle(index: Double(index + 1), count: count) - cut
        return end - start >= minArcSpan ? (start, end) : nil
    }

    /// Number of arrows: one between every pair of neighbours, plus the closing one when the route is ready. A single
    /// node has no arrows (it would loop onto itself).
    static func arrowCount(nodes: Int, closed: Bool) -> Int {
        guard nodes >= 2 else { return 0 }
        return nodes - 1 + (closed ? 1 : 0)
    }

    /// Points along the arc, as offsets from the centre.
    static func arcPoints(start: Double, end: Double, radius: CGFloat) -> [CGPoint] {
        let steps = max(6, Int(((end - start) * 14).rounded(.up)))
        return (0...steps).map { step in
            offset(angle: start + (end - start) * Double(step) / Double(steps), radius: radius)
        }
    }

    /// Arrowhead at the end of an arc: tip on the arc end, base back along the clockwise tangent.
    static func head(end: Double, radius: CGFloat) -> [CGPoint] {
        let tip = offset(angle: end, radius: radius)
        let tangent = CGPoint(x: CGFloat(cos(end)), y: CGFloat(sin(end)))
        let normal = CGPoint(x: -tangent.y, y: tangent.x)
        let base = CGPoint(x: tip.x - tangent.x * headLength, y: tip.y - tangent.y * headLength)
        return [
            tip,
            CGPoint(x: base.x + normal.x * headWidth / 2, y: base.y + normal.y * headWidth / 2),
            CGPoint(x: base.x - normal.x * headWidth / 2, y: base.y - normal.y * headWidth / 2)
        ]
    }
}
