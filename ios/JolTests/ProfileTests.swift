@testable import Jol
import XCTest

@MainActor
final class ProfileTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let session = SessionTokens(accessToken: "access-1", refreshToken: "refresh-1")

    private func makeModel(store: MemoryTokenStore) -> (ProfileModel, AuthState) {
        let client = APIClient(
            baseURL: .success(base), tokens: store, installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        let auth = AuthState(tokens: store)
        return (ProfileModel(service: AuthService(api: client, tokens: store), auth: auth), auth)
    }

    private func body(_ request: URLRequest) -> [String: String]? {
        request.httpBody.flatMap { try? JSONDecoder().decode([String: String].self, from: $0) }
    }

    func testSignOutRevokesRefreshTokenAndClearsSession() async {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!, status: 204), Data()) }
        let store = MemoryTokenStore(session)
        let (model, auth) = makeModel(store: store)
        XCTAssertTrue(auth.isSignedIn)

        await model.signOut()

        let request = StubURLProtocol.requests.first
        XCTAssertEqual(request?.httpMethod, "POST")
        XCTAssertEqual(request?.url?.path, "/v1/auth/logout")
        XCTAssertEqual(request.flatMap(body), ["refresh_token": "refresh-1"])
        XCTAssertNil(try store.load())
        XCTAssertFalse(auth.isSignedIn)
    }

    func testSignOutClearsSessionEvenWhenServerFails() async throws {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let store = MemoryTokenStore(session)
        let (model, auth) = makeModel(store: store)

        await model.signOut()

        XCTAssertNil(try store.load())
        XCTAssertFalse(auth.isSignedIn)
    }

    func testDeleteAccountSendsDeleteWithBearerAndClearsSession() async throws {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!, status: 204), Data()) }
        let store = MemoryTokenStore(session)
        let (model, auth) = makeModel(store: store)

        let deleted = await model.deleteAccount()

        XCTAssertTrue(deleted)
        let request = try XCTUnwrap(StubURLProtocol.requests.first)
        XCTAssertEqual(request.httpMethod, "DELETE")
        XCTAssertEqual(request.url?.path, "/v1/me")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer access-1")
        XCTAssertNil(try store.load())
        XCTAssertFalse(auth.isSignedIn)
        XCTAssertEqual(model.deleteState, .idle)
    }

    func testDeleteAccountServerErrorKeepsSessionAndReportsMessage() async throws {
        let errorBody = Data(#"{"error":{"code":"internal","message":"Try later"}}"#.utf8)
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!, status: 500), errorBody) }
        let store = MemoryTokenStore(session)
        let (model, auth) = makeModel(store: store)

        let deleted = await model.deleteAccount()

        XCTAssertFalse(deleted)
        XCTAssertEqual(model.deleteState, .failed(message: "Try later"))
        XCTAssertEqual(try store.load(), session, "session kept so the user can retry")
        XCTAssertTrue(auth.isSignedIn)

        model.dismissDeleteError()
        XCTAssertEqual(model.deleteState, .idle)
    }

    func testDeleteAccountNetworkErrorKeepsSession() async throws {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let store = MemoryTokenStore(session)
        let (model, auth) = makeModel(store: store)

        let deleted = await model.deleteAccount()

        XCTAssertFalse(deleted)
        XCTAssertEqual(model.deleteState, .failed(message: ""))
        XCTAssertTrue(auth.isSignedIn)
        XCTAssertEqual(try store.load(), session)
    }

    func testLoadDecodesIdentityPreferringEmail() async {
        let payload = Data(#"{"id":"u1","locale":"ru","display_name":"Aigerim","email":"a@example.com"}"#.utf8)
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), payload) }
        let (model, _) = makeModel(store: MemoryTokenStore(session))

        await model.load()

        XCTAssertEqual(model.me?.identity, "a@example.com")
    }

    func testLoadFallsBackToDisplayNameAndToleratesFailure() async {
        let payload = Data(#"{"id":"u1","locale":"ru","display_name":"Aigerim"}"#.utf8)
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), payload) }
        let (model, _) = makeModel(store: MemoryTokenStore(session))
        await model.load()
        XCTAssertEqual(model.me?.identity, "Aigerim")

        StubURLProtocol.install { _ in throw URLError(.timedOut) }
        let (failing, _) = makeModel(store: MemoryTokenStore(session))
        await failing.load()
        XCTAssertNil(failing.me)
    }

    func testAppleSignInSendsAuthorizationCode() async throws {
        let tokens = Data(#"{"access_token":"a","refresh_token":"r"}"#.utf8)
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), tokens) }
        let store = MemoryTokenStore()
        let (_, _) = makeModel(store: store)
        let client = APIClient(
            baseURL: .success(base), tokens: store, installID: "i", session: StubURLProtocol.session(),
            language: { "en" }, onSessionCleared: {}
        )
        let service = AuthService(api: client, tokens: store)

        try await service.signInWithApple(identityToken: "id-token", authorizationCode: "auth-code")

        let sent = try XCTUnwrap(StubURLProtocol.requests.first.flatMap(body))
        XCTAssertEqual(sent, ["identity_token": "id-token", "authorization_code": "auth-code"])
        XCTAssertEqual(try store.load(), SessionTokens(accessToken: "a", refreshToken: "r"))

        try await service.signInWithApple(identityToken: "id-token")
        let withoutCode = try XCTUnwrap(StubURLProtocol.requests.last.flatMap(body))
        XCTAssertEqual(withoutCode, ["identity_token": "id-token"], "code is omitted when Apple gave none")
    }
}
