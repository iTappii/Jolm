import Foundation

/// Trips saved on the device (SSOT §7.4): one JSON file per trip in `Application Support/Jol/OfflineTrips`, written
/// atomically, holding the server's offline copy, its version and the `ETag` for the next conditional request.
/// A file that cannot be read (damaged, written by an older shape) counts as "not saved".
struct OfflineTripStore: Sendable {
    let directory: URL

    init(directory: URL = OfflineTripStore.defaultDirectory) {
        self.directory = directory
    }

    static var defaultDirectory: URL {
        let base = (try? FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true
        )) ?? FileManager.default.temporaryDirectory
        return base.appending(path: "Jol", directoryHint: .isDirectory)
            .appending(path: "OfflineTrips", directoryHint: .isDirectory)
    }

    private func file(_ id: UUID) -> URL {
        directory.appending(path: "\(id.uuidString.lowercased()).json", directoryHint: .notDirectory)
    }

    private static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }

    private static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }

    func save(_ trip: OfflineTrip, etag: String?, at date: Date = Date()) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let saved = SavedTrip(meta: OfflineTripMeta(etag: etag, savedAt: date), trip: trip)
        let options: Data.WritingOptions = [.atomic, .completeFileProtectionUntilFirstUserAuthentication]
        try Self.encoder().encode(saved).write(to: file(trip.tripID), options: options)
    }

    func load(_ id: UUID) -> SavedTrip? {
        guard let data = try? Data(contentsOf: file(id)) else { return nil }
        return try? Self.decoder().decode(SavedTrip.self, from: data)
    }

    func remove(_ id: UUID) {
        try? FileManager.default.removeItem(at: file(id))
    }

    func removeAll() {
        try? FileManager.default.removeItem(at: directory)
    }

    /// Every readable saved trip, the earliest start date first.
    func all() -> [SavedTrip] {
        let files = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []
        return files.filter { $0.pathExtension == "json" }
            .compactMap { url in
                (try? Data(contentsOf: url)).flatMap { try? Self.decoder().decode(SavedTrip.self, from: $0) }
            }
            .sorted { ($0.trip.startDate, $0.trip.tripID.uuidString) < ($1.trip.startDate, $1.trip.tripID.uuidString) }
    }
}
