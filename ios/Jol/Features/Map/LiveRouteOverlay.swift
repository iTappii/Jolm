import SwiftUI

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

    @State private var picked: Picked?

    /// An alternative the person tapped: the "Choose this instead" card is up for it.
    struct Picked: Equatable {
        let stop: LiveStop
        let place: LivePlace
    }

    static let pinSize: CGFloat = 30
    static let alternativeSize: CGFloat = 20
    static let labelOffset: CGFloat = 20

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

    private var canvas: some View {
        ZStack(alignment: .topLeading) {
            ForEach(route.edges) { edge in
                if let from = projection.point(for: edge.from), let to = projection.point(for: edge.to) {
                    EdgeLine(from: from, to: to)
                        .transition(.opacity)
                }
            }
            ForEach(route.stops) { stop in
                if let point = projection.point(for: stop.place.coordinate) {
                    stopPin(stop, at: point)
                        .transition(.scale(scale: 0.3).combined(with: .opacity))
                }
            }
            ForEach(route.stops) { stop in
                ForEach(stop.alternatives) { place in
                    if let point = projection.point(for: place.coordinate) {
                        alternativePin(stop: stop, place: place, at: point)
                            .transition(.scale(scale: 0.3).combined(with: .opacity))
                    }
                }
            }
            ForEach(route.edges) { edge in
                if let from = projection.point(for: edge.from), let to = projection.point(for: edge.to) {
                    edgeLabel(edge, from: from, to: to)
                        .transition(.scale(scale: 0.6).combined(with: .opacity))
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .ignoresSafeArea()
    }

    private func stopPin(_ stop: LiveStop, at point: CGPoint) -> some View {
        let number = route.number(of: stop)
        let name = stop.place.name
        return ZStack(alignment: .topLeading) {
            Button { onOpenPlace(stop.place) } label: {
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
                number: number, name: name, language: language)))
            .accessibilityIdentifier("live-stop-\(number)")
        }
        .frame(width: 44, height: 44)
        .overlay(alignment: .top) {
            Text(verbatim: name)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(JolColor.textPrimary)
                .lineLimit(1)
                .truncationMode(.tail)
                .frame(maxWidth: 104)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(.regularMaterial, in: Capsule())
                .frame(width: 150)
                .offset(y: 40)
                .allowsHitTesting(false)
                .accessibilityHidden(true)
        }
        .offset(x: point.x - 22, y: point.y - 22)
    }

    private func alternativePin(stop: LiveStop, place: LivePlace, at point: CGPoint) -> some View {
        Button { picked = Picked(stop: stop, place: place) } label: {
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
        .accessibilityIdentifier("live-alt-\(stop.ord)-\(place.id.uuidString.lowercased())")
        .offset(x: point.x - 22, y: point.y - 22)
    }

    @ViewBuilder
    private func edgeLabel(_ edge: LiveEdge, from: CGPoint, to: CGPoint) -> some View {
        if let mode = edge.leg.mode {
            let center = LiveRouteGeometry.labelCenter(from: from, to: to, offset: Self.labelOffset)
            HStack(spacing: 4) {
                Image(systemName: LiveRouteFormatting.symbol(mode))
                    .imageScale(.small)
                Text(verbatim: LiveRouteFormatting.duration(edge.leg.durationS, language: language))
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
            .accessibilityIdentifier("live-edge-\(edge.fromNumber)-\(edge.toNumber)")
        }
    }

    // MARK: - Cards

    private func chooseCard(_ picked: Picked) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(verbatim: picked.place.name).font(JolFont.headline)
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
                .accessibilityIdentifier("live-choose-close")
            }
            HStack(spacing: JolSpacing.sm) {
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
                        .padding(.horizontal, 10).frame(minHeight: 44)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("live-choose-details")
            }
        }
        .padding(JolSpacing.md)
        .frame(maxWidth: 420, alignment: .leading)
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
