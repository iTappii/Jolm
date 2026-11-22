import SwiftUI

/// Profile menu (SSOT §11.4), in the style of an account menu: identity, settings, language, help, about,
/// sign out / delete account. A guest sees "Sign in" instead of the account rows.
struct ProfileMenuSheet: View {
    @Environment(AppContainer.self) private var container

    var body: some View {
        ProfileMenuContent(
            model: container.makeProfileModel(), bonuses: container.makeBonusModel(),
            bookings: container.makeBookingsModel()
        )
    }
}

private struct ProfileMenuContent: View {
    @Environment(AppContainer.self) private var container
    @Environment(\.dismiss) private var dismiss
    @State private var model: ProfileModel
    @State private var bonuses: BonusModel
    @State private var bookings: MyBookingsModel
    @State private var confirmDelete = false

    init(model: ProfileModel, bonuses: BonusModel, bookings: MyBookingsModel) {
        _model = State(initialValue: model)
        _bonuses = State(initialValue: bonuses)
        _bookings = State(initialValue: bookings)
    }

    var body: some View {
        NavigationStack {
            List {
                accountSection
                if container.auth.isSignedIn {
                    bonusSection
                    bookingsSection
                }
                Section {
                    NavigationLink { SettingsScreen() } label: {
                        Label("Settings", systemImage: "gearshape")
                    }
                    .accessibilityIdentifier("profile-settings")
                    NavigationLink { LanguageScreen() } label: {
                        LabeledContent {
                            if let name = container.language.selection.nativeName {
                                Text(verbatim: name)
                            } else {
                                Text("System")
                            }
                        } label: {
                            Label("Language", systemImage: "globe")
                        }
                    }
                    .accessibilityIdentifier("profile-language")
                    NavigationLink { HelpScreen() } label: {
                        Label("Help", systemImage: "questionmark.circle")
                    }
                    .accessibilityIdentifier("profile-help")
                    NavigationLink { AboutScreen() } label: {
                        Label("About", systemImage: "info.circle")
                    }
                    .accessibilityIdentifier("profile-about")
                }
                if container.auth.isSignedIn {
                    dangerSection
                }
            }
            .accessibilityIdentifier("profile-menu")
            .navigationTitle(Text("Profile"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                        .accessibilityIdentifier("profile-done")
                }
            }
        }
        .task { await model.load() }
        .task { await bonuses.load() }
        .confirmationDialog("Delete account?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete account", role: .destructive) {
                Task { if await model.deleteAccount() { dismiss() } }
            }
            .accessibilityIdentifier("delete-confirm")
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Your account and its data will be permanently deleted. This cannot be undone.")
        }
        .alert("Couldn’t delete the account", isPresented: deleteFailed) {
            Button("OK", role: .cancel) { model.dismissDeleteError() }
        } message: {
            if case .failed(let message) = model.deleteState, !message.isEmpty {
                Text(verbatim: message)
            } else {
                Text("Check your connection and try again. Your account was not deleted.")
            }
        }
    }

    private var deleteFailed: Binding<Bool> {
        Binding(
            get: { if case .failed = model.deleteState { true } else { false } },
            set: { if !$0 { model.dismissDeleteError() } }
        )
    }

    @ViewBuilder
    private var accountSection: some View {
        Section {
            if container.auth.isSignedIn {
                HStack(spacing: JolSpacing.md) {
                    Image(systemName: "person.crop.circle.fill")
                        .font(.largeTitle)
                        .foregroundStyle(JolColor.brandText)
                        .accessibilityHidden(true)
                    if let identity = model.me?.identity {
                        Text(verbatim: identity)
                            .accessibilityIdentifier("profile-identity")
                    } else {
                        Text("Signed in")
                            .accessibilityIdentifier("profile-identity")
                    }
                }
                .frame(minHeight: JolTarget.minimum)
                .accessibilityElement(children: .combine)
            } else {
                NavigationLink {
                    SignInEntryView(onSignedIn: { dismiss() })
                } label: {
                    Label("Sign in", systemImage: "person.crop.circle.badge.plus")
                        .foregroundStyle(JolColor.brandText)
                }
                .accessibilityIdentifier("profile-sign-in")
            }
        }
    }

    /// Bonus balance (SSOT §10.3); guests have no bonus account, so no row.
    private var bonusSection: some View {
        Section {
            NavigationLink { BonusScreen(model: bonuses) } label: {
                LabeledContent {
                    if let balance = bonuses.balance {
                        Text(verbatim: balance.formatted(.number.locale(container.language.locale)))
                            .accessibilityIdentifier("profile-bonus-balance")
                    }
                } label: {
                    Label("Bonuses", systemImage: "gift")
                }
            }
            .accessibilityIdentifier("profile-bonuses")
        }
    }

    /// «My bookings» (Ш-55): requests to venues and their status; signed-in only.
    private var bookingsSection: some View {
        Section {
            NavigationLink { MyBookingsScreen(model: bookings) } label: {
                Label("My bookings", systemImage: "calendar.badge.clock")
            }
            .accessibilityIdentifier("profile-bookings")
        }
    }

    private var dangerSection: some View {
        Section {
            Button {
                Task {
                    await model.signOut()
                    dismiss()
                }
            } label: {
                Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
            }
            .disabled(model.isSigningOut || model.deleteState == .deleting)
            .accessibilityIdentifier("profile-sign-out")
            Button(role: .destructive) {
                confirmDelete = true
            } label: {
                Label("Delete account", systemImage: "trash")
            }
            .disabled(model.isSigningOut || model.deleteState == .deleting)
            .accessibilityIdentifier("profile-delete-account")
            if model.deleteState == .deleting {
                HStack(spacing: JolSpacing.sm) {
                    ProgressView()
                    Text("Deleting the account…").foregroundStyle(JolColor.textSecondary)
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("profile-deleting")
            }
        }
    }
}
