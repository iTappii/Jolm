import Foundation

// Wire types and the forms of user submissions (Ш-44, SSOT §10; exact JSON: docs/reviews/Ш-44-server.md).

/// A JSON value for the free-form `payload` of a submission.
enum JSONValue: Encodable, Equatable, Sendable {
    case string(String)
    case int(Int)
    case object([String: JSONValue])
    case array([JSONValue])

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .int(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        }
    }
}

/// `POST /v1/submissions` body.
struct SubmissionRequest: Encodable, Equatable, Sendable {
    let type: SubmissionKind
    let placeID: UUID
    let payload: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case type, payload
        case placeID = "place_id"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(type.rawValue, forKey: .type)
        try container.encode(placeID.uuidString.lowercased(), forKey: .placeID)
        try container.encode(payload, forKey: .payload)
    }
}

/// `POST /v1/uploads` answer: where to PUT the file and with which headers.
struct UploadSlot: Decodable, Equatable, Sendable {
    let uploadID: UUID
    let url: String
    let method: String
    let headers: [String: String]
    let maxBytes: Int?

    enum CodingKeys: String, CodingKey {
        case url, method, headers
        case uploadID = "upload_id"
        case maxBytes = "max_bytes"
    }
}

/// `POST /v1/submissions` answer (the part the app uses).
struct SubmissionResult: Decodable, Equatable, Sendable {
    let id: String
    let type: String
    /// `published_pending_review`, `rejected_auto`, `approved`, `rejected`.
    let status: String
    let pendingReview: Bool
    let reasonCodes: [String]

    enum CodingKeys: String, CodingKey {
        case id, type, status
        case pendingReview = "pending_review"
        case reasonCodes = "reason_codes"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        id = try values.decode(String.self, forKey: .id)
        type = try values.decode(String.self, forKey: .type)
        status = try values.decode(String.self, forKey: .status)
        pendingReview = try values.decodeIfPresent(Bool.self, forKey: .pendingReview) ?? false
        reasonCodes = try values.decodeIfPresent([String].self, forKey: .reasonCodes) ?? []
    }

    /// The automatic filter refused it (HTTP 201 all the same): not a network error, nothing was published.
    var isRejected: Bool { status == "rejected_auto" || status == "rejected" }
}

// MARK: - Reviews of a place

struct PlaceReview: Decodable, Equatable, Identifiable, Sendable {
    let id: String
    let rating: Int
    let text: String?
    let authorName: String?
    let createdAt: String
    let pendingReview: Bool

    enum CodingKeys: String, CodingKey {
        case id, rating, text
        case authorName = "author_name"
        case createdAt = "created_at"
        case pendingReview = "pending_review"
    }

    var date: Date? { DirectionOption.parseDate(createdAt) }
}

struct ReviewsSummary: Decodable, Equatable, Sendable {
    let count: Int
    let average: Double?
}

/// `GET /v1/places/{id}/reviews`.
struct ReviewsPage: Decodable, Equatable, Sendable {
    let items: [PlaceReview]
    let nextCursor: String?
    let summary: ReviewsSummary?

    enum CodingKeys: String, CodingKey {
        case items, summary
        case nextCursor = "next_cursor"
    }
}

// MARK: - Forms

enum SubmissionKind: String, CaseIterable, Identifiable, Sendable {
    case review, menu, photo, transit, price

    var id: String { rawValue }
}

enum TicketAudience: String, CaseIterable, Identifiable, Sendable {
    case adult, child, student, senior, foreigner, resident

    var id: String { rawValue }
}

struct MenuItemDraft: Equatable, Identifiable {
    let id = UUID()
    var name = ""
    var price = ""
}

/// What the person typed, before it becomes a request. Mirrors the server's limits
/// (`server/app/submissions/schemas.py`) so a mistake is shown on the form, not as a 422.
struct SubmissionDraft: Equatable {
    enum Problem: Equatable {
        case rating
        case textTooLong
        case menuEmpty
        case menuName
        case menuPrice
        case photoMissing
        case captionTooLong
        case routeRef
        case fieldTooLong
        case interval
        case price
    }

    static let maxMoney = 1_000_000

    var kind = SubmissionKind.review
    var rating = 0
    var text = ""
    var menuItems = [MenuItemDraft()]
    var caption = ""
    var routeRef = ""
    var stop = ""
    var direction = ""
    var interval = ""
    var transitPrice = ""
    var transitNote = ""
    var price = ""
    var audience = TicketAudience.adult
    var priceNote = ""
    /// A photo was chosen and cleaned (the bytes live in `ContentModel`).
    var hasPhoto = false

    /// The photo is part of this kind of submission (optional for a menu, required for a photo).
    var usesPhoto: Bool { kind == .photo || kind == .menu }
}
