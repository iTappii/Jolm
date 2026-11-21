import SwiftUI

/// Language list: System / Русский / English. Applies immediately (see `RootView`), no restart.
struct LanguageScreen: View {
    @Environment(AppContainer.self) private var container

    var body: some View {
        List {
            ForEach(AppLanguage.allCases) { option in
                Button {
                    container.language.selection = option
                } label: {
                    HStack {
                        if let name = option.nativeName {
                            Text(verbatim: name)
                        } else {
                            Text("System")
                        }
                        Spacer()
                        if container.language.selection == option {
                            Image(systemName: "checkmark").foregroundStyle(JolColor.brand)
                        }
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .foregroundStyle(JolColor.textPrimary)
                .accessibilityIdentifier("language-\(option.rawValue)")
                .accessibilityAddTraits(container.language.selection == option ? .isSelected : [])
            }
        }
        .navigationTitle(Text("Language"))
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct SettingsScreen: View {
    var body: some View {
        List {
            Section {
                Text("More settings will appear here.")
                    .foregroundStyle(JolColor.textSecondary)
            }
        }
        .navigationTitle(Text("Settings"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("settings-screen")
    }
}

struct HelpScreen: View {
    var body: some View {
        List {
            Section {
                Text("The help center is being prepared.")
                    .foregroundStyle(JolColor.textSecondary)
            }
        }
        .navigationTitle(Text("Help"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("help-screen")
    }
}

struct AboutScreen: View {
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
                Text("© OpenStreetMap contributors")
                    .accessibilityIdentifier("about-osm")
                Text("Map rendering by MapLibre Native.")
                    .accessibilityIdentifier("about-maplibre")
            } header: {
                Text("Map data")
            }
        }
        .navigationTitle(Text("About"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("about-screen")
    }
}
