import Foundation

struct Endpoint: Sendable {
    enum Method: String, Sendable {
        case get = "GET"
        case post = "POST"
        case put = "PUT"
        case patch = "PATCH"
        case delete = "DELETE"
    }

    var method: Method
    var path: String
    var query: [URLQueryItem] = []
    var body: Data?
    /// Attach the bearer token (when a session exists) and refresh it on 401.
    /// Guest-accessible endpoints are still fine with `true`: with no session no header is sent.
    var authorized = true
    var timeout: TimeInterval = 10

    init(_ method: Method, _ path: String, query: [URLQueryItem] = [], authorized: Bool = true) {
        self.method = method
        self.path = path
        self.query = query
        self.authorized = authorized
    }

    static func get(_ path: String, query: [URLQueryItem] = [], authorized: Bool = true) -> Endpoint {
        Endpoint(.get, path, query: query, authorized: authorized)
    }

    static func post<Body: Encodable>(
        _ path: String, json: Body, authorized: Bool = true
    ) throws -> Endpoint {
        var endpoint = Endpoint(.post, path, authorized: authorized)
        endpoint.body = try JSONEncoder().encode(json)
        return endpoint
    }

    static func post(_ path: String, authorized: Bool = true) -> Endpoint {
        Endpoint(.post, path, authorized: authorized)
    }

    static func delete(_ path: String, authorized: Bool = true) -> Endpoint {
        Endpoint(.delete, path, authorized: authorized)
    }
}
