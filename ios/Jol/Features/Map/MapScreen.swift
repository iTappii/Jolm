import SwiftUI

/// Full-screen map layer. `HomeScreen` puts the chat, profile button and attribution label on top.
struct MapScreen: View {
    let places: PlacesModel
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
            bottomInset: bottomInset,
            onRegionChange: { places.regionChanged($0) },
            onSelect: { places.select($0) },
            onTapEmpty: { places.clearSelection() }
        )
        .ignoresSafeArea()
    }
}
