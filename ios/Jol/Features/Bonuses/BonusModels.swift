import Foundation

// Wire shape of `GET /v1/me/bonuses` (Ш-46, SSOT §10.3; exact JSON: docs/reviews/Ш-46.md).

/// One line of the bonus history. Today only accruals exist (spending is not available yet).
struct BonusEntry: Decodable, Equatable, Identifiable, Sendable {
    let id: String
    let amount: Int
    let kind: String
    let submissionType: String?
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, amount, kind
        case submissionType = "submission_type"
        case createdAt = "created_at"
    }

    var date: Date? { DirectionOption.parseDate(createdAt) }

    /// A String Catalog key for what the bonus was paid for.
    var reasonKey: String {
        switch submissionType {
        case "review": "Review"
        case "photo": "Photo"
        case "menu": "Menu"
        case "transit": "Transport data"
        case "price": "Entry price"
        default: "Bonus"
        }
    }
}

struct BonusPage: Decodable, Equatable, Sendable {
    let balance: Int
    /// SSOT §10.3: 1 bonus ≈ 1 tenge.
    let tengePerBonus: Int
    let items: [BonusEntry]
    let nextCursor: String?

    enum CodingKeys: String, CodingKey {
        case balance, items
        case tengePerBonus = "tenge_per_bonus"
        case nextCursor = "next_cursor"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        balance = try values.decode(Int.self, forKey: .balance)
        tengePerBonus = try values.decodeIfPresent(Int.self, forKey: .tengePerBonus) ?? 1
        items = try values.decodeIfPresent([BonusEntry].self, forKey: .items) ?? []
        nextCursor = try values.decodeIfPresent(String.self, forKey: .nextCursor)
    }
}

struct BonusService: Sendable {
    let api: APIClient

    func page(cursor: String?) async throws -> BonusPage {
        var query = [URLQueryItem(name: "limit", value: "20")]
        if let cursor { query.append(URLQueryItem(name: "cursor", value: cursor)) }
        return try await api.send(.get("v1/me/bonuses", query: query))
    }
}
