import Foundation

/// Network layer for the Jol server (`/v1/...`).
///
/// - decodes `{"error":{"code","message"}}` into `APIError.server`;
/// - sends `Accept-Language`, `X-Install-ID` and (when a session exists) `Authorization: Bearer`;
/// - on 401 refreshes the pair via `POST /v1/auth/refresh` (single-flight: concurrent requests
///   share one refresh) and retries the request once;
/// - when the server rejects the refresh token the session is cleared and `onSessionCleared` fires.
final class APIClient: Sendable {
    private let baseURL: Result<URL, APIError>
    private let session: URLSession
    private let tokens: any TokenStore
    private let installID: String
    private let languageProvider: @Sendable () -> String?
    private let refresher: Refresher

    init(
        baseURL: Result<URL, APIError>,
        tokens: any TokenStore,
        installID: String,
        session: URLSession = .shared,
        language: @escaping @Sendable () -> String? = { Locale.preferredLanguages.first },
        onSessionCleared: @escaping @Sendable () -> Void = {}
    ) {
        self.baseURL = baseURL
        self.session = session
        self.tokens = tokens
        self.installID = installID
        self.languageProvider = language
        self.refresher = Refresher(store: tokens, onSessionCleared: onSessionCleared)
    }

    // MARK: - Public API

    func send<T: Decodable>(_ endpoint: Endpoint, as type: T.Type = T.self) async throws -> T {
        let data = try await sendRaw(endpoint)
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            throw APIError.invalidResponse
        }
    }

    /// For endpoints without a response body (e.g. 204).
    func send(_ endpoint: Endpoint) async throws {
        _ = try await sendRaw(endpoint)
    }

    /// Opens a `text/event-stream` endpoint. The request (including the 401 → refresh → retry)
    /// is made when iteration starts; cancelling the iteration cancels the request.
    func stream(_ endpoint: Endpoint) -> AsyncThrowingStream<SSEEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    var endpoint = endpoint
                    endpoint.timeout = max(endpoint.timeout, 300)
                    let bytes = try await self.withAuth(endpoint, accept: "text/event-stream") { request in
                        let (bytes, response) = try await self.session.bytes(for: request)
                        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
                        guard (200..<300).contains(http.statusCode) else {
                            var body = Data()
                            for try await byte in bytes {
                                body.append(byte)
                                if body.count > 16_384 { break }
                            }
                            throw APIErrorBody.decode(response: http, data: body)
                        }
                        return bytes
                    }
                    for try await event in SSEParser.events(from: bytes) {
                        continuation.yield(event)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: Self.normalize(error))
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    // MARK: - Internals

    private func sendRaw(_ endpoint: Endpoint) async throws -> Data {
        do {
            return try await withAuth(endpoint, accept: "application/json") { request in
                let (data, response) = try await self.session.data(for: request)
                guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
                guard (200..<300).contains(http.statusCode) else {
                    throw APIErrorBody.decode(response: http, data: data)
                }
                return data
            }
        } catch {
            throw Self.normalize(error)
        }
    }

    private func withAuth<R>(
        _ endpoint: Endpoint,
        accept: String,
        _ call: (URLRequest) async throws -> R
    ) async throws -> R {
        let used = endpoint.authorized ? (try? tokens.load())?.accessToken : nil
        do {
            return try await call(try makeRequest(endpoint, accept: accept, bearer: used))
        } catch let error as APIError where error.isUnauthorized {
            guard let used else { throw error }
            let fresh = try await refresher.freshAccessToken(replacing: used) { [self] refreshToken in
                try await refreshCall(refreshToken)
            }
            return try await call(try makeRequest(endpoint, accept: accept, bearer: fresh))
        }
    }

    private func refreshCall(_ refreshToken: String) async throws -> SessionTokens {
        var endpoint = try Endpoint.post("v1/auth/refresh", json: RefreshBody(refreshToken: refreshToken),
                                         authorized: false)
        endpoint.timeout = 10
        do {
            let data = try await withAuth(endpoint, accept: "application/json") { request in
                let (data, response) = try await self.session.data(for: request)
                guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
                guard (200..<300).contains(http.statusCode) else {
                    throw APIErrorBody.decode(response: http, data: data)
                }
                return data
            }
            return try JSONDecoder().decode(SessionTokens.self, from: data)
        } catch {
            if error is DecodingError { throw APIError.invalidResponse }
            throw Self.normalize(error)
        }
    }

    private func makeRequest(_ endpoint: Endpoint, accept: String, bearer: String?) throws -> URLRequest {
        let base = try baseURL.get()
        var components = URLComponents(url: base.appending(path: endpoint.path), resolvingAgainstBaseURL: false)
        if !endpoint.query.isEmpty { components?.queryItems = endpoint.query }
        guard let url = components?.url else { throw APIError.invalidBaseURL }
        var request = URLRequest(url: url, timeoutInterval: endpoint.timeout)
        request.httpMethod = endpoint.method.rawValue
        request.setValue(accept, forHTTPHeaderField: "Accept")
        request.setValue(languageProvider(), forHTTPHeaderField: "Accept-Language")
        request.setValue(installID, forHTTPHeaderField: "X-Install-ID")
        if let bearer { request.setValue("Bearer \(bearer)", forHTTPHeaderField: "Authorization") }
        if let body = endpoint.body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }
        return request
    }

    /// URLError (except cancellation) → `APIError.network`; everything else is passed through.
    private static func normalize(_ error: Error) -> Error {
        if let urlError = error as? URLError, urlError.code != .cancelled { return APIError.network(urlError) }
        return error
    }
}

private struct RefreshBody: Encodable {
    let refreshToken: String

    enum CodingKeys: String, CodingKey { case refreshToken = "refresh_token" }
}

/// Serialises token refreshes so concurrent 401s trigger exactly one `POST /v1/auth/refresh`.
private actor Refresher {
    private let store: any TokenStore
    private let onSessionCleared: @Sendable () -> Void
    private var inFlight: Task<String, Error>?

    init(store: any TokenStore, onSessionCleared: @escaping @Sendable () -> Void) {
        self.store = store
        self.onSessionCleared = onSessionCleared
    }

    func freshAccessToken(
        replacing stale: String,
        refresh: @escaping @Sendable (String) async throws -> SessionTokens
    ) async throws -> String {
        if let inFlight { return try await inFlight.value }
        // Someone already refreshed while this request was failing.
        if let current = try? store.load(), current.accessToken != stale { return current.accessToken }
        let task = Task { try await self.performRefresh(refresh) }
        inFlight = task
        defer { inFlight = nil }
        return try await task.value
    }

    private func performRefresh(_ refresh: @Sendable (String) async throws -> SessionTokens) async throws -> String {
        guard let current = try store.load() else {
            throw APIError.server(status: 401, code: "unauthorized", message: "")
        }
        do {
            let fresh = try await refresh(current.refreshToken)
            try store.save(fresh)
            return fresh.accessToken
        } catch let error as APIError {
            // The server rejected the refresh token → the session is dead. Transient failures
            // (offline, 5xx, 429) keep the tokens so the next request can try again.
            if case .server(let status, _, _) = error, (400..<500).contains(status), status != 429, status != 408 {
                try? store.clear()
                onSessionCleared()
            }
            throw error
        }
    }
}
