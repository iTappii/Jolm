import Foundation

/// `GET /v1/meta`.
struct ServerMeta: Decodable, Equatable, Sendable {
    let version: String
    let minIOSVersion: String

    enum CodingKeys: String, CodingKey {
        case version
        case minIOSVersion = "min_ios_version"
    }
}

extension APIClient {
    func meta() async throws -> ServerMeta {
        try await send(.get("v1/meta", authorized: false))
    }
}
