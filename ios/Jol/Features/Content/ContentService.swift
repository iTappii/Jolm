import Foundation

private struct UploadBody: Encodable {
    let contentType: String
    let sizeBytes: Int

    enum CodingKeys: String, CodingKey {
        case contentType = "content_type"
        case sizeBytes = "size_bytes"
    }
}

/// The content API (Ш-44): upload slots, submissions, reviews of a place.
struct ContentService: Sendable {
    let api: APIClient

    /// `POST /v1/uploads`: the photo is always JPEG after `PhotoSanitizer`.
    func createUpload(sizeBytes: Int) async throws -> UploadSlot {
        try await api.send(Endpoint.post(
            "v1/uploads", json: UploadBody(contentType: "image/jpeg", sizeBytes: sizeBytes)
        ))
    }

    /// PUT of exactly the announced bytes with the headers the server returned.
    func put(_ data: Data, to slot: UploadSlot) async throws {
        guard slot.method.uppercased() == "PUT", let url = URL(string: slot.url) else { throw APIError.invalidResponse }
        try await api.upload(to: url, headers: slot.headers, body: data)
    }

    func submit(_ request: SubmissionRequest) async throws -> SubmissionResult {
        try await api.send(Endpoint.post("v1/submissions", json: request))
    }

    func reviews(placeID: UUID, cursor: String?) async throws -> ReviewsPage {
        var query = [URLQueryItem(name: "limit", value: "20")]
        if let cursor { query.append(URLQueryItem(name: "cursor", value: cursor)) }
        return try await api.send(.get("v1/places/\(placeID.uuidString.lowercased())/reviews", query: query))
    }
}
