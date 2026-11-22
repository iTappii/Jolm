import Foundation

/// `booking` of a place card (Ш-49): which requests the place's partner takes; `nil` for a place without a partner.
struct BookingInfo: Decodable, Equatable, Sendable {
    let available: Bool?
    let kinds: [String]

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        available = try values.decodeIfPresent(Bool.self, forKey: .available)
        kinds = try values.decodeIfPresent([String].self, forKey: .kinds) ?? []
    }

    enum CodingKeys: String, CodingKey { case available, kinds }

    /// The booking button works only when the server says so and names at least one kind the app knows.
    var isAvailable: Bool { available == true && !supportedKinds.isEmpty }

    var supportedKinds: [BookingKind] { kinds.compactMap(BookingKind.init(rawValue:)) }
}

enum BookingKind: String, CaseIterable, Identifiable, Sendable {
    case table, room, ticket, food

    var id: String { rawValue }

    var needsStart: Bool { self != .food }
    var needsEnd: Bool { self == .room }
}

/// `POST /v1/bookings` body. `starts_at` / `ends_at` are ISO times with the Almaty offset.
struct BookingRequest: Encodable, Equatable, Sendable {
    let placeID: UUID
    let kind: BookingKind
    let partySize: Int
    let startsAt: String?
    let endsAt: String?
    let note: String?

    enum CodingKeys: String, CodingKey {
        case kind, note
        case placeID = "place_id"
        case partySize = "party_size"
        case startsAt = "starts_at"
        case endsAt = "ends_at"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(placeID.uuidString.lowercased(), forKey: .placeID)
        try container.encode(kind.rawValue, forKey: .kind)
        try container.encode(partySize, forKey: .partySize)
        try container.encodeIfPresent(startsAt, forKey: .startsAt)
        try container.encodeIfPresent(endsAt, forKey: .endsAt)
        try container.encodeIfPresent(note, forKey: .note)
    }
}

/// A booking request and where it stands: `pending`, `confirmed`, `declined`, `cancelled`, `failed`.
struct Booking: Decodable, Equatable, Identifiable, Sendable {
    struct Venue: Decodable, Equatable, Sendable {
        let id: UUID
        let name: String
    }

    let id: UUID
    let place: Venue?
    let kind: String
    let status: String
    let partySize: Int?
    let startsAt: String?
    let endsAt: String?
    let note: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, place, kind, status, note
        case partySize = "party_size"
        case startsAt = "starts_at"
        case endsAt = "ends_at"
        case createdAt = "created_at"
    }

    /// The person can still ask to cancel it (the server has the last word: 409 `not_cancellable`).
    var canCancel: Bool { status == "pending" || status == "confirmed" }
}

/// `GET /v1/bookings`: newest first, `next_cursor` for the next page.
struct BookingPage: Decodable, Equatable, Sendable {
    let items: [Booking]
    let nextCursor: String?

    enum CodingKeys: String, CodingKey {
        case items
        case nextCursor = "next_cursor"
    }
}
