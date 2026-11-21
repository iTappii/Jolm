@testable import Jol
import XCTest

@MainActor
final class SignInTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!

    private struct Fixture {
        let model: SignInModel
        let store: MemoryTokenStore
        let auth: AuthState
    }

    private func makeFixture(tick: Duration = .milliseconds(10)) -> Fixture {
        let store = MemoryTokenStore()
        let client = APIClient(
            baseURL: .success(base), tokens: store, installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        let auth = AuthState(tokens: store)
        let model = SignInModel(service: AuthService(api: client, tokens: store), auth: auth, tick: tick)
        return Fixture(model: model, store: store, auth: auth)
    }

    private func wait(_ timeout: TimeInterval = 3, until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(5)) }
    }

    private func otpRequests(_ path: String) -> [URLRequest] {
        StubURLProtocol.requests.filter { $0.url?.path == path }
    }

    private func body(_ request: URLRequest) throws -> [String: String] {
        try XCTUnwrap(JSONSerialization.jsonObject(with: XCTUnwrap(request.httpBody)) as? [String: String])
    }

    // MARK: - Validation

    func testEmailValidation() {
        XCTAssertTrue(ContactValidator.isPlausibleEmail("a@b.kz"))
        XCTAssertTrue(ContactValidator.isPlausibleEmail("  tourist+x@mail.example.com "))
        for bad in ["", "a", "a@", "@b.kz", "a@b", "a b@c.kz", "a@@b.kz", "a@b."] {
            XCTAssertFalse(ContactValidator.isPlausibleEmail(bad), bad)
        }
    }

    func testPhoneCleaning() {
        XCTAssertEqual(ContactValidator.cleanedPhone("+7 (701) 123-45-67"), "+77011234567")
        XCTAssertEqual(ContactValidator.cleanedPhone("8 701 123 45 67"), "87011234567")
        XCTAssertEqual(ContactValidator.cleanedPhone("7011234567"), "7011234567")
        XCTAssertNil(ContactValidator.cleanedPhone("12345"))
        XCTAssertNil(ContactValidator.cleanedPhone("+7 701 abc 45 67"))
        XCTAssertNil(ContactValidator.cleanedPhone("1234567890123456"))
    }

    func testAppleFlagParsing() {
        XCTAssertTrue(AppConfig.parseFlag("YES"))
        XCTAssertTrue(AppConfig.parseFlag(" true "))
        XCTAssertFalse(AppConfig.parseFlag("NO"))
        XCTAssertFalse(AppConfig.parseFlag(""))
        XCTAssertFalse(AppConfig.parseFlag(nil), "missing key → no Apple sign-in")
    }

    // MARK: - Request and verify

    func testEmailFlowRequestsCodeThenSignsIn() async throws {
        StubURLProtocol.install { request in
            if request.url?.path == "/v1/auth/otp/verify" {
                let tokens = Data("{\"access_token\":\"a1\",\"refresh_token\":\"r1\"}".utf8)
                return (StubURLProtocol.response(request.url!), tokens)
            }
            return (StubURLProtocol.response(request.url!, status: 204), Data())
        }
        let fixture = makeFixture()
        let model = fixture.model
        model.input = "  Tourist@Example.com "
        await model.sendCode()
        XCTAssertEqual(model.step, .code)
        XCTAssertNil(model.problem)
        XCTAssertEqual(model.destination, "Tourist@Example.com", "trimmed; the server normalizes the rest")
        XCTAssertEqual(model.secondsUntilResend, SignInModel.defaultCooldown)

        let request = try XCTUnwrap(otpRequests("/v1/auth/otp/request").first)
        XCTAssertEqual(try body(request), ["channel": "email", "destination": "Tourist@Example.com"])
        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))

        model.code = "123456"
        let signedIn = await model.verify()
        XCTAssertTrue(signedIn)
        let verify = try XCTUnwrap(otpRequests("/v1/auth/otp/verify").first)
        XCTAssertEqual(try body(verify), ["channel": "email", "destination": "Tourist@Example.com", "code": "123456"])
        XCTAssertEqual(try fixture.store.load(), SessionTokens(accessToken: "a1", refreshToken: "r1"))
        XCTAssertTrue(fixture.auth.isSignedIn)
    }

    func testPhoneIsSentCleaned() async throws {
        StubURLProtocol.install { ($0.url.map { StubURLProtocol.response($0, status: 204) }!, Data()) }
        let model = makeFixture().model
        model.channel = .phone
        model.input = "+7 (701) 123-45-67"
        await model.sendCode()
        XCTAssertEqual(model.step, .code)
        let request = try XCTUnwrap(otpRequests("/v1/auth/otp/request").first)
        XCTAssertEqual(try body(request), ["channel": "phone", "destination": "+77011234567"])
    }

    func testBadDestinationIsRejectedLocallyWithoutRequest() async {
        StubURLProtocol.install { ($0.url.map { StubURLProtocol.response($0, status: 204) }!, Data()) }
        let model = makeFixture().model
        model.input = "not-an-email"
        await model.sendCode()
        XCTAssertEqual(model.problem, .invalidDestination)
        XCTAssertEqual(model.step, .destination)
        XCTAssertTrue(otpRequests("/v1/auth/otp/request").isEmpty)
    }

    func testServerRejectsDestination() async {
        StubURLProtocol.install(apiError(422, code: "otp_invalid_destination"))
        let model = makeFixture().model
        model.input = "a@b.kz"
        await model.sendCode()
        XCTAssertEqual(model.problem, .invalidDestination)
        XCTAssertEqual(model.step, .destination)
    }

    func testExpiredCodeIsDistinctFromWrongCode() async {
        StubURLProtocol.install { request in
            if request.url?.path == "/v1/auth/otp/verify" { return apiError(401, code: "otp_expired")(request) }
            return (StubURLProtocol.response(request.url!, status: 204), Data())
        }
        let fixture = makeFixture()
        fixture.model.input = "a@b.kz"
        await fixture.model.sendCode()
        fixture.model.code = "123456"
        let signedIn = await fixture.model.verify()
        XCTAssertFalse(signedIn)
        XCTAssertEqual(fixture.model.problem, .codeExpired)
        XCTAssertEqual(fixture.model.code, "")
    }

    func testWrongCodeKeepsGuestAndClearsField() async throws {
        StubURLProtocol.install { request in
            if request.url?.path == "/v1/auth/otp/verify" { return apiError(401, code: "otp_invalid")(request) }
            return (StubURLProtocol.response(request.url!, status: 204), Data())
        }
        let fixture = makeFixture()
        fixture.model.input = "a@b.kz"
        await fixture.model.sendCode()
        fixture.model.code = "000000"
        let signedIn = await fixture.model.verify()
        XCTAssertFalse(signedIn)
        XCTAssertEqual(fixture.model.problem, .wrongCode)
        XCTAssertEqual(fixture.model.code, "")
        XCTAssertFalse(fixture.auth.isSignedIn)
        XCTAssertNil(try fixture.store.load())
        fixture.model.code = "1"
        XCTAssertNil(fixture.model.problem, "typing again clears the error")
    }

    func testShortCodeIsNotSubmitted() async {
        StubURLProtocol.install { ($0.url.map { StubURLProtocol.response($0, status: 204) }!, Data()) }
        let model = makeFixture().model
        model.code = "123"
        let signedIn = await model.verify()
        XCTAssertFalse(signedIn)
        XCTAssertTrue(otpRequests("/v1/auth/otp/verify").isEmpty)
    }

    // MARK: - Rate limit, resend

    func testRateLimitWithRetryAfterStartsThatCountdownThenAllowsRetry() async {
        StubURLProtocol.install(apiError(429, code: "otp_rate_limited", headers: ["Retry-After": "2"]))
        let model = makeFixture(tick: .milliseconds(15)).model
        model.input = "a@b.kz"
        await model.sendCode()
        XCTAssertEqual(model.problem, .rateLimited(retryAfter: 2))
        XCTAssertEqual(model.step, .destination)
        XCTAssertEqual(model.secondsUntilResend, 2)
        XCTAssertFalse(model.canSubmitDestination, "the button waits out the countdown")
        await wait { model.secondsUntilResend == 0 }
        XCTAssertEqual(model.secondsUntilResend, 0)
        XCTAssertTrue(model.canSubmitDestination)
    }

    func testRateLimitWithoutHeaderUsesDefaultCooldown() async {
        StubURLProtocol.install(apiError(429, code: "otp_rate_limited"))
        let model = makeFixture().model
        model.input = "a@b.kz"
        await model.sendCode()
        XCTAssertEqual(model.problem, .rateLimited(retryAfter: nil))
        XCTAssertEqual(model.secondsUntilResend, SignInModel.rateLimitedCooldown)
    }

    func testResendIsBlockedDuringCountdownAndWorksAfter() async {
        StubURLProtocol.install { ($0.url.map { StubURLProtocol.response($0, status: 204) }!, Data()) }
        let model = makeFixture(tick: .milliseconds(1)).model
        model.input = "a@b.kz"
        await model.sendCode()
        XCTAssertFalse(model.canResend)
        await model.resend()
        XCTAssertEqual(otpRequests("/v1/auth/otp/request").count, 1, "no second request during the countdown")
        await wait(5) { model.canResend }
        XCTAssertTrue(model.canResend)
        await model.resend()
        XCTAssertEqual(otpRequests("/v1/auth/otp/request").count, 2)
        XCTAssertEqual(model.step, .code)
    }

    func testDeliveryAndNetworkProblems() async {
        StubURLProtocol.install(apiError(503, code: "otp_delivery_unavailable"))
        let model = makeFixture().model
        model.input = "a@b.kz"
        await model.sendCode()
        XCTAssertEqual(model.problem, .deliveryUnavailable)
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        await model.sendCode()
        XCTAssertEqual(model.problem, .network)
    }

    func testChangeDestinationGoesBack() async {
        StubURLProtocol.install { ($0.url.map { StubURLProtocol.response($0, status: 204) }!, Data()) }
        let model = makeFixture().model
        model.input = "a@b.kz"
        await model.sendCode()
        model.code = "12"
        model.changeDestination()
        XCTAssertEqual(model.step, .destination)
        XCTAssertEqual(model.code, "")
        XCTAssertEqual(model.secondsUntilResend, 0)
    }

    // MARK: - 429 in APIClient

    func testAPIClientKeepsRetryAfterOnRateLimit() async {
        StubURLProtocol.install(apiError(429, code: "rate_limited", headers: ["Retry-After": "11"]))
        let client = APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(), installID: "i",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
        do {
            try await client.send(.post("v1/x"))
            XCTFail("expected error")
        } catch {
            XCTAssertEqual(error as? APIError, .rateLimited(retryAfter: 11, message: "m"))
        }
    }

    // MARK: - Gate

    func testGateRunsActionImmediatelyWhenSignedIn() {
        let store = MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r"))
        let gate = AccountGate(auth: AuthState(tokens: store))
        var ran = 0
        gate.requireAccount { ran += 1 }
        XCTAssertEqual(ran, 1)
        XCTAssertFalse(gate.isPresenting)
    }

    func testGateAsksGuestAndContinuesOnlyAfterSignIn() throws {
        let store = MemoryTokenStore()
        let auth = AuthState(tokens: store)
        let gate = AccountGate(auth: auth)
        var ran = 0
        gate.requireAccount { ran += 1 }
        XCTAssertTrue(gate.isPresenting)
        XCTAssertEqual(ran, 0, "nothing happens before the user signs in")

        try store.save(SessionTokens(accessToken: "a", refreshToken: "r"))
        auth.refresh()
        gate.isPresenting = false
        gate.sheetDismissed()
        XCTAssertEqual(ran, 1, "the flow continues after sign-in")
        gate.sheetDismissed()
        XCTAssertEqual(ran, 1, "and only once")
    }

    func testGateDropsActionWhenSheetIsCancelled() {
        let auth = AuthState(tokens: MemoryTokenStore())
        let gate = AccountGate(auth: auth)
        var ran = 0
        gate.requireAccount { ran += 1 }
        gate.isPresenting = false
        gate.sheetDismissed()
        XCTAssertEqual(ran, 0)
    }
}

private func apiError(_ status: Int, code: String, headers: [String: String] = [:]) -> @Sendable (URLRequest) -> (
    HTTPURLResponse, Data
) {
    { request in
        (StubURLProtocol.response(request.url!, status: status, headers: headers),
         Data("{\"error\":{\"code\":\"\(code)\",\"message\":\"m\"}}".utf8))
    }
}
