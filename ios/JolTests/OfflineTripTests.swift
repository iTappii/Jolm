@testable import Jol
import XCTest

/// Ш-42: the saved copy of a trip: storage, `ETag` / `If-None-Match`, the fallback of the full map without a network.
@MainActor
final class OfflineTripTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!
    private let tripID = UUID(uuidString: ChatStub.tripID)!
    private var directory: URL!

    override func setUp() async throws {
        try await super.setUp()
        directory = FileManager.default.temporaryDirectory.appending(path: "jol-offline-\(UUID().uuidString)")
    }

    override func tearDown() async throws {
        try? FileManager.default.removeItem(at: directory)
        try await super.tearDown()
    }

    private func client() -> APIClient {
        APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(SessionTokens(accessToken: "a", refreshToken: "r")),
            installID: "install-1", session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
    }

    private func decodeCopy(version: Int = 1) throws -> OfflineTrip {
        let json = UITestExtraStub.offlineJSON(tripID: ChatStub.tripID)
            .replacingOccurrences(of: "\"version\":1,", with: "\"version\":\(version),")
        return try JSONDecoder().decode(OfflineTrip.self, from: Data(json.utf8))
    }

    private func wait(_ timeout: TimeInterval = 3, until condition: () -> Bool) async {
        let deadline = Date().addingTimeInterval(timeout)
        while !condition(), Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    // MARK: - Storage

    func testStoreKeepsTheCopyItsVersionAndETagAcrossInstances() throws {
        let store = OfflineTripStore(directory: directory)
        XCTAssertNil(store.load(tripID))
        let copy = try decodeCopy(version: 7)
        try store.save(copy, etag: "\"v7-en\"")

        let reopened = OfflineTripStore(directory: directory)
        let saved = try XCTUnwrap(reopened.load(tripID))
        XCTAssertEqual(saved.trip, copy)
        XCTAssertEqual(saved.trip.version, 7)
        XCTAssertEqual(saved.meta.etag, "\"v7-en\"")
        XCTAssertEqual(reopened.all().map(\.trip.tripID), [tripID])
        let files = try FileManager.default.contentsOfDirectory(atPath: directory.path)
        XCTAssertEqual(files, ["\(tripID.uuidString.lowercased()).json"], "one file per trip, no temp leftovers")
    }

    func testRemoveAndDamagedFile() throws {
        let store = OfflineTripStore(directory: directory)
        try store.save(try decodeCopy(), etag: nil)
        store.remove(tripID)
        XCTAssertNil(store.load(tripID))

        try store.save(try decodeCopy(), etag: nil)
        try Data("not json".utf8).write(to: directory.appending(path: "\(tripID.uuidString.lowercased()).json"))
        XCTAssertNil(store.load(tripID), "a damaged file counts as not saved")
        XCTAssertTrue(store.all().isEmpty)

        try store.save(try decodeCopy(), etag: nil)
        store.removeAll()
        XCTAssertTrue(store.all().isEmpty)
    }

    // MARK: - ETag

    func testDownloadSavesThenAsksWithIfNoneMatchAndKeepsTheCopyOn304() async throws {
        StubURLProtocol.install { request in
            let url = try XCTUnwrap(request.url)
            if request.value(forHTTPHeaderField: "If-None-Match") == "\"v1-en\"" {
                return (StubURLProtocol.response(url, status: 304, headers: ["ETag": "\"v1-en\""]), Data())
            }
            return (StubURLProtocol.response(url, headers: ["ETag": "\"v1-en\""]),
                    Data(UITestExtraStub.offlineJSON(tripID: ChatStub.tripID).utf8))
        }
        let model = OfflineTripsModel(api: client(), store: OfflineTripStore(directory: directory))
        XCTAssertEqual(model.state(for: tripID), .none)

        let first = await model.download(tripID: tripID)
        XCTAssertTrue(first)
        XCTAssertEqual(model.state(for: tripID), .saved)
        XCTAssertNil(StubURLProtocol.requests[0].value(forHTTPHeaderField: "If-None-Match"), "nothing saved yet")
        XCTAssertEqual(StubURLProtocol.requests[0].url?.path, "/v1/trips/\(ChatStub.tripID)/offline")
        XCTAssertEqual(StubURLProtocol.requests[0].value(forHTTPHeaderField: "Authorization"), "Bearer a")

        let again = await model.download(tripID: tripID)
        XCTAssertTrue(again, "304: the copy on the device is current")
        XCTAssertEqual(StubURLProtocol.requests.count, 2)
        XCTAssertEqual(StubURLProtocol.requests[1].value(forHTTPHeaderField: "If-None-Match"), "\"v1-en\"")
        XCTAssertEqual(model.saved(tripID)?.trip.version, 1)
    }

    func testANewVersionReplacesTheSavedCopy() async throws {
        let store = OfflineTripStore(directory: directory)
        try store.save(try decodeCopy(version: 1), etag: "\"v1-en\"")
        let updated = UITestExtraStub.offlineJSON(tripID: ChatStub.tripID)
            .replacingOccurrences(of: "\"version\":1,", with: "\"version\":2,")
        StubURLProtocol.install { request in
            (StubURLProtocol.response(try XCTUnwrap(request.url), headers: ["ETag": "\"v2-en\""]), Data(updated.utf8))
        }
        let model = OfflineTripsModel(api: client(), store: store)
        XCTAssertEqual(model.state(for: tripID), .saved, "saved trips are known at launch")
        await model.syncIfSaved(tripID: tripID)
        XCTAssertEqual(StubURLProtocol.requests[0].value(forHTTPHeaderField: "If-None-Match"), "\"v1-en\"")
        let saved = try XCTUnwrap(store.load(tripID))
        XCTAssertEqual(saved.trip.version, 2)
        XCTAssertEqual(saved.meta.etag, "\"v2-en\"")
    }

    func testFailedDownloadSavesNothingAndKeepsAnOldCopy() async throws {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let store = OfflineTripStore(directory: directory)
        let model = OfflineTripsModel(api: client(), store: store)
        let ok = await model.download(tripID: tripID)
        XCTAssertFalse(ok)
        XCTAssertEqual(model.problem, .network)
        XCTAssertEqual(model.state(for: tripID), .none)
        XCTAssertNil(store.load(tripID))

        try store.save(try decodeCopy(), etag: "\"v1-en\"")
        model.reload()
        await model.syncIfSaved(tripID: tripID)
        XCTAssertNotNil(store.load(tripID), "a failed refresh leaves the saved copy alone")
    }

    func testServerErrorIsReportedAndSignOutRemovesTheCopies() async throws {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(try XCTUnwrap(request.url), status: 404),
             Data("{\"error\":{\"code\":\"not_found\",\"message\":\"Trip not found\"}}".utf8))
        }
        let store = OfflineTripStore(directory: directory)
        let model = OfflineTripsModel(api: client(), store: store)
        _ = await model.download(tripID: tripID)
        XCTAssertEqual(model.problem, .server("Trip not found"))

        try store.save(try decodeCopy(), etag: nil)
        model.reload()
        model.removeAll()
        XCTAssertEqual(model.state(for: tripID), .none)
        XCTAssertTrue(store.all().isEmpty)
    }

    // MARK: - The copy as a plan

    func testTheCopyBecomesAPlanWithTimesAndLegs() throws {
        let overview = try XCTUnwrap(try decodeCopy().overview())
        XCTAssertEqual(overview.days.count, 2)
        let day = overview.days[0]
        XCTAssertEqual(day.items.map(\.place.name), ["Fixture Museum", "Fixture Cafe"])
        XCTAssertEqual(day.items.map(\.startTime), ["09:30", "12:00"])
        XCTAssertEqual(day.items.map(\.endTime), ["11:00", "13:30"])
        XCTAssertEqual(day.items[0].mustHave, true)
        let leg = try XCTUnwrap(day.legs.first)
        XCTAssertEqual(leg.chosenMode, .bus)
        XCTAssertEqual(leg.activeOption?.mode, .bus)
        XCTAssertGreaterThanOrEqual(leg.activeOption?.line.count ?? 0, 2, "the path is drawn from the saved geometry")
        XCTAssertEqual(leg.activeOption?.approximate, false)
        XCTAssertEqual(overview.totalCostKzt, 90_000)
    }

    func testAStopWithoutItsPlaceIsLeftOut() throws {
        let copy = try decodeCopy()
        let withoutCafe = OfflineTrip(
            tripID: copy.tripID, version: copy.version, locale: copy.locale, timezone: copy.timezone,
            startDate: copy.startDate, endDate: copy.endDate, budgetKzt: nil, totalCostKzt: nil, days: copy.days,
            places: copy.places.filter { $0.value.name != "Fixture Cafe" }
        )
        let overview = try XCTUnwrap(withoutCafe.overview())
        XCTAssertEqual(overview.days[0].items.map(\.place.name), ["Fixture Museum"])
    }

    func testOpeningHoursOfTheVisitDay() throws {
        let copy = try decodeCopy()
        let item = try XCTUnwrap(try XCTUnwrap(copy.overview()).days[0].items.first)
        let place = try XCTUnwrap(copy.places[UITestSupport.centerPlaceID])
        // 2026-12-05 is a Saturday = 5 (Monday is 0); the fixture has Saturday hours.
        XCTAssertEqual(OfflinePlaceCard.weekday(of: "2026-12-05"), 5)
        XCTAssertEqual(OfflinePlaceCard(item: item, place: place, dayDate: "2026-12-05").hoursText, "10:00–18:00")
        XCTAssertNil(OfflinePlaceCard(item: item, place: place, dayDate: "2026-12-06").hoursText)
    }

    // MARK: - The full map without a network

    func testTheMapOpensTheSavedCopyWhenThereIsNoNetwork() async throws {
        let store = OfflineTripStore(directory: directory)
        try store.save(try decodeCopy(), etag: "\"v1-en\"")
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let api = client()
        let map = TripMapModel(api: api, offline: OfflineTripsModel(api: api, store: store))

        map.open(tripID: tripID)
        await wait { map.phase == .loaded }
        XCTAssertEqual(map.phase, .loaded)
        XCTAssertTrue(map.isSavedCopy)
        XCTAssertEqual(map.days.count, 2)
        XCTAssertEqual(map.day?.items.map(\.startTime), ["09:30", "12:00"])
        XCTAssertEqual(map.stops.count, 2)
        XCTAssertEqual(map.lines.count, 1)
        XCTAssertFalse(map.lines[0].approximate)
        XCTAssertNotNil(map.savedPlaces[UUID(uuidString: UITestSupport.centerPlaceID)!])

        // Read-only: edits would need the server.
        let before = StubURLProtocol.requests.count
        map.remove(try XCTUnwrap(map.day?.items.first))
        map.selectLeg(try XCTUnwrap(map.day?.legs.first).id)
        XCTAssertNil(map.selectedLegID)
        XCTAssertEqual(StubURLProtocol.requests.count, before)
    }

    func testWithoutASavedCopyTheMapFailsAsBefore() async throws {
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let api = client()
        let saved = OfflineTripsModel(api: api, store: OfflineTripStore(directory: directory))
        let map = TripMapModel(api: api, offline: saved)
        map.open(tripID: tripID)
        await wait { map.phase == .failed }
        XCTAssertEqual(map.phase, .failed)
        XCTAssertFalse(map.isSavedCopy)
    }

    func testAnOnlineLoadWinsOverTheCopyAndRefreshesIt() async throws {
        let store = OfflineTripStore(directory: directory)
        try store.save(try decodeCopy(version: 1), etag: "\"v1-en\"")
        let updated = UITestExtraStub.offlineJSON(tripID: ChatStub.tripID)
            .replacingOccurrences(of: "\"version\":1,", with: "\"version\":3,")
        StubURLProtocol.install { request in
            let url = try XCTUnwrap(request.url)
            switch url.path {
            case "/v1/trips/\(ChatStub.tripID)":
                return (StubURLProtocol.response(url), Data(TripStub.json(id: ChatStub.tripID).utf8))
            case "/v1/trips/\(ChatStub.tripID)/offline":
                return (StubURLProtocol.response(url, headers: ["ETag": "\"v3-en\""]), Data(updated.utf8))
            default:
                return (StubURLProtocol.response(url), Data("{\"items\":[]}".utf8))
            }
        }
        let api = client()
        let map = TripMapModel(api: api, offline: OfflineTripsModel(api: api, store: store))
        map.open(tripID: tripID)
        await wait { store.load(self.tripID)?.trip.version == 3 }
        XCTAssertFalse(map.isSavedCopy)
        XCTAssertEqual(map.days.count, 3, "the live plan, not the copy (two days)")
        XCTAssertEqual(store.load(tripID)?.trip.version, 3, "an open trip keeps its saved copy current")
    }

    func testMyTripsFallBackToTheSavedOnesWithoutANetwork() async throws {
        let store = OfflineTripStore(directory: directory)
        try store.save(try decodeCopy(), etag: nil)
        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        let api = client()
        let map = TripMapModel(api: api, offline: OfflineTripsModel(api: api, store: store))
        map.loadSummaries()
        await wait { map.summaries != .loading }
        guard case .loaded(let rows) = map.summaries else { return XCTFail("\(map.summaries)") }
        XCTAssertEqual(rows.map(\.id), [tripID])
        XCTAssertEqual(rows.first?.days, 2)
        XCTAssertEqual(rows.first?.startDate, "2026-12-05")
    }
}
