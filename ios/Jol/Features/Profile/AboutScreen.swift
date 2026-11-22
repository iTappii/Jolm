import SwiftUI

/// «О приложении» (Ш-52): version, data attributions the licences require (OpenStreetMap ODbL,
/// Overture Maps CDLA-Permissive-2.0, Foursquare OS Places Apache 2.0, Open-Meteo CC BY 4.0)
/// and the privacy policy link.
struct AboutScreen: View {
    static let osmCopyright = URL(string: "https://www.openstreetmap.org/copyright")!
    static let openMeteo = URL(string: "https://open-meteo.com/")!
    static let ccBy4 = URL(string: "https://creativecommons.org/licenses/by/4.0/")!
    static let maplibre = URL(string: "https://maplibre.org/")!
    static let overture = URL(string: "https://overturemaps.org/")!
    static let foursquare = URL(string: "https://opensource.foursquare.com/os-places/")!

    private var version: String {
        let info = Bundle.main.infoDictionary
        let short = info?["CFBundleShortVersionString"] as? String ?? "?"
        let build = info?["CFBundleVersion"] as? String ?? "?"
        return "\(short) (\(build))"
    }

    var body: some View {
        List {
            Section {
                LabeledContent("Version") { Text(verbatim: version) }
                    .accessibilityIdentifier("about-version")
            }
            Section {
                Link(destination: Self.osmCopyright) {
                    Text(verbatim: "© OpenStreetMap contributors")
                }
                .accessibilityIdentifier("about-osm")
                Link(destination: Self.overture) {
                    Text("Places data © Overture Maps Foundation (CDLA-Permissive-2.0)")
                }
                .accessibilityIdentifier("about-overture")
                Link(destination: Self.foursquare) {
                    Text("Places data © Foursquare OS Places (Apache 2.0)")
                }
                .accessibilityIdentifier("about-foursquare")
                Link(destination: Self.maplibre) {
                    Text("Map rendering by MapLibre Native.")
                }
                .accessibilityIdentifier("about-maplibre")
            } header: {
                Text("Map data")
            }
            Section {
                Link(destination: Self.openMeteo) {
                    Text(verbatim: "Weather data by Open-Meteo.com")
                }
                .accessibilityIdentifier("about-open-meteo")
                Link(destination: Self.ccBy4) {
                    Text(verbatim: "CC BY 4.0")
                }
                .accessibilityIdentifier("about-cc-by")
            } header: {
                Text("Weather")
            }
            Section {
                if let url = AppConfig.privacyPolicyURL {
                    Link(destination: url) {
                        Text("Privacy policy")
                    }
                    .accessibilityIdentifier("about-privacy")
                }
            }
        }
        .navigationTitle(Text("About"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("about-screen")
    }
}
