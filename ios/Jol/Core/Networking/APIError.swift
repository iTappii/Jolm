import Foundation

/// Typed error for every failure of `APIClient`.
enum APIError: Error, Equatable {
    /// Server answered with a non-2xx status. `code`/`message` come from `{"error":{"code","message"}}`;
    /// when the body does not have that shape, `code` is `"http_error"` and `message` is empty.
    case server(status: Int, code: String, message: String)
    /// HTTP 429. `retryAfter` is the `Retry-After` header in seconds (`nil` when the server did not send it).
    case rateLimited(retryAfter: TimeInterval?, message: String)
    /// Transport failure (no connection, timeout, TLS ...). Cancellation is NOT wrapped here.
    case network(URLError)
    /// Response is not HTTP or the body could not be decoded into the expected type.
    case invalidResponse
    /// `JOL_API_BASE_URL` is missing, malformed or not allowed (plain http outside the simulator).
    case invalidBaseURL

    var isUnauthorized: Bool {
        if case .server(let status, _, _) = self { return status == 401 }
        return false
    }

    /// Server-provided, already localized message (empty if there is none).
    var serverMessage: String {
        switch self {
        case .server(_, _, let message), .rateLimited(_, let message): message
        default: ""
        }
    }
}

/// Wire shape of the server error body.
struct APIErrorBody: Decodable {
    struct Payload: Decodable {
        let code: String
        let message: String
    }

    let error: Payload

    /// 429 code of the person's daily AI limit (Ш-66).
    static let budgetExceededCode = "llm_budget_exceeded"

    /// Maps a non-2xx response; 429 keeps its `Retry-After` (seconds form only; HTTP-date is ignored).
    static func decode(response: HTTPURLResponse, data: Data) -> APIError {
        let error = decode(status: response.statusCode, data: data)
        guard response.statusCode == 429 else { return error }
        // The daily AI limit is not a retry-in-a-moment case: keep its `code` (and no countdown).
        if case .server(_, let code, _) = error, code == budgetExceededCode { return error }
        let retry = response.value(forHTTPHeaderField: "Retry-After").flatMap { TimeInterval($0) }
        return .rateLimited(retryAfter: retry.map { max(0, $0) }, message: error.serverMessage)
    }

    static func decode(status: Int, data: Data) -> APIError {
        if let body = try? JSONDecoder().decode(APIErrorBody.self, from: data) {
            return .server(status: status, code: body.error.code, message: body.error.message)
        }
        return .server(status: status, code: "http_error", message: "")
    }
}
