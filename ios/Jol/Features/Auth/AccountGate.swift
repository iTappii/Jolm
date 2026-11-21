import Observation
import SwiftUI

/// Registration gate (SSOT §3.2): personal trips need an account. Any feature wraps its entry point in
/// `container.gate.requireAccount { … }`: a signed-in user runs the action at once; a guest gets the
/// sign-in sheet and the action runs after a successful sign-in (and only then). The caller keeps its own
/// state (e.g. the chat draft), so nothing is lost while the sheet is up.
@MainActor
@Observable
final class AccountGate {
    var isPresenting = false

    @ObservationIgnored private let auth: AuthState
    @ObservationIgnored private var pending: (@MainActor () -> Void)?

    init(auth: AuthState) {
        self.auth = auth
    }

    func requireAccount(_ action: @escaping @MainActor () -> Void) {
        if auth.isSignedIn {
            action()
        } else {
            pending = action
            isPresenting = true
        }
    }

    /// Called when the sheet has gone: continue the flow if the user signed in, otherwise drop it.
    func sheetDismissed() {
        let action = pending
        pending = nil
        if auth.isSignedIn { action?() }
    }
}

/// The sign-in sheet shown by the gate.
struct AccountGateSheet: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            SignInEntryView(onSignedIn: { dismiss() }, reason: "Sign in to build your route. Your message is saved.")
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }
                            .accessibilityIdentifier("gate-cancel")
                    }
                }
        }
        .accessibilityIdentifier("account-gate")
    }
}
