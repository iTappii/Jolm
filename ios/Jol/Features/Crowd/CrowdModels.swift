import Foundation

/// Crowd statistics of a place card (`crowd`, Ш-47). `level` is 0 (empty) … 1 (packed); `label` is `empty`, `normal`
/// or `busy`. The block is absent (`nil`) while there is too little data — the app never fills the gap itself.
struct CrowdLevel: Decodable, Equatable, Sendable {
    let level: Double
    let label: String
    let samples: Int
}

struct CrowdHour: Decodable, Equatable, Sendable {
    let hour: Int
    let level: Double
    let label: String
    let samples: Int
}

struct CrowdBlock: Decodable, Equatable, Sendable {
    let now: CrowdLevel?
    let today: [CrowdHour]
    let samples: Int
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case now, today, samples
        case updatedAt = "updated_at"
    }

    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        now = try? values.decodeIfPresent(CrowdLevel.self, forKey: .now)
        today = try values.decodeIfPresent([CrowdHour].self, forKey: .today) ?? []
        samples = try values.decodeIfPresent(Int.self, forKey: .samples) ?? 0
        updatedAt = try values.decodeIfPresent(String.self, forKey: .updatedAt)
    }
}

/// What a person can tell about a place right now.
enum CrowdReportLevel: String, CaseIterable, Identifiable, Sendable {
    case busy, normal, empty

    var id: String { rawValue }
}

/// `POST /v1/places/{id}/checkin` and `/crowd`.
struct CrowdRecorded: Decodable, Equatable, Sendable {
    let recorded: Bool
    let distanceM: Int?

    enum CodingKeys: String, CodingKey {
        case recorded
        case distanceM = "distance_m"
    }
}
