import SwiftUI

/// Full-screen map layer. `HomeScreen` puts the chat, profile button and attribution label on top.
struct MapScreen: View {
    let places: PlacesModel
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
            bottomInset: bottomInset,
            onRegionChange: { places.regionChanged($0) },
            onSelect: { places.select($0) },
            onTapEmpty: { places.clearSelection() }
        )
        .ignoresSafeArea()
    }
}
