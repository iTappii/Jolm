import CoreGraphics

/// Collision rules of the live route's overlay (Ш-54), pure geometry so they are unit-tested: duration capsules slide
/// along their edge away from the stop pins, and a stop's caption goes below its pin, else above, else is hidden
/// (the name stays in the VoiceOver label).
enum LiveRouteLayout {
    enum CaptionSide: Equatable { case below, above, hidden }

    static let pinRadius: CGFloat = 15
    static let captionGap: CGFloat = 6

    /// A rough capsule size from the text (the layout runs before SwiftUI measures anything).
    static func capsuleSize(text: String) -> CGSize {
        CGSize(width: 34 + CGFloat(text.count) * 7.5, height: 28)
    }

    static func rect(center: CGPoint, size: CGSize) -> CGRect {
        CGRect(x: center.x - size.width / 2, y: center.y - size.height / 2, width: size.width, height: size.height)
    }

    /// The pin as a square a little larger than the circle (shadow, white ring).
    static func pinRect(_ center: CGPoint) -> CGRect {
        rect(center: center, size: CGSize(width: pinRadius * 2 + 4, height: pinRadius * 2 + 4))
    }

    /// Centre of the capsule of an edge: the middle of the edge pushed to its upper side; when that touches a stop pin,
    /// it slides along the edge (alternating sides of the middle) until it is free. Falls back to the middle.
    static func capsuleCenter(
        from: CGPoint, to: CGPoint, offset: CGFloat, size: CGSize, avoiding pins: [CGPoint],
        alternatives: [CGPoint] = [], otherCapsules: [CGRect] = []
    ) -> CGPoint {
        let blocked = pins.map(pinRect)
            + alternatives.map { rect(center: $0, size: CGSize(width: 28, height: 28)) }
            + otherCapsules
        func center(at fraction: CGFloat) -> CGPoint {
            let point = CGPoint(x: from.x + (to.x - from.x) * fraction, y: from.y + (to.y - from.y) * fraction)
            let shift = labelShift(from: from, to: to, offset: offset)
            return CGPoint(x: point.x + shift.x, y: point.y + shift.y)
        }
        for step in 0...10 {
            let delta = CGFloat((step + 1) / 2) * 0.06 * (step.isMultiple(of: 2) ? 1 : -1)
            let fraction = 0.5 + delta
            guard fraction > 0.15, fraction < 0.85 else { continue }
            let candidate = center(at: fraction)
            let frame = rect(center: candidate, size: size)
            if !blocked.contains(where: { $0.intersects(frame) }) { return candidate }
        }
        return center(at: 0.5)
    }

    /// The sideways push of `LiveRouteGeometry.labelCenter` as a vector.
    private static func labelShift(from: CGPoint, to: CGPoint, offset: CGFloat) -> CGPoint {
        let middle = CGPoint(x: (from.x + to.x) / 2, y: (from.y + to.y) / 2)
        let pushed = LiveRouteGeometry.labelCenter(from: from, to: to, offset: offset)
        return CGPoint(x: pushed.x - middle.x, y: pushed.y - middle.y)
    }

    struct Caption {
        let pin: CGPoint
        let size: CGSize
    }

    /// Where each caption goes. `blockers` are the frames it must not cover: alternative pins, capsules, other pins.
    static func captionSides(_ captions: [Caption], blockers: [CGRect]) -> [CaptionSide] {
        var placed: [CGRect] = []
        return captions.map { caption in
            for side in [CaptionSide.below, .above] {
                let frame = captionRect(caption, side: side)
                if !(blockers + placed).contains(where: { $0.intersects(frame) }) {
                    placed.append(frame)
                    return side
                }
            }
            return .hidden
        }
    }

    static func captionRect(_ caption: Caption, side: CaptionSide) -> CGRect {
        let distance = pinRadius + captionGap + caption.size.height / 2
        let centerY = caption.pin.y + (side == .above ? -distance : distance)
        return rect(center: CGPoint(x: caption.pin.x, y: centerY), size: caption.size)
    }
}
