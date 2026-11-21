import SwiftUI

/// Full-screen map with a visible OSM attribution.
struct MapScreen: View {
    @State private var showAppleSignIn = false

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
        .overlay(alignment: .bottomLeading) {
            Button {
                showAppleSignIn = true
            } label: {
                Image(systemName: "person.crop.circle")
                    .font(.title2)
                    .padding(10)
                    .background(.thinMaterial, in: Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Sign In", tableName: "AppleSignIn"))
            .accessibilityIdentifier("open-apple-sign-in")
            .padding(8)
        }
        .sheet(isPresented: $showAppleSignIn) {
            AppleSignInView()
        }
    }
}
