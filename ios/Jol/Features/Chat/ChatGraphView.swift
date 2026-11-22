import SwiftUI

/// The answer chain (SSOT §11.2): a strip at the top of the chat card, under the header. Every node is an answer of
/// the tourist that filled a field of the brief (days, budget, lodging, a wish, …); the value they gave stands next to
/// the node. Nodes go left to right in the order of the answers with a gentle wave, joined by straight lines; the chain
/// is centred while it fits and the strip scrolls (to the newest node) when it does not. A new node comes in from the
/// right and the others slide to re-centre; a changed answer only changes its label. When the route is ready a finish
/// node (a flag) ends the chain. Tapping a node shows its full value (see `ChatChainFooter`).
struct ChatGraphView: View {
    let nodes: [ChainNode]
    let brief: ChatBrief
    let finished: Bool
    @Binding var selected: String?

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.locale) private var locale

    /// Nodes on the strip: the answers, plus the finish node once the route is ready.
    private var total: Int { nodes.count + (finished ? 1 : 0) }

    var body: some View {
        GeometryReader { proxy in
            strip(viewport: proxy.size.width)
        }
        .frame(height: ChainGeometry.height)
        .onChange(of: nodes.map(\.key)) { _, keys in
            if let selected, !keys.contains(selected) { self.selected = nil }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(summary)
        .accessibilityValue(finished ? "ready" : "building")
        .accessibilityIdentifier("chat-chain")
    }

    private func full(_ node: ChainNode) -> String {
        ChainLabels.full(node, brief: brief, locale: locale)
    }

    private func strip(viewport: CGFloat) -> some View {
        let count = Double(total)
        let width = ChainGeometry.contentWidth(count: count, viewport: viewport)
        return ScrollViewReader { reader in
            ScrollView(.horizontal, showsIndicators: false) {
                ZStack(alignment: .topLeading) {
                    ForEach(0..<ChainGeometry.connectorCount(nodes: total), id: \.self) { index in
                        ChainConnector(index: index, count: count, viewport: viewport)
                            .stroke(JolColor.brand, style: StrokeStyle(lineWidth: 1.8, lineCap: .round))
                            .transition(.opacity)
                    }
                    ForEach(Array(nodes.enumerated()), id: \.element.key) { index, node in
                        dot(node, index: index, count: count, viewport: viewport)
                        label(node, index: index, count: count, viewport: viewport)
                    }
                    if finished {
                        finishNode(index: nodes.count, count: count, viewport: viewport)
                    }
                    // The end of the content, for scrolling to the newest node.
                    Color.clear.frame(width: 1, height: 1).padding(.leading, width - 1).id("chain-end")
                }
                .frame(width: width, height: ChainGeometry.height, alignment: .topLeading)
            }
            // The content grows in the same transaction as the count: scroll once the layout has caught up.
            .task(id: total) {
                try? await Task.sleep(nanoseconds: 120_000_000)
                withAnimation(reduceMotion ? nil : .easeOut(duration: 0.4)) {
                    reader.scrollTo("chain-end", anchor: .trailing)
                }
            }
        }
        .animation(reduceMotion ? nil : .spring(duration: 0.55, bounce: 0.15), value: total)
    }

    private func dot(_ node: ChainNode, index: Int, count: Double, viewport: CGFloat) -> some View {
        let isSelected = node.key == selected
        let center = ChainGeometry.nodeCenter(index: Double(index), count: count, viewport: viewport)
        return Button {
            selected = isSelected ? nil : node.key
        } label: {
            Image(systemName: Self.symbol(node.kind))
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(JolColor.onBrand)
                .frame(width: ChainGeometry.nodeRadius * 2, height: ChainGeometry.nodeRadius * 2)
                .background(JolColor.brand, in: Circle())
                .overlay(Circle().stroke(isSelected ? JolColor.textPrimary : JolColor.surfaceElevated, lineWidth: 1.5))
                // The dot stays small, the finger gets 44 pt (the nodes are 66 pt apart, so they do not overlap).
                .minTapTarget()
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(verbatim: ChainLabels.spoken(node, index: index, brief: brief, locale: locale)))
        .accessibilityHint(Text(isSelected ? "Hides the full value" : "Shows the full value"))
        .accessibilityAddTraits(isSelected ? .isSelected : [])
        .accessibilityIdentifier("graph-node-\(index + 1)")
        .position(center)
        .transition(.opacity.combined(with: .offset(x: ChainGeometry.step, y: 0)))
    }

    /// The value next to a node: above a high node, below a low one. Decorative for VoiceOver (the node carries it).
    private func label(_ node: ChainNode, index: Int, count: Double, viewport: CGFloat) -> some View {
        Text(verbatim: ChainLabels.short(node, brief: brief, locale: locale))
            .font(.system(size: 10, weight: node.key == selected ? .bold : .medium))
            .foregroundStyle(JolColor.textPrimary)
            .lineLimit(1)
            .frame(width: ChainGeometry.labelWidth, height: ChainGeometry.labelHeight)
            .position(ChainGeometry.labelCenter(index: index, count: count, viewport: viewport))
            .allowsHitTesting(false)
            .accessibilityHidden(true)
            .transition(.opacity)
    }

    /// The route is ready: a flag node closes the chain.
    private func finishNode(index: Int, count: Double, viewport: CGFloat) -> some View {
        let center = ChainGeometry.nodeCenter(index: Double(index), count: count, viewport: viewport)
        return Image(systemName: "flag.checkered")
            .font(.system(size: 9, weight: .bold))
            .foregroundStyle(JolColor.brandText)
            .frame(width: ChainGeometry.nodeRadius * 2, height: ChainGeometry.nodeRadius * 2)
            .background(JolColor.surface, in: Circle())
            .overlay(Circle().stroke(JolColor.brand, lineWidth: 1.8))
            .accessibilityLabel(Text("Route ready"))
            .accessibilityIdentifier("graph-chain-finish")
            .position(center)
            .transition(.opacity.combined(with: .offset(x: ChainGeometry.step, y: 0)))
    }

    private static func symbol(_ kind: ChainNode.Kind) -> String {
        switch kind {
        case .dates: "calendar"
        case .budget: "banknote"
        case .lodging: "bed.double.fill"
        case .mustHave: "star.fill"
        case .interests: "sparkles"
        case .pace: "figure.walk"
        case .crowd: "person.2.fill"
        }
    }

    private var summary: Text {
        finished ? Text("\(nodes.count) answers, route is ready") : Text("\(nodes.count) answers, route is not ready")
    }
}

/// What goes with the chain under the strip, above the messages: the full value of a tapped node (and the AI's
/// thesis, if any) and, once the route is ready, «Open full map».
struct ChatChainFooter: View {
    let nodes: [ChainNode]
    let brief: ChatBrief
    /// Theses the AI wrote (`graph_node`): the detail of a tapped node, never nodes of their own.
    let theses: [GraphNode]
    let finished: Bool
    let selected: String?
    let onDeselect: () -> Void
    let onOpenRoute: () -> Void
    @Environment(\.locale) private var locale

    private var selectedIndex: Int? { nodes.firstIndex { $0.key == selected } }

    var body: some View {
        VStack(alignment: .trailing, spacing: JolSpacing.sm) {
            if let index = selectedIndex {
                detail(nodes[index], index: index)
            }
            if finished {
                openButton
            }
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
        .padding(.bottom, JolSpacing.xs)
    }

    private func full(_ node: ChainNode) -> String {
        ChainLabels.full(node, brief: brief, locale: locale)
    }

    private func detail(_ node: ChainNode, index: Int) -> some View {
        VStack(alignment: .trailing, spacing: 2) {
            Text(verbatim: full(node))
                .font(JolFont.caption.weight(.semibold))
                .foregroundStyle(JolColor.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("graph-node-detail")
            if let thesis = theses.first(where: { $0.ord == index + 1 })?.text, thesis != full(node) {
                Text(verbatim: thesis)
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityIdentifier("graph-node-thesis")
            }
        }
        .multilineTextAlignment(.trailing)
        .padding(.horizontal, JolSpacing.md)
        .padding(.vertical, JolSpacing.xs + 2)
        .background {
            RoundedRectangle(cornerRadius: JolRadius.md).fill(JolColor.surface)
            RoundedRectangle(cornerRadius: JolRadius.md).stroke(JolColor.brand.opacity(0.7), lineWidth: 1)
        }
        .onTapGesture { onDeselect() }
        .accessibilityElement(children: .contain)
        .accessibilityAction(named: Text("Hide details")) { onDeselect() }
    }

    private var openButton: some View {
        Button(action: onOpenRoute) {
            Label("Open full map", systemImage: "map.fill")
                .font(JolFont.callout.weight(.semibold))
                .foregroundStyle(JolColor.onBrand)
                .padding(.horizontal, JolSpacing.md)
                .padding(.vertical, JolSpacing.sm)
                .frame(minHeight: JolTarget.minimum)
                .background(JolColor.brand, in: Capsule())
        }
        .buttonStyle(.plain)
        .transition(.scale(scale: 0.8, anchor: .trailing).combined(with: .opacity))
        .accessibilityHint(Text("Opens the whole route on the map"))
        .accessibilityIdentifier("chat-open-route")
    }
}

/// One connector of the chain: a straight segment between two neighbouring nodes. Animatable by the node count, so it
/// follows its nodes while they slide.
private struct ChainConnector: Shape {
    let index: Int
    var count: Double
    let viewport: CGFloat

    var animatableData: Double {
        get { count }
        set { count = newValue }
    }

    func path(in rect: CGRect) -> Path {
        let curve = ChainGeometry.connector(index: index, count: count, viewport: viewport)
        var path = Path()
        path.move(to: curve.start)
        path.addLine(to: curve.end)
        return path
    }
}
