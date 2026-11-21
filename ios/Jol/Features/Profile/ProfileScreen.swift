import SwiftUI

/// Placeholder; Ш-16 builds the real profile menu. The language picker is here already because
/// the language override (`LanguageSettings`) must be switchable at runtime.
struct ProfileScreen: View {
    var body: some View {
        Form {
            Section {
                LanguagePicker()
            }
        }
        .navigationTitle(Text("Profile"))
    }
}

/// System / Русский / English. Changing it re-renders the whole UI immediately (see `RootView`).
struct LanguagePicker: View {
    @Environment(AppContainer.self) private var container

    var body: some View {
        @Bindable var language = container.language
        Picker("Language", selection: $language.selection) {
            ForEach(AppLanguage.allCases) { option in
                if let name = option.nativeName {
                    Text(verbatim: name).tag(option)
                } else {
                    Text("System").tag(option)
                }
            }
        }
        .pickerStyle(.segmented)
        .accessibilityIdentifier("language-picker")
    }
}
