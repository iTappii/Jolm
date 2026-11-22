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
                            Image(systemName: "checkmark").foregroundStyle(JolColor.brandText)
                                .accessibilityHidden(true)
                        }
                    }
                    .frame(minHeight: JolTarget.minimum)
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
