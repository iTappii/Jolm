import SwiftUI
import UIKit

/// The live route on the map behind the chat (Ш-54, SSOT §11.1): numbered stops in the brand colour, the other
/// candidates as small pale pins, straight edges between consecutive stops, and over each edge a capsule with the
/// way of getting there and the time. SwiftUI on top of the map, positioned by `MapProjection`.
struct LiveRouteOverlay: View {
    let route: LiveRoute
    let projection: MapProjection
    let language: String
    var isChoosing = false
    var error: LiveRouteError?
    var onChoose: (LiveStop, LivePlace) -> Void = { _, _ in }
    var onOpenPlace: (LivePlace) -> Void = { _ in }
    var onDismissError: () -> Void = {}

    /// The chat keeps the keyboard after sending; a tap on the map means the person is looking there, so the
    /// keyboard goes away and the «Choose this instead» card is not hidden under it.
    @MainActor static func hideKeyboard() {
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }

    @State private var picked: Picked?

    /// An alternative the person tapped: the "Choose this instead" card is up for it.
    struct Picked: Equatable {
        let stop: LiveStop
        let place: LivePlace
    }

    static let pinSize: CGFloat = 30
    static let alternativeSize: CGFloat = 20
    static let labelOffset: CGFloat = 20
    static let captionWidth: CGFloat = 104

    var body: some View {
        ZStack {
            canvas
            VStack(spacing: JolSpacing.sm) {
                if let picked { chooseCard(picked) }
                if let error { errorToast(error) }
                Spacer(minLength: 0)
            }
            .padding(.top, 60)
            .padding(.horizontal, JolSpacing.lg)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        }
        .animation(.spring(duration: 0.45), value: route)
        .animation(.snappy(duration: 0.25), value: picked)
        .onChange(of: route) { _, _ in picked = nil }
    }

    // MARK: - Map layer

    /// Screen positions of everything, with the collision rules applied (`LiveRouteLayout`).
    private struct Resolved {
        var stopPoints: [Int: CGPoint] = [:]
        var alternativePoints: [UUID: CGPoint] = [:]
        var edgePoints: [String: (CGPoint, CGPoint)] = [:]
        var capsuleCenters: [String: CGPoint] = [:]
        var captionSides: [Int: LiveRouteLayout.CaptionSide] = [:]
    }

    private func edgeText(_ edge: LiveEdge) -> String {
        LiveRouteFormatting.duration(edge.leg.durationS, language: language)
    }

    private func resolve() -> Resolved {
        var result = Resolved()
        for stop in route.stops {
            if let point = projection.point(for: stop.place.coordinate) { result.stopPoints[stop.ord] = point }
            for place in stop.alternatives {
                if let point = projection.point(for: place.coordinate) { result.alternativePoints[place.id] = point }
            }
        }
        var blockers = result.alternativePoints.values.map {
            LiveRouteLayout.rect(center: $0, size: CGSize(width: 28, height: 28))
        }
        let pins = Array(result.stopPoints.values)
        var placedCapsules: [CGRect] = []
        for edge in route.edges where edge.leg.mode != nil {
            guard let from = projection.point(for: edge.from), let to = projection.point(for: edge.to) else { continue }
            result.edgePoints[edge.id] = (from, to)
            let size = LiveRouteLayout.capsuleSize(text: edgeText(edge))
            let center = LiveRouteLayout.capsuleCenter(
                from: from, to: to, offset: Self.labelOffset, size: size, avoiding: pins,
                alternatives: Array(result.alternativePoints.values), otherCapsules: placedCapsules)
            result.capsuleCenters[edge.id] = center
            let frame = LiveRouteLayout.rect(center: center, size: size)
            placedCapsules.append(frame)
            blockers.append(frame)
        }
        blockers += pins.map(LiveRouteLayout.pinRect)
        let captioned = route.stops.compactMap { stop in
            result.stopPoints[stop.ord].map { (stop.ord, LiveRouteLayout.Caption(pin: $0, size: captionSize(stop))) }
        }
        let sides = LiveRouteLayout.captionSides(captioned.map(\.1), blockers: blockers)
        for (index, item) in captioned.enumerated() { result.captionSides[item.0] = sides[index] }
        return result
    }

    private func captionSize(_ stop: LiveStop) -> CGSize {
        CGSize(width: min(Self.captionWidth, 12 + CGFloat(stop.place.name.count) * 6.5), height: 20)
    }

    private var canvas: some View {
        let resolved = resolve()
        // Draw order: edges < alternatives < capsules < stop pins < captions.
        return ZStack(alignment: .topLeading) {
            ForEach(route.edges) { edge in
                if let points = resolved.edgePoints[edge.id] {
                    EdgeLine(from: points.0, to: points.1)
                        .transition(.opacity)
                }
            }
            ForEach(route.stops) { stop in
                ForEach(stop.alternatives) { place in
                    if let point = resolved.alternativePoints[place.id] {
                        alternativePin(stop: stop, place: place, at: point)
                            .transition(.scale(scale: 0.3).combined(with: .opacity))
                    }
                }
            }
            ForEach(route.edges) { edge in
                if let center = resolved.capsuleCenters[edge.id] {
                    edgeLabel(edge, center: center)
                        .transition(.scale(scale: 0.6).combined(with: .opacity))
                }
            }
            ForEach(route.stops) { stop in
                if let point = resolved.stopPoints[stop.ord] {
                    stopPin(stop, at: point)
                        .transition(.scale(scale: 0.3).combined(with: .opacity))
                }
            }
            ForEach(route.stops) { stop in
                if let point = resolved.stopPoints[stop.ord], let side = resolved.captionSides[stop.ord],
                   side != .hidden {
                    caption(stop.place.name, at: point, side: side)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .ignoresSafeArea()
        // Labels on a map keep a bounded size (the capsules are laid out by an estimate of the text width); what they
        // say is in the VoiceOver labels, and the cards below scale freely.
        .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(Text("Route on the map"))
    }

    /// VoiceOver walks the route in its own order: stop 1, its alternatives, the leg to stop 2, stop 2, … (higher
    /// priority is read first). Stops are spaced 10 apart so the alternatives and the leg fit between them.
    private func order(stop number: Int, offset: Int = 0) -> Double {
        Double(10_000 - number * 10 - offset)
    }

    private func stopPin(_ stop: LiveStop, at point: CGPoint) -> some View {
        let number = route.number(of: stop)
        return Button {
            Self.hideKeyboard()
            onOpenPlace(stop.place)
        } label: {
            ZStack {
                Circle().fill(JolColor.brand)
                Circle().stroke(Color.white, lineWidth: 2.5)
                Text(verbatim: String(number))
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(JolColor.onBrand)
            }
            .frame(width: Self.pinSize, height: Self.pinSize)
            .shadow(color: .black.opacity(0.35), radius: 2, y: 1)
            .minTapTarget()
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(verbatim: LiveRouteFormatting.spokenStop(
            number: number, name: stop.place.name, language: language)))
        .accessibilityHint(Text("Shows the place card"))
        .accessibilitySortPriority(order(stop: number))
        .accessibilityIdentifier("live-stop-\(number)")
        .offset(x: point.x - 22, y: point.y - 22)
    }

    /// The name of a stop, below its pin (or above when the rules moved it). Not interactive; VoiceOver has the name in
    /// the pin's label.
    private func caption(_ name: String, at point: CGPoint, side: LiveRouteLayout.CaptionSide) -> some View {
        let distance = LiveRouteLayout.pinRadius + LiveRouteLayout.captionGap + 10
        return Text(verbatim: name)
            .font(.caption2.weight(.semibold))
            .foregroundStyle(JolColor.textPrimary)
            .lineLimit(1)
            .truncationMode(.tail)
            .frame(maxWidth: Self.captionWidth)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(.regularMaterial, in: Capsule())
            .frame(width: Self.captionWidth + 12, height: 20)
            .offset(
                x: point.x - (Self.captionWidth + 12) / 2,
                y: point.y + (side == .above ? -distance : distance) - 10
            )
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }

    private func alternativePin(stop: LiveStop, place: LivePlace, at point: CGPoint) -> some View {
        Button {
            Self.hideKeyboard()
            picked = Picked(stop: stop, place: place)
        } label: {
            Circle()
                .fill(JolColor.brand.opacity(0.4))
                .overlay(Circle().stroke(JolColor.brand, lineWidth: 2))
                .overlay(Circle().stroke(Color.white.opacity(0.9), lineWidth: 1).padding(-1))
                .frame(width: Self.alternativeSize, height: Self.alternativeSize)
                .minTapTarget()
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text(verbatim: LiveRouteFormatting.spokenAlternative(name: place.name, language: language)))
        .accessibilityHint(Text("Choose this instead"))
        .accessibilitySortPriority(order(stop: route.number(of: stop), offset: -1))
        .accessibilityIdentifier("live-alt-\(stop.ord)-\(place.id.uuidString.lowercased())")
        .offset(x: point.x - 22, y: point.y - 22)
    }

    @ViewBuilder
    private func edgeLabel(_ edge: LiveEdge, center: CGPoint) -> some View {
        if let mode = edge.leg.mode {
            HStack(spacing: 4) {
                Image(systemName: LiveRouteFormatting.symbol(mode))
                    .imageScale(.small)
                Text(verbatim: edgeText(edge))
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(JolColor.textPrimary)
            .padding(.horizontal, 9)
            .padding(.vertical, 4)
            .background(.regularMaterial, in: Capsule())
            .overlay(Capsule().stroke(JolColor.separator, lineWidth: 0.5))
            .shadow(color: .black.opacity(0.2), radius: 2, y: 1)
            .fixedSize()
            .frame(width: 200, height: 44)
            .offset(x: center.x - 100, y: center.y - 22)
            .allowsHitTesting(false)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(Text(verbatim: LiveRouteFormatting.spokenEdge(edge, language: language)))
            .accessibilitySortPriority(order(stop: edge.fromNumber, offset: -5))
            .accessibilityIdentifier("live-edge-\(edge.fromNumber)-\(edge.toNumber)")
        }
    }

}

// MARK: - Cards

extension LiveRouteOverlay {

    private func chooseCard(_ picked: Picked) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(verbatim: picked.place.name).font(JolFont.headline).accessibilityAddTraits(.isHeader)
                    if let category = picked.place.category {
                        Text(verbatim: category).font(.caption).foregroundStyle(JolColor.textSecondary)
                    }
                }
                Spacer(minLength: 0)
                Button { self.picked = nil } label: {
                    Image(systemName: "xmark.circle.fill").font(.title3).foregroundStyle(JolColor.textSecondary)
                        .minTapTarget()
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text("Close"))
                .accessibilityHint(Text("Keeps the current stop"))
                .accessibilityIdentifier("live-choose-close")
            }
            AdaptiveStack(spacing: JolSpacing.sm) {
                Button { onChoose(picked.stop, picked.place) } label: {
                    HStack {
                        if isChoosing { ProgressView().controlSize(.small) }
                        Text("Choose this instead").font(.subheadline.weight(.semibold))
                    }
                    .foregroundStyle(JolColor.onBrand)
                    .padding(.horizontal, 14)
                    .frame(minHeight: 44)
                    .background(JolColor.brand, in: Capsule())
                }
                .buttonStyle(.plain)
                .disabled(isChoosing)
                .accessibilityIdentifier("live-choose-confirm")
                Button { self.picked = nil; onOpenPlace(picked.place) } label: {
                    Text("Details").font(.subheadline.weight(.semibold)).foregroundStyle(JolColor.brandText)
                        .padding(.horizontal, 10).frame(minHeight: 44).contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("live-choose-details")
            }
        }
        .padding(JolSpacing.md)
        .frame(maxWidth: 420, alignment: .leading)
        // The card hangs over the map above the chat card: past xxxLarge it would reach the chat (seen at AX3).
        .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: .black.opacity(0.2), radius: 6, y: 2)
        .transition(.move(edge: .top).combined(with: .opacity))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("live-choose-card")
    }

    private static func message(for error: LiveRouteError) -> LocalizedStringKey {
        switch error {
        case .outdated: "That choice is no longer available."
        case .busy: "The assistant is still answering. Try again in a moment."
        case .network: "Couldn't change the stop. Try again."
        }
    }

    private func errorToast(_ error: LiveRouteError) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(JolColor.danger)
            Text(Self.message(for: error))
                .font(.footnote.weight(.semibold))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(.regularMaterial, in: Capsule())
        .shadow(color: .black.opacity(0.2), radius: 4, y: 1)
        .transition(.move(edge: .top).combined(with: .opacity))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("live-route-error")
        .task(id: error) {
            try? await Task.sleep(for: .seconds(4))
            if !Task.isCancelled { onDismissError() }
        }
    }
}

/// A straight edge between two stops: white casing under the brand line, drawn from the first stop to the second.
private struct EdgeLine: View {
    let from: CGPoint
    let to: CGPoint
    @State private var progress: CGFloat = 0

    var body: some View {
        let path = Path { path in
            path.move(to: from)
            path.addLine(to: to)
        }
        ZStack {
            path.trim(from: 0, to: progress)
                .stroke(Color.white, style: StrokeStyle(lineWidth: 7, lineCap: .round))
            path.trim(from: 0, to: progress)
                .stroke(JolColor.brand, style: StrokeStyle(lineWidth: 4, lineCap: .round))
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
        .onAppear { withAnimation(.easeOut(duration: 0.5)) { progress = 1 } }
    }
}
