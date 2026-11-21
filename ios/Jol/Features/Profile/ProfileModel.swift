import Observation

/// State behind the profile menu: who is signed in, sign-out, account deletion.
@MainActor
@Observable
final class ProfileModel {
    enum DeleteState: Equatable {
        case idle
        case deleting
        /// `message` is the server's localized text, empty when there is none (the view shows a generic one).
        case failed(message: String)
    }

    private(set) var me: MeInfo?
    private(set) var deleteState = DeleteState.idle
    private(set) var isSigningOut = false

    @ObservationIgnored private let service: AuthService
    @ObservationIgnored private let auth: AuthState

    init(service: AuthService, auth: AuthState) {
        self.service = service
        self.auth = auth
    }

    /// Loads the account identity for the header. Failure is not fatal: the menu shows a generic row.
    func load() async {
        guard auth.isSignedIn else { return }
        me = try? await service.me()
    }

    /// Server logout (best effort) + local session cleared.
    func signOut() async {
        isSigningOut = true
        await service.signOut()
        auth.refresh()
        me = nil
        isSigningOut = false
    }

    /// `DELETE /v1/me`. Returns `true` when the account is gone and the local session is cleared;
    /// on failure the session stays and `deleteState` carries the error.
    @discardableResult
    func deleteAccount() async -> Bool {
        deleteState = .deleting
        do {
            try await service.deleteAccount()
            auth.refresh()
            me = nil
            deleteState = .idle
            return true
        } catch let error as APIError {
            deleteState = .failed(message: error.serverMessage)
        } catch {
            deleteState = .failed(message: "")
        }
        return false
    }

    func dismissDeleteError() {
        if case .failed = deleteState { deleteState = .idle }
    }
}
