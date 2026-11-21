import SwiftUI

/// The single-branch graph of theses (SSOT §11.2): a vertical line with one dot and one chip per thesis. Nodes
/// appear with a spring as the conversation goes; when the route is ready the line bends into one final node
/// "Route ready" and the dots turn solid.
struct ChatGraphView: View {
    let nodes: [GraphNode]
    let converged: Bool

    private static let railWidth: CGFloat = 16
    private static let dotSize: CGFloat = 10
    private static let dotTop: CGFloat = 12

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(nodes.enumerated()), id: \.element.ord) { index, node in
                row(node, isFirst: index == 0, isLast: index == nodes.count - 1)
                    .transition(.asymmetric(
                        insertion: .scale(scale: 0.6, anchor: .topLeading).combined(with: .opacity),
                        removal: .opacity
                    ))
            }
            if converged {
                finalRow
                    .transition(.scale(scale: 0.6, anchor: .topLeading).combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.5, bounce: 0.25), value: nodes)
        .animation(.spring(duration: 0.6, bounce: 0.2), value: converged)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("chat-graph")
    }

    private func row(_ node: GraphNode, isFirst: Bool, isLast: Bool) -> some View {
        let continues = !isLast || converged
        return HStack(alignment: .top, spacing: JolSpacing.sm) {
            ZStack(alignment: .top) {
                // The line runs through the dot: from the top edge (not for the first dot) to the bottom edge
                // (not for the last dot while the graph is still growing).
                Rectangle()
                    .fill(JolColor.brand.opacity(0.45))
                    .frame(width: 2)
                    .padding(.top, isFirst ? Self.dotTop + Self.dotSize / 2 : 0)
                    .frame(maxHeight: continues ? .infinity : Self.dotTop + Self.dotSize / 2, alignment: .top)
                Circle()
                    .fill(converged ? JolColor.brand : JolColor.surfaceElevated)
                    .overlay(Circle().stroke(JolColor.brand, lineWidth: 2))
                    .frame(width: Self.dotSize, height: Self.dotSize)
                    .padding(.top, Self.dotTop)
            }
            .frame(width: Self.railWidth)
            Text(verbatim: node.text)
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textPrimary)
                .padding(.horizontal, JolSpacing.md)
                .padding(.vertical, JolSpacing.xs + 2)
                .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
                .overlay(
                    RoundedRectangle(cornerRadius: JolRadius.md)
                        .stroke(converged ? JolColor.brand.opacity(0.5) : .clear, lineWidth: 1)
                )
                .padding(.vertical, 3)
                .accessibilityIdentifier("graph-node-\(node.ord)")
        }
    }

    /// The branch ends here: the rail turns through a rounded elbow into the "Route ready" capsule.
    private var finalRow: some View {
        HStack(alignment: .top, spacing: 0) {
            ConvergeElbow()
                .stroke(JolColor.brand.opacity(0.45), lineWidth: 2)
                .frame(width: Self.railWidth + JolSpacing.sm + 6, height: 20)
            HStack(spacing: JolSpacing.xs + 2) {
                Image(systemName: "checkmark.circle.fill")
                Text("Route ready")
            }
            .font(JolFont.headline)
            .foregroundStyle(JolColor.onBrand)
            .padding(.horizontal, JolSpacing.md)
            .padding(.vertical, JolSpacing.sm)
            .background(JolColor.brand, in: Capsule())
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("graph-final")
        }
        .padding(.top, 2)
    }
}

/// Vertical rail that bends right at the bottom: from the dot column into the final capsule.
private struct ConvergeElbow: Shape {
    func path(in rect: CGRect) -> Path {
        let rail = 7.0
        let radius = min(12, rect.height)
        var path = Path()
        path.move(to: CGPoint(x: rail, y: 0))
        path.addLine(to: CGPoint(x: rail, y: rect.maxY - radius))
        path.addQuadCurve(
            to: CGPoint(x: rail + radius, y: rect.maxY),
            control: CGPoint(x: rail, y: rect.maxY)
        )
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        return path
    }
}
