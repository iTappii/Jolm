import Foundation

/// One analytics event waiting to be sent (Ш-50). The `id` is made when the event happens and never changes, so a
/// retry of the same batch is a duplicate for the server, not a second event. No coordinates and no free text:
/// only the name, the time, an optional place and short whitelisted properties.
struct AnalyticsEvent: Codable, Equatable, Sendable {
    let id: UUID
    let name: String
    let ts: Date
    let placeID: UUID?
    let props: [String: String]

    init(id: UUID = UUID(), name: String, ts: Date, placeID: UUID? = nil, props: [String: String] = [:]) {
        self.id = id
        self.name = name
        self.ts = ts
        self.placeID = placeID
        self.props = props
    }

    enum CodingKeys: String, CodingKey {
        case id, name, ts, props
        case placeID = "place_id"
    }
}

/// Names of the events the app sends (`server/app/analytics/events.py`: `CLIENT_EVENTS`).
enum AnalyticsName {
    static let install = "app_install"
    static let launch = "app_launch"
    static let directionsStart = "directions_start"
}

/// `POST /v1/analytics/events` body.
struct AnalyticsBatch: Encodable, Sendable {
    let sentAt: Date
    let events: [AnalyticsEvent]

    /// The server's limit of events per batch.
    static let maxEvents = 50

    enum CodingKeys: String, CodingKey {
        case events
        case sentAt = "sent_at"
    }

    private enum EventKeys: String, CodingKey {
        case id, name, ts, props
        case placeID = "place_id"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(Self.iso(sentAt), forKey: .sentAt)
        var list = container.nestedUnkeyedContainer(forKey: .events)
        for event in events {
            var item = list.nestedContainer(keyedBy: EventKeys.self)
            try item.encode(event.id.uuidString.lowercased(), forKey: .id)
            try item.encode(event.name, forKey: .name)
            try item.encode(Self.iso(event.ts), forKey: .ts)
            try item.encodeIfPresent(event.placeID?.uuidString.lowercased(), forKey: .placeID)
            if !event.props.isEmpty { try item.encode(event.props, forKey: .props) }
        }
    }

    /// ISO-8601 with a zone, as the server wants it.
    static func iso(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: date)
    }
}

/// The queue on disk: `Application Support/Jol/analytics-queue.json`. A damaged file is an empty queue.
struct AnalyticsQueueStore: Sendable {
    let url: URL

    init(url: URL = AnalyticsQueueStore.defaultURL) {
        self.url = url
    }

    static var defaultURL: URL {
        let base = (try? FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true
        )) ?? FileManager.default.temporaryDirectory
        return base.appending(path: "Jol", directoryHint: .isDirectory)
            .appending(path: "analytics-queue.json", directoryHint: .notDirectory)
    }

    private static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    func load() -> [AnalyticsEvent] {
        guard let data = try? Data(contentsOf: url) else { return [] }
        return (try? Self.decoder().decode([AnalyticsEvent].self, from: data)) ?? []
    }

    func save(_ events: [AnalyticsEvent]) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        guard let data = try? encoder.encode(events) else { return }
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url, options: .atomic)
    }
}
