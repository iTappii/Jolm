import SwiftUI

/// Main sights on the home map (Ш-69, SSOT §13): a round category marker with the name under it, drawn from the
/// sight's `minZoom` up. SwiftUI on top of the map, positioned by `MapProjection` like the live route, so each marker
/// is a VoiceOver element and a 44 pt target. The home screen does not draw it while the live route, the full route
/// map or a way to a place is on the map: those show their own stops, and the sights would only crowd them.
struct LandmarksOverlay: View {
    let landmarks: [Landmark]
    let projection: MapProjection
    let onOpen: (Landmark) -> Void

    var body: some View {
        GeometryReader { proxy in
            let placed = LandmarkLayout.visible(
                landmarks, zoom: projection.zoom,
                viewport: CGRect(origin: .zero, size: proxy.size)
            ) { projection.point(for: $0) }
            ZStack(alignment: .topLeading) {
                ForEach(placed, id: \.landmark.id) { item in
                    marker(item.landmark)
                        .offset(
                            x: item.point.x - Self.cellWidth / 2,
                            y: item.point.y - LandmarkLayout.markerSize / 2
                        )
                        .transition(.opacity)
                }
            }
            .frame(width: proxy.size.width, height: proxy.size.height, alignment: .topLeading)
            .animation(.easeOut(duration: 0.25), value: placed.map(\.landmark.id))
        }
        .ignoresSafeArea()
        // The label's width is laid out by an estimate, so it keeps a bounded size.
        .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
        .accessibilityElement(children: .contain)
        .accessibilityLabel(Text("Main sights"))
    }

    private static let cellWidth = LandmarkLayout.maxLabelWidth + 20

    private func marker(_ landmark: Landmark) -> some View {
        Button {
            onOpen(landmark)
        } label: {
            VStack(spacing: LandmarkLayout.labelGap) {
                drawing(landmark)
                    .frame(width: LandmarkLayout.markerSize, height: LandmarkLayout.markerSize)
                Text(verbatim: landmark.name)
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(LandmarkPalette.label)
                    .lineLimit(1)
                    .truncationMode(.tail)
                    .frame(maxWidth: LandmarkLayout.maxLabelWidth)
                    .frame(height: LandmarkLayout.labelHeight)
                    .haloed()
            }
            .frame(minWidth: 44, minHeight: LandmarkLayout.markerSize)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .frame(width: Self.cellWidth, alignment: .top)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("\(landmark.name), landmark"))
        .accessibilityHint(Text("Shows the place card"))
        .accessibilityAddTraits(.isButton)
        .accessibilitySortPriority(Double(1000 - landmark.rank))
        .accessibilityIdentifier("landmark-\(landmark.id.uuidString.lowercased())")
    }

    /// The sight's own line drawing, in the map's muted colour; without one, the category's pin.
    @ViewBuilder
    private func drawing(_ landmark: Landmark) -> some View {
        if let name = LandmarkIcon.assetName(for: landmark.icon) {
            Image(name)
                .renderingMode(.template)
                .resizable()
                .scaledToFit()
                .foregroundStyle(LandmarkPalette.drawing)
                .haloed()
        } else {
            let pin = PlaceCategoryStyle.style(for: landmark.category).pinImage(diameter: LandmarkLayout.markerSize)
            Image(uiImage: pin)
                .shadow(color: .black.opacity(0.3), radius: 2, y: 1)
        }
    }
}

private extension View {
    /// A thin outline in the map's halo colour, so the drawing and the name stay readable over roads and parks.
    func haloed() -> some View {
        shadow(color: LandmarkPalette.halo, radius: 0.5)
            .shadow(color: LandmarkPalette.halo, radius: 0.5)
            .shadow(color: LandmarkPalette.halo.opacity(0.8), radius: 1.5)
    }
}
