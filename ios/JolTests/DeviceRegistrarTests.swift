@testable import Jol
import XCTest

/// Ш-40: registering the device for pushes (`POST /v1/devices`).
@MainActor
final class DeviceRegistrarTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let installID = "6F9619FF-8B86-4011-B42D-00C04FC964FF"
    private var defaults: UserDefaults!
    private var suite: String!

    @MainActor
    private final class FakePush: PushAuthorizing {
        var authorized: Bool?
        var grants = true
        private(set) var questions = 0
        private(set) var registrations = 0

        init(authorized: Bool? = nil) { self.authorized = authorized }

        func isAuthorized() async -> Bool? { authorized }

        func requestAuthorization() async -> Bool {
            questions += 1
            authorized = grants
            return grants
        }

        func registerForRemoteNotifications() { registrations += 1 }
    }

    override func setUp() async throws {
        try await super.setUp()
        suite = "jol-devices-\(UUID().uuidString)"
        defaults = UserDefaults(suiteName: suite)
    }

    override func tearDown() async throws {
        defaults.removePersistentDomain(forName: suite)
        try await super.tearDown()
    }

    private func make(
        signedIn: Bool = false, language: String = "en", push: FakePush = FakePush()
    ) -> (DeviceRegistrar, MemoryTokenStore) {
        let store = MemoryTokenStore(signedIn ? SessionTokens(accessToken: "access-1", refreshToken: "refresh-1") : nil)
        let client = APIClient(
            baseURL: .success(base), tokens: store, installID: installID,
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        let registrar = DeviceRegistrar(
            api: client, installID: installID, language: { language }, defaults: defaults, push: push
        )
        return (registrar, store)
    }

    private func answerOK() {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!),
             Data("{\"install_id\":\"x\",\"user_linked\":false,\"push_enabled\":false}".utf8))
        }
    }

    private func json(_ request: URLRequest) throws -> [String: Any?] {
        let data = try XCTUnwrap(request.httpBody)
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        return object.mapValues { $0 is NSNull ? nil : $0 }
    }

    private func wait(until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(3)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    func testAGuestLaunchSendsNullTokenAndNoBearer() async throws {
        answerOK()
        let (registrar, _) = make(language: "ru")
        await registrar.register()

        let request = try XCTUnwrap(StubURLProtocol.requests.first)
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual(request.url?.path, "/v1/devices")
        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
        let body = try json(request)
        XCTAssertEqual(body["install_id"] as? String, installID)
        XCTAssertTrue(body.keys.contains("apns_token"), "the key is there, with null")
        XCTAssertNil(body["apns_token"] ?? nil)
        XCTAssertEqual(body["language"] as? String, "ru")
        XCTAssertFalse(registrar.needsRetry)
    }

    func testSignedInSendsTheBearerAndSignOutSendsNone() async throws {
        answerOK()
        let (registrar, store) = make(signedIn: true)
        await registrar.register()
        XCTAssertEqual(StubURLProtocol.requests[0].value(forHTTPHeaderField: "Authorization"), "Bearer access-1")

        try store.clear() // sign-out
        await registrar.register()
        XCTAssertEqual(StubURLProtocol.requests.count, 2)
        XCTAssertNil(StubURLProtocol.requests[1].value(forHTTPHeaderField: "Authorization"),
                     "a signed-out device must not stay linked to the previous user")
    }

    func testANewTokenIsStoredAsHexAndSentAtOnce() async throws {
        answerOK()
        let (registrar, _) = make()
        registrar.tokenReceived(Data([0xAB, 0x01, 0xFF, 0x10] + Array(repeating: UInt8(0x0F), count: 28)))
        await wait { !StubURLProtocol.requests.isEmpty }
        let sent = try json(try XCTUnwrap(StubURLProtocol.requests.first))["apns_token"] as? String
        XCTAssertEqual(sent, "ab01ff10" + String(repeating: "0f", count: 28))
        XCTAssertEqual(registrar.apnsToken, sent)
        XCTAssertEqual(sent?.count, 64)

        // The same token again is not news.
        registrar.tokenReceived(Data([0xAB, 0x01, 0xFF, 0x10] + Array(repeating: UInt8(0x0F), count: 28)))
        try await Task.sleep(for: .milliseconds(100))
        XCTAssertEqual(StubURLProtocol.requests.count, 1)

        // A later launch keeps sending the token it has.
        await registrar.register()
        XCTAssertEqual(try json(StubURLProtocol.requests[1])["apns_token"] as? String, sent)
    }

    func testFailureIsRememberedAndRepeatedWhenTheAppIsActiveAgain() async throws {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let (registrar, _) = make()
        await registrar.register()
        XCTAssertTrue(registrar.needsRetry)

        answerOK()
        await registrar.retryIfNeeded()
        XCTAssertFalse(registrar.needsRetry)
        await registrar.retryIfNeeded()
        XCTAssertEqual(StubURLProtocol.requests.count, 1, "nothing to repeat once it went through")
    }

    func testQuickChangesReachTheServerInOrder() async throws {
        StubURLProtocol.install { request in
            Thread.sleep(forTimeInterval: request.value(forHTTPHeaderField: "Authorization") == nil ? 0 : 0.15)
            return (StubURLProtocol.response(request.url!), Data("{}".utf8))
        }
        let (registrar, store) = make(signedIn: true)
        async let first: Void = registrar.register()
        try await Task.sleep(for: .milliseconds(20))
        try store.clear()
        async let second: Void = registrar.register()
        _ = await (first, second)
        XCTAssertEqual(StubURLProtocol.requests.map { $0.value(forHTTPHeaderField: "Authorization") != nil },
                       [true, false], "the sign-out call is not overtaken by the slower sign-in call")
    }

    // MARK: - Permission

    func testTheQuestionIsAskedOnceAfterTheFirstTripAndNeverAtLaunch() async throws {
        answerOK()
        let push = FakePush()
        let (registrar, _) = make(push: push)
        await registrar.refreshTokenAtLaunch()
        XCTAssertEqual(push.questions, 0, "launch asks nothing")
        XCTAssertEqual(push.registrations, 0)

        await registrar.requestPermissionAfterFirstTrip()
        XCTAssertEqual(push.questions, 1)
        XCTAssertEqual(push.registrations, 1, "allowed: an APNs token is requested")

        await registrar.requestPermissionAfterFirstTrip()
        XCTAssertEqual(push.questions, 1, "once in the life of the install")
    }

    func testADeniedQuestionIsNotRepeatedAndNoTokenIsRequested() async throws {
        let push = FakePush()
        push.grants = false
        let (registrar, _) = make(push: push)
        await registrar.requestPermissionAfterFirstTrip()
        await registrar.requestPermissionAfterFirstTrip()
        XCTAssertEqual(push.questions, 1)
        XCTAssertEqual(push.registrations, 0)
    }

    func testLaunchRefreshesTheTokenWhenAllowedAndDropsItWhenWithdrawn() async throws {
        answerOK()
        let push = FakePush(authorized: true)
        let (registrar, _) = make(push: push)
        registrar.tokenReceived(Data(repeating: 0x0A, count: 32))
        await wait { !StubURLProtocol.requests.isEmpty }
        await registrar.refreshTokenAtLaunch()
        XCTAssertEqual(push.registrations, 1, "iOS is asked for the token again at launch")

        push.authorized = false // switched off in Settings
        await registrar.refreshTokenAtLaunch()
        XCTAssertNil(registrar.apnsToken)
        XCTAssertNil(try json(try XCTUnwrap(StubURLProtocol.requests.last))["apns_token"] ?? nil,
                     "the server is told there is no token any more")
    }
}
