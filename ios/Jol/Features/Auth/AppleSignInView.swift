import AuthenticationServices
import SwiftUI

struct AppleSignInView: View {
    @Environment(\.dismiss) private var dismiss
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
        .padding(24)
        .interactiveDismissDisabled(exchanging)
        .presentationDetents([.height(180)])
        .task(id: attempt) {
            do {
                nonce = try await AppleSignInAPI.challenge()
            } catch {
                failed = !Task.isCancelled
            }
        }
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
            exchanging = true
            Task {
                defer { exchanging = false }
                do {
                    let tokens = try await AppleSignInAPI.signIn(identityToken: token)
                    try SessionStore.shared.save(tokens)
                    dismiss()
                } catch {
                    failed = true
                }
            }
        case .failure(let error):
            if (error as? ASAuthorizationError)?.code == .canceled {
                dismiss()
            } else {
                failed = true
            }
        }
    }
}

private struct AppleIdentityToken: Encodable {
    let identityToken: String

    enum CodingKeys: String, CodingKey {
        case identityToken = "identity_token"
    }
}

private enum AppleSignInAPI {
    struct Challenge: Decodable {
        let nonce: String
    }

    static func challenge() async throws -> String {
        let result: Challenge = try await post("v1/auth/apple/challenge")
        return result.nonce
    }

    static func signIn(identityToken: String) async throws -> SessionTokens {
        let body = try JSONEncoder().encode(AppleIdentityToken(identityToken: identityToken))
        return try await post("v1/auth/apple", body: body)
    }

    private static func post<T: Decodable>(_ path: String, body: Data? = nil) async throws -> T {
        guard let configured = Bundle.main.object(forInfoDictionaryKey: "JOL_API_BASE_URL") as? String,
              let base = URL(string: configured),
              let host = base.host, !host.isEmpty else {
            throw URLError(.badURL)
        }
        #if targetEnvironment(simulator)
        let local = base.scheme == "http" && host == "localhost"
        #else
        let local = false
        #endif
        guard base.scheme == "https" || local else {
            throw URLError(.appTransportSecurityRequiresSecureConnection)
        }

        var request = URLRequest(url: base.appending(path: path), timeoutInterval: 10)
        request.httpMethod = "POST"
        request.setValue(Locale.preferredLanguages.first, forHTTPHeaderField: "Accept-Language")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(T.self, from: data)
    }
}
