import SwiftUI

/// The thesis ring (SSOT §11.2): a small ring above the input field, at the trailing side. Every thesis is a dot on
/// a circle (12 o'clock, clockwise) with an arrow from the previous one; a new dot appears with a spring and the dots
/// re-distribute evenly. While the route is not ready the ring is open; on `route_ready` the last arrow back to the
/// first dot is drawn and the ring closes. Next to it: the latest thesis (the full text of a tapped dot) and, once the
/// route is ready, «Open full map».
struct ChatGraphView: View {
    let nodes: [GraphNode]
    let closed: Bool
    let onOpenRoute: () -> Void

    @State private var selected: Int?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var selectedNode: GraphNode? { nodes.first { $0.ord == selected } }
    private var caption: GraphNode? { selectedNode ?? nodes.last }

    var body: some View {
        HStack(alignment: .bottom, spacing: JolSpacing.md) {
            VStack(alignment: .trailing, spacing: JolSpacing.sm) {
                if let caption {
                    captionView(caption)
                }
                if closed {
                    openButton
                }
            }
            .frame(maxWidth: .infinity, alignment: .trailing)
            if !nodes.isEmpty {
                ring
            }
        }
        .onChange(of: nodes.count) { selected = nil }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("chat-graph")
    }

    private func captionView(_ node: GraphNode) -> some View {
        let isSelected = node.ord == selected
        return Text(verbatim: node.text)
            .font(JolFont.caption)
            .foregroundStyle(isSelected ? JolColor.textPrimary : JolColor.textSecondary)
            .lineLimit(isSelected ? nil : 2)
            .multilineTextAlignment(.trailing)
            .padding(.horizontal, isSelected ? JolSpacing.md : 0)
            .padding(.vertical, isSelected ? JolSpacing.xs + 2 : 0)
            .background {
                if isSelected {
                    RoundedRectangle(cornerRadius: JolRadius.md).fill(JolColor.surface)
                    RoundedRectangle(cornerRadius: JolRadius.md).stroke(JolColor.brand.opacity(0.7), lineWidth: 1)
                }
            }
            .onTapGesture { if isSelected { selected = nil } }
            .accessibilityHidden(!isSelected)
            .accessibilityIdentifier(isSelected ? "graph-node-detail" : "graph-caption")
    }

    private var openButton: some View {
        Button(action: onOpenRoute) {
            Label("Open full map", systemImage: "map.fill")
                .font(JolFont.callout.weight(.semibold))
                .foregroundStyle(JolColor.onBrand)
                .padding(.horizontal, JolSpacing.md)
                .padding(.vertical, JolSpacing.sm)
                .background(JolColor.brand, in: Capsule())
        }
        .buttonStyle(.plain)
        .transition(.scale(scale: 0.8, anchor: .trailing).combined(with: .opacity))
        .accessibilityIdentifier("chat-open-route")
    }

    // MARK: - Ring

    private var ring: some View {
        let count = Double(nodes.count)
        let side = RingGeometry.side(nodes: nodes.count)
        return ZStack {
            ForEach(0..<RingGeometry.arrowCount(nodes: nodes.count, closed: closed), id: \.self) { index in
                RingArrow(index: index, count: count, reduceMotion: reduceMotion)
            }
            ForEach(Array(nodes.enumerated()), id: \.element.ord) { index, node in
                dot(node, number: index + 1)
                    .modifier(RingPlacement(index: index, count: count))
                    .transition(.scale(scale: 0.2).combined(with: .opacity))
            }
            if closed {
                closedMark(visible: nodes.count >= 3)
            }
        }
        .frame(width: side, height: side)
        .animation(reduceMotion ? nil : .spring(duration: 0.55, bounce: 0.2), value: nodes.count)
        .animation(reduceMotion ? nil : .easeOut(duration: 0.4), value: closed)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(summary)
        .accessibilityValue(closed ? "closed" : "open")
        .accessibilityIdentifier("chat-graph-ring")
    }

    private func dot(_ node: GraphNode, number: Int) -> some View {
        let isSelected = node.ord == selected
        return Button {
            selected = isSelected ? nil : node.ord
        } label: {
            Text(verbatim: "\(number)")
                .font(.system(size: 11, weight: .bold, design: .rounded))
                .foregroundStyle(JolColor.onBrand)
                .frame(width: RingGeometry.nodeRadius * 2, height: RingGeometry.nodeRadius * 2)
                .background(JolColor.brand, in: Circle())
                .overlay(Circle().stroke(isSelected ? JolColor.textPrimary : JolColor.surfaceElevated, lineWidth: 2))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(verbatim: node.text))
        .accessibilityIdentifier("graph-node-\(node.ord)")
    }

    /// The ring is closed: a check in the middle (when the ring is big enough to hold it).
    @ViewBuilder
    private func closedMark(visible: Bool) -> some View {
        if visible {
            Image(systemName: "checkmark")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(JolColor.brand)
                .transition(.scale(scale: 0.3).combined(with: .opacity))
                .accessibilityLabel(Text("Route ready"))
                .accessibilityIdentifier("graph-ring-closed")
        } else {
            Color.clear.frame(width: 1, height: 1)
                .accessibilityElement()
                .accessibilityLabel(Text("Route ready"))
                .accessibilityIdentifier("graph-ring-closed")
        }
    }

    private var summary: Text {
        closed ? Text("\(nodes.count) theses, route is ready") : Text("\(nodes.count) theses, route is not ready")
    }
}

/// Moves a node (drawn at the centre of the ring) to its place on the circle. Animatable by the node count, so while
/// a node is added every dot glides along the circle to its new, evenly spread place.
private struct RingPlacement: GeometryEffect {
    let index: Int
    var count: Double

    var animatableData: Double {
        get { count }
        set { count = newValue }
    }

    func effectValue(size: CGSize) -> ProjectionTransform {
        let offset = RingGeometry.nodeOffset(index: index, count: count)
        return ProjectionTransform(CGAffineTransform(translationX: offset.x, y: offset.y))
    }
}

/// One arrow of the ring: an arc along the circle with an arrowhead. Drawn in when it appears.
private struct RingArrow: View {
    let index: Int
    let count: Double
    let reduceMotion: Bool
    @State private var drawn = false

    var body: some View {
        ZStack {
            ArrowArcShape(index: index, count: count)
                .trim(from: 0, to: drawn ? 1 : 0)
                .stroke(JolColor.brand, style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
            ArrowHeadShape(index: index, count: count)
                .fill(JolColor.brand)
                .opacity(drawn ? 1 : 0)
        }
        .onAppear {
            withAnimation(reduceMotion ? nil : .easeOut(duration: 0.5)) { drawn = true }
        }
        .accessibilityHidden(true)
    }
}

private struct ArrowArcShape: Shape {
    let index: Int
    var count: Double

    var animatableData: Double {
        get { count }
        set { count = newValue }
    }

    func path(in rect: CGRect) -> Path {
        guard let arc = RingGeometry.arc(index: index, count: count) else { return Path() }
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = RingGeometry.ringRadius(count: count)
        let points = RingGeometry.arcPoints(start: arc.start, end: arc.end, radius: radius)
        var path = Path()
        for (offset, point) in points.enumerated() {
            let absolute = CGPoint(x: center.x + point.x, y: center.y + point.y)
            if offset == 0 {
                path.move(to: absolute)
            } else {
                path.addLine(to: absolute)
            }
        }
        return path
    }
}

private struct ArrowHeadShape: Shape {
    let index: Int
    var count: Double

    var animatableData: Double {
        get { count }
        set { count = newValue }
    }

    func path(in rect: CGRect) -> Path {
        guard let arc = RingGeometry.arc(index: index, count: count) else { return Path() }
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let points = RingGeometry.head(end: arc.end, radius: RingGeometry.ringRadius(count: count))
            .map { CGPoint(x: center.x + $0.x, y: center.y + $0.y) }
        var path = Path()
        path.move(to: points[0])
        path.addLine(to: points[1])
        path.addLine(to: points[2])
        path.closeSubpath()
        return path
    }
}
