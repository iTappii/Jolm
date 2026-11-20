import SwiftUI

/// Full-screen map with a visible OSM attribution.
struct MapScreen: View {
    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            MapView(styleURL: AppConfig.mapStyleURL)
                .ignoresSafeArea()
            Text("© OpenStreetMap contributors")
                .font(.caption2)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(.thinMaterial, in: Capsule())
                .padding(8)
                .accessibilityIdentifier("osm-attribution")
        }
    }
}
