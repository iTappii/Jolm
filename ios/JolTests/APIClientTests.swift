@testable import Jol
import XCTest

final class APIClientTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let stale = SessionTokens(accessToken: "old-access", refreshToken: "old-refresh")
    private let fresh = SessionTokens(accessToken: "new-access", refreshToken: "new-refresh")

    private func makeClient(
        store: MemoryTokenStore,
        cleared: (@Sendable () -> Void)? = nil
    ) -> APIClient {
        APIClient(
            baseURL: .success(base),
            tokens: store,
            installID: "install-1",
            session: StubURLProtocol.session(),
            language: { "ru" },
            onSessionCleared: cleared ?? {}
        )
    }

    private func json(_ object: Any) -> Data {
        // swiftlint:disable:next force_try
        try! JSONSerialization.data(withJSONObject: object)
    }

    private func refreshBody(_ request: URLRequest) -> String? {
        request.httpBody.flatMap { String(data: $0, encoding: .utf8) }
    }

    // MARK: - Decoding and headers

    func testMetaDecodesAndSendsHeadersWithoutAuth() async throws {
        let body = json(["version": "0.1.0", "min_ios_version": "17.0"])
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), body) }
        let client = makeClient(store: MemoryTokenStore(stale))

        let meta = try await client.meta()

        XCTAssertEqual(meta, ServerMeta(version: "0.1.0", minIOSVersion: "17.0"))
        let request = try XCTUnwrap(StubURLProtocol.requests.first)
        XCTAssertEqual(request.url?.absoluteString, "https://api.example.test/v1/meta")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Accept-Language"), "ru")
        XCTAssertEqual(request.value(forHTTPHeaderField: "X-Install-ID"), "install-1")
        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"), "meta is sent without a token")
    }

    func testBearerTokenIsAttached() async throws {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), Data("{}".utf8)) }
        let client = makeClient(store: MemoryTokenStore(stale))
        let _: [String: String] = try await client.send(.get("v1/me"))
        XCTAssertEqual(StubURLProtocol.requests.first?.value(forHTTPHeaderField: "Authorization"), "Bearer old-access")
    }

    func testNoContentEndpoint() async throws {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!, status: 204), Data()) }
        let client = makeClient(store: MemoryTokenStore())
        try await client.send(.post("v1/auth/logout", authorized: false))
    }

    func testUndecodableBodyIsInvalidResponse() async {
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!), Data("nope".utf8)) }
        let client = makeClient(store: MemoryTokenStore())
        do {
            _ = try await client.meta()
            XCTFail("expected error")
        } catch {
            XCTAssertEqual(error as? APIError, .invalidResponse)
        }
    }

    // MARK: - Errors

    func testServerErrorBodyIsDecoded() async {
        let body = json(["error": ["code": "invalid_code", "message": "Неверный код"]])
        StubURLProtocol.install { request in (StubURLProtocol.response(request.url!, status: 422), body) }
        let client = makeClient(store: MemoryTokenStore())
        do {
            _ = try await client.meta()
            XCTFail("expected error")
        } catch {
            XCTAssertEqual(error as? APIError, .server(status: 422, code: "invalid_code", message: "Неверный код"))
        }
    }

    func testNonJSONErrorBodyFallsBackToHTTPError() async {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!, status: 502), Data("<html>".utf8))
        }
        let client = makeClient(store: MemoryTokenStore())
        do {
            _ = try await client.meta()
            XCTFail("expected error")
        } catch {
            XCTAssertEqual(error as? APIError, .server(status: 502, code: "http_error", message: ""))
        }
    }

    func testTransportErrorIsWrapped() async {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let client = makeClient(store: MemoryTokenStore())
        do {
            _ = try await client.meta()
            XCTFail("expected error")
        } catch {
            guard case .network(let urlError)? = error as? APIError else { return XCTFail("expected network error") }
            XCTAssertEqual(urlError.code, .notConnectedToInternet)
        }
    }

    func testInvalidBaseURL() async {
        let client = APIClient(baseURL: .failure(.invalidBaseURL), tokens: MemoryTokenStore(), installID: "x")
        do {
            _ = try await client.meta()
            XCTFail("expected error")
        } catch {
            XCTAssertEqual(error as? APIError, .invalidBaseURL)
        }
    }

    // MARK: - Refresh

    private func meHandler(refreshStatus: Int = 200) -> StubURLProtocol.Handler {
        let tokenBody = json(["access_token": "new-access", "refresh_token": "new-refresh"])
        let unauthorized = json(["error": ["code": "unauthorized", "message": "no"]])
        return { request in
            let url = request.url!
            if url.path == "/v1/auth/refresh" {
                if refreshStatus == 200 { return (StubURLProtocol.response(url), tokenBody) }
                return (StubURLProtocol.response(url, status: refreshStatus), unauthorized)
            }
            if request.value(forHTTPHeaderField: "Authorization") == "Bearer new-access" {
                return (StubURLProtocol.response(url), Data("{\"id\":\"u1\"}".utf8))
            }
            return (StubURLProtocol.response(url, status: 401), unauthorized)
        }
    }

    func testRefreshOn401RetriesOnceAndStoresRotatedTokens() async throws {
        StubURLProtocol.install(meHandler())
        let store = MemoryTokenStore(stale)
        let client = makeClient(store: store)

        let me: [String: String] = try await client.send(.get("v1/me"))

        XCTAssertEqual(me["id"], "u1")
        XCTAssertEqual(try store.load(), fresh)
        let paths = StubURLProtocol.requests.map { $0.url!.path }
        XCTAssertEqual(paths, ["/v1/me", "/v1/auth/refresh", "/v1/me"])
        XCTAssertEqual(refreshBody(StubURLProtocol.requests[1]), "{\"refresh_token\":\"old-refresh\"}")
        XCTAssertNil(StubURLProtocol.requests[1].value(forHTTPHeaderField: "Authorization"))
    }

    func testConcurrentUnauthorizedRequestsShareOneRefresh() async throws {
        StubURLProtocol.install(meHandler())
        let store = MemoryTokenStore(stale)
        let client = makeClient(store: store)

        try await withThrowingTaskGroup(of: Void.self) { group in
            for _ in 0..<8 {
                group.addTask {
                    let _: [String: String] = try await client.send(.get("v1/me"))
                }
            }
            try await group.waitForAll()
        }

        let refreshes = StubURLProtocol.requests.filter { $0.url!.path == "/v1/auth/refresh" }
        XCTAssertEqual(refreshes.count, 1, "single-flight refresh")
        XCTAssertEqual(try store.load(), fresh)
    }

    func testRejectedRefreshClearsSession() async throws {
        StubURLProtocol.install(meHandler(refreshStatus: 401))
        let store = MemoryTokenStore(stale)
        let cleared = ClearedFlag()
        let client = makeClient(store: store) { cleared.set() }

        do {
            let _: [String: String] = try await client.send(.get("v1/me"))
            XCTFail("expected error")
        } catch {
            XCTAssertEqual((error as? APIError)?.isUnauthorized, true)
        }

        XCTAssertNil(try store.load())
        XCTAssertTrue(cleared.value)
    }

    func testTransientRefreshFailureKeepsSession() async throws {
        StubURLProtocol.install(meHandler(refreshStatus: 503))
        let store = MemoryTokenStore(stale)
        let cleared = ClearedFlag()
        let client = makeClient(store: store) { cleared.set() }

        do {
            let _: [String: String] = try await client.send(.get("v1/me"))
            XCTFail("expected error")
        } catch {
            guard case .server(let status, _, _)? = error as? APIError else { return XCTFail("expected server error") }
            XCTAssertEqual(status, 503)
        }

        XCTAssertEqual(try store.load(), stale)
        XCTAssertFalse(cleared.value)
    }

    func testUnauthorizedWithoutSessionDoesNotRefresh() async {
        StubURLProtocol.install(meHandler())
        let client = makeClient(store: MemoryTokenStore())
        do {
            let _: [String: String] = try await client.send(.get("v1/me"))
            XCTFail("expected error")
        } catch {
            XCTAssertEqual((error as? APIError)?.isUnauthorized, true)
        }
        XCTAssertEqual(StubURLProtocol.requests.count, 1)
    }

    // MARK: - Streaming

    func testStreamParsesEventsAndRefreshesOn401() async throws {
        let sse = "event: token\r\ndata: Hel\r\n\r\ndata: lo\n\n"
        let unauthorized = json(["error": ["code": "unauthorized", "message": "no"]])
        let tokenBody = json(["access_token": "new-access", "refresh_token": "new-refresh"])
        StubURLProtocol.install { request in
            let url = request.url!
            if url.path == "/v1/auth/refresh" { return (StubURLProtocol.response(url), tokenBody) }
            if request.value(forHTTPHeaderField: "Authorization") == "Bearer new-access" {
                return (StubURLProtocol.response(url, headers: ["Content-Type": "text/event-stream"]), Data(sse.utf8))
            }
            return (StubURLProtocol.response(url, status: 401), unauthorized)
        }
        let client = makeClient(store: MemoryTokenStore(stale))

        var events: [SSEEvent] = []
        for try await event in client.stream(.get("v1/chat/guest")) { events.append(event) }

        XCTAssertEqual(events, [SSEEvent(event: "token", data: "Hel"), SSEEvent(event: "message", data: "lo")])
        XCTAssertEqual(StubURLProtocol.requests.last?.value(forHTTPHeaderField: "Accept"), "text/event-stream")
    }
}

final class ClearedFlag: @unchecked Sendable {
    private let lock = NSLock()
    private var flag = false
    var value: Bool { lock.lock(); defer { lock.unlock() }; return flag }
    func set() { lock.lock(); flag = true; lock.unlock() }
}
