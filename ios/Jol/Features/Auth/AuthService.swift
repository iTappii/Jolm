import Foundation

private struct Challenge: Decodable {
    let nonce: String
}

private struct AppleCredential: Encodable {
    let identityToken: String
    /// Lets the server revoke the Apple token when the account is deleted.
    let authorizationCode: String?

    enum CodingKeys: String, CodingKey {
        case identityToken = "identity_token"
        case authorizationCode = "authorization_code"
    }
}

/// `GET /v1/me`. The server currently returns `id`, `locale`, `display_name`; `email`/`phone` are
/// decoded when present (the server will add them with the Ш-28 email/SMS sign-in).
struct MeInfo: Decodable, Equatable, Sendable {
    let id: String
    let displayName: String?
    let email: String?
    let phone: String?

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case email
        case phone
    }

    /// What the menu shows as the account identity: email, phone or name, whichever exists.
    var identity: String? {
        [email, phone, displayName].lazy.compactMap { $0 }.first { !$0.isEmpty }
    }
}

private struct RefreshToken: Encodable {
    let refreshToken: String

    enum CodingKeys: String, CodingKey {
        case refreshToken = "refresh_token"
    }
}

enum OTPChannel: String, Sendable {
    case email
    case phone
}

private struct OTPRequestBody: Encodable {
    let channel: String
    let destination: String
}

private struct OTPVerifyBody: Encodable {
    let channel: String
    let destination: String
    let code: String
}

/// Auth endpoints on top of `APIClient`.
struct AuthService: Sendable {
    let api: APIClient
    let tokens: any TokenStore

    func appleChallenge() async throws -> String {
        let result: Challenge = try await api.send(.post("v1/auth/apple/challenge", authorized: false))
        return result.nonce
    }

    /// Exchanges the Apple identity token for a session and stores it in the Keychain.
    func signInWithApple(identityToken: String, authorizationCode: String? = nil) async throws {
        let body = AppleCredential(identityToken: identityToken, authorizationCode: authorizationCode)
        let endpoint = try Endpoint.post("v1/auth/apple", json: body, authorized: false)
        let session: SessionTokens = try await api.send(endpoint)
        try tokens.save(session)
    }

    /// `POST /v1/auth/otp/request` (204): the server sends a 6-digit code to the e-mail / phone.
    /// `destination` is sent as typed (light client-side validation only): the server normalizes e-mail
    /// and phone numbers (E.164, KZ by default).
    func requestCode(channel: OTPChannel, destination: String) async throws {
        let body = OTPRequestBody(channel: channel.rawValue, destination: destination)
        try await api.send(Endpoint.post("v1/auth/otp/request", json: body, authorized: false))
    }

    /// `POST /v1/auth/otp/verify`: exchanges the code for a session and stores it in the Keychain.
    func verifyCode(channel: OTPChannel, destination: String, code: String) async throws {
        let body = OTPVerifyBody(channel: channel.rawValue, destination: destination, code: code)
        let session: SessionTokens = try await api.send(
            Endpoint.post("v1/auth/otp/verify", json: body, authorized: false)
        )
        try tokens.save(session)
    }

    /// Revokes the session on the server (best effort) and always clears the local one.
    func signOut() async {
        if let current = (try? tokens.load()) ?? nil,
           let endpoint = try? Endpoint.post("v1/auth/logout", json: RefreshToken(refreshToken: current.refreshToken),
                                             authorized: false) {
            try? await api.send(endpoint)
        }
        try? tokens.clear()
    }

    func me() async throws -> MeInfo {
        try await api.send(.get("v1/me"))
    }

    /// Deletes the account on the server (204) and then clears the local session.
    /// On failure the session is kept so the user can retry.
    func deleteAccount() async throws {
        try await api.send(.delete("v1/me"))
        try? tokens.clear()
    }
}
