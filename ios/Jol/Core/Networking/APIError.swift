import Foundation

/// Typed error for every failure of `APIClient`.
enum APIError: Error, Equatable {
    /// Server answered with a non-2xx status. `code`/`message` come from `{"error":{"code","message"}}`;
    /// when the body does not have that shape, `code` is `"http_error"` and `message` is empty.
    case server(status: Int, code: String, message: String)
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
        if case .server(_, _, let message) = self { return message }
        return ""
    }
}

/// Wire shape of the server error body.
struct APIErrorBody: Decodable {
    struct Payload: Decodable {
        let code: String
        let message: String
    }

    let error: Payload

    static func decode(status: Int, data: Data) -> APIError {
        if let body = try? JSONDecoder().decode(APIErrorBody.self, from: data) {
            return .server(status: status, code: body.error.code, message: body.error.message)
        }
        return .server(status: status, code: "http_error", message: "")
    }
}
