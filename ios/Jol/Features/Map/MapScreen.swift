import SwiftUI

/// Full-screen map layer. `HomeScreen` puts the chat, profile button and attribution label on top.
struct MapScreen: View {
    let places: PlacesModel
    var chat: ChatModel?
    var directions: DirectionsModel?
    var bottomInset: CGFloat = 0
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        MapView(
            styleURL: AppConfig.mapStyleURL(dark: colorScheme == .dark),
            pins: places.activeRoute == nil ? places.pins : [],
            pinsVersion: places.activeRoute == nil ? places.pinsVersion : -2,
            routeStops: places.routeStops,
            routeID: places.activeRoute?.id,
            selectedID: places.selected?.id,
            directionLines: directions?.lines ?? [],
            directionOrigin: directions?.origin,
            directionVersion: directions?.lineVersion ?? 0,
            directionFitVersion: directions?.fitVersion ?? 0,
            chatPlaces: chat?.state.mapPlaces ?? [],
            chatPlacesVersion: chat?.state.mapVersion ?? 0,
            bottomInset: bottomInset,
            onRegionChange: { places.regionChanged($0) },
            onSelect: { id in
                if let pin = chat?.state.mapPlaces.first(where: { $0.id == id }) {
                    places.select(pin.summary)
                } else {
                    places.select(id)
                }
            },
            onTapEmpty: { places.clearSelection() }
        )
        .ignoresSafeArea()
        #if DEBUG
        .overlay(alignment: .topTrailing) {
            if UITestSupport.isStubbed {
                Color.clear
                    .frame(width: 1, height: 1)
                    .accessibilityElement()
                    .accessibilityLabel(Text(verbatim: "chat-map-places"))
                    .accessibilityValue(Text(verbatim: String(chat?.state.mapPlaces.count ?? 0)))
                    .accessibilityIdentifier("chat-map-places")
            }
        }
        #endif
    }
}
