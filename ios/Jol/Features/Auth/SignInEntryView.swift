import SwiftUI

/// Sign-in entry (guest → account). Apple works now; email and SMS code screens arrive with Ш-28.
struct SignInEntryView: View {
    let onSignedIn: () -> Void

    var body: some View {
        VStack(spacing: JolSpacing.lg) {
            Text("Sign in to build a personal trip plan and keep your chats.")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            AppleSignInView(onSignedIn: onSignedIn)
            placeholderButton("Continue with email", systemImage: "envelope", identifier: "sign-in-email")
            placeholderButton("Continue with phone", systemImage: "phone", identifier: "sign-in-phone")
            Text("Coming soon")
                .font(JolFont.caption)
                .foregroundStyle(JolColor.textTertiary)
            Spacer()
        }
        .padding(JolSpacing.lg)
        .navigationTitle(Text("Sign in"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("sign-in-entry")
    }

    private func placeholderButton(_ title: LocalizedStringKey, systemImage: String, identifier: String) -> some View {
        Label(title, systemImage: systemImage)
            .font(JolFont.headline)
            .frame(maxWidth: .infinity)
            .frame(height: 48)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
            .foregroundStyle(JolColor.textTertiary)
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.isButton)
            .accessibilityIdentifier(identifier)
    }
}
