import AuthenticationServices
import SwiftUI

struct AppleSignInView: View {
    /// Called after the session is stored (the caller closes whatever flow it is in).
    var onSignedIn: () -> Void = {}
    @Environment(AppContainer.self) private var container
    @State private var nonce: String?
    @State private var failed = false
    @State private var attempt = 0
    @State private var exchanging = false

    var body: some View {
        VStack(spacing: 16) {
            if let nonce {
                SignInWithAppleButton(.signIn) { request in
                    request.nonce = nonce
                } onCompletion: { result in
                    finish(result)
                }
                .frame(height: 48)
            } else if failed {
                Text("Couldn’t sign in with Apple.", tableName: "AppleSignIn")
                Button {
                    failed = false
                    attempt += 1
                } label: {
                    Text("Try Again", tableName: "AppleSignIn")
                }
            } else {
                ProgressView()
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("apple-sign-in")
        .padding(.vertical, JolSpacing.sm)
        .interactiveDismissDisabled(exchanging)
        .task(id: attempt) {
            do {
                nonce = try await service.appleChallenge()
            } catch {
                failed = !Task.isCancelled
            }
        }
    }

    private var service: AuthService {
        AuthService(api: container.api, tokens: container.tokens)
    }

    private func finish(_ result: Result<ASAuthorization, Error>) {
        nonce = nil
        switch result {
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let data = credential.identityToken,
                  let token = String(data: data, encoding: .utf8) else {
                failed = true
                return
            }
            let code = credential.authorizationCode.flatMap { String(data: $0, encoding: .utf8) }
            exchanging = true
            Task {
                defer { exchanging = false }
                do {
                    try await service.signInWithApple(identityToken: token, authorizationCode: code)
                    container.auth.refresh()
                    onSignedIn()
                } catch {
                    failed = true
                }
            }
        case .failure(let error):
            // A cancelled Apple sheet just returns here: show the button again.
            if (error as? ASAuthorizationError)?.code == .canceled {
                attempt += 1
            } else {
                failed = true
            }
        }
    }
}
