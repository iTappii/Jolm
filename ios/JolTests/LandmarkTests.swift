import CoreLocation
@testable import Jol
import UIKit
import XCTest

/// Ш-69: the main sights — decoding, the zoom and collision rules of the layer, and the once-per-session list.
@MainActor
final class LandmarkTests: XCTestCase {
    private func landmark(_ name: String, rank: Int, minZoom: Double = 12, lat: Double = 43.2, lon: Double = 76.9)
        -> Landmark {
        Landmark(id: UUID(), name: name, category: "landmark", icon: nil, lat: lat, lon: lon, minZoom: minZoom,
                 rank: rank, region: "almaty")
    }

    private let screen = CGRect(x: 0, y: 0, width: 393, height: 852)

    // MARK: - Decoding

    func testDecodesTheServerList() throws {
        let json = """
        {"landmarks":[{"id":"a0000000-0000-4000-8000-000000000001","name":"Медеу","category":"landmark",\
        "icon":"skating_rink","lat":43.157,"lon":77.059,"min_zoom":12.0,"rank":1,"region":"almaty"}]}
        """
        let list = try JSONDecoder().decode(LandmarksList.self, from: Data(json.utf8))
        let medeu = try XCTUnwrap(list.landmarks.first)
        XCTAssertEqual(medeu.name, "Медеу")
        XCTAssertEqual(medeu.minZoom, 12)
        XCTAssertEqual(medeu.rank, 1)
        XCTAssertEqual(medeu.icon, "skating_rink")
        XCTAssertEqual(medeu.region, "almaty")
        XCTAssertEqual(medeu.summary.id, medeu.id, "the card is opened by the place id")
    }

    func testDecodesTheStubFixture() throws {
        let list = try JSONDecoder().decode(LandmarksList.self, from: Data(UITestSupport.landmarksJSON.utf8))
        XCTAssertEqual(list.landmarks.count, 8)
        XCTAssertEqual(list.landmarks.filter { $0.region == "almaty" }.count, 6)
        XCTAssertTrue(list.landmarks.allSatisfy { LandmarkIcon.assetName(for: $0.icon) != nil }, "all have art")
        XCTAssertTrue(list.landmarks.allSatisfy { $0.minZoom > 11 }, "nothing at the city overview of the stub")
    }

    func testIconKeyMapsToArtOrFallsBack() {
        XCTAssertEqual(LandmarkIcon.assetName(for: "mosque"), "landmark-mosque")
        XCTAssertNil(LandmarkIcon.assetName(for: "spaceship"))
        XCTAssertNil(LandmarkIcon.assetName(for: nil))
        XCTAssertEqual(LandmarkIcon.keys.count, 16)
        for key in LandmarkIcon.keys {
            XCTAssertNotNil(UIImage(named: "landmark-\(key)"), "\(key) is missing from the asset catalog")
        }
    }

    // MARK: - Zoom and collisions

    func testVisibleOnlyFromItsMinZoom() {
        let medeu = landmark("Medeu", rank: 1, minZoom: 12)
        XCTAssertFalse(medeu.isVisible(atZoom: 11))
        XCTAssertFalse(medeu.isVisible(atZoom: 11.99))
        XCTAssertTrue(medeu.isVisible(atZoom: 12))
        XCTAssertTrue(medeu.isVisible(atZoom: 15))
    }

    func testOverviewShowsNothingAndZoomedInShowsTheSight() {
        let list = [landmark("Medeu", rank: 1, minZoom: 12), landmark("Kok-Tobe", rank: 2, minZoom: 13, lat: 43.3)]
        let center = { (_: CLLocationCoordinate2D) in CGPoint(x: 200, y: 400) }
        XCTAssertTrue(LandmarkLayout.visible(list, zoom: 11, viewport: screen, point: center).isEmpty)
        let zoomed = LandmarkLayout.visible(list, zoom: 12.5, viewport: screen) {
            CGPoint(x: 200, y: $0.latitude > 43.25 ? 700 : 400)
        }
        XCTAssertEqual(zoomed.map(\.landmark.name), ["Medeu"], "Kok-Tobe waits for zoom 13")
    }

    func testOffScreenIsNotPlacedButJustOutsideIs() {
        let list = [landmark("Near", rank: 1, lat: 1), landmark("Far", rank: 2, lat: 2)]
        let placed = LandmarkLayout.visible(list, zoom: 14, viewport: screen) {
            CGPoint(x: $0.latitude == 1 ? -20 : -500, y: 300)
        }
        XCTAssertEqual(placed.map(\.landmark.name), ["Near"])
    }

    func testCollidingMarkerLosesToTheMoreImportantOne() {
        let list = [landmark("Minor", rank: 5), landmark("Major", rank: 1)]
        let placed = LandmarkLayout.visible(list, zoom: 14, viewport: screen) { _ in CGPoint(x: 200, y: 400) }
        XCTAssertEqual(placed.map(\.landmark.name), ["Major"])
    }

    func testFarApartMarkersAllStay() {
        let list = [landmark("One", rank: 1, lat: 1), landmark("Two", rank: 2, lat: 2)]
        let placed = LandmarkLayout.visible(list, zoom: 14, viewport: screen) {
            CGPoint(x: 100, y: $0.latitude * 200)
        }
        XCTAssertEqual(placed.count, 2)
    }

    func testBlockersKeepMarkersAway() {
        let list = [landmark("Medeu", rank: 1)]
        let blocker = CGRect(x: 180, y: 380, width: 40, height: 40)
        let placed = LandmarkLayout.visible(list, zoom: 14, viewport: screen, blockers: [blocker]) { _ in
            CGPoint(x: 200, y: 400)
        }
        XCTAssertTrue(placed.isEmpty)
    }

    // MARK: - The list in memory

    func testLoadsOncePerLanguageAndKeepsTheListOnFailure() async {
        let counter = Counter()
        let model = LandmarksModel {
            await counter.bump()
            if await counter.fail { throw URLError(.notConnectedToInternet) }
            return [Landmark.fixture(name: "Medeu")]
        }
        await model.load(language: "en")
        await model.load(language: "en")
        let afterTwoLoads = await counter.calls
        XCTAssertEqual(afterTwoLoads, 1, "once per session")
        XCTAssertEqual(model.items.map(\.name), ["Medeu"])

        await counter.setFail(true)
        await model.load(language: "ru")
        XCTAssertEqual(model.items.map(\.name), ["Medeu"], "a failed refresh keeps what is on the map")
        XCTAssertEqual(model.loadedLanguage, "en")

        await counter.setFail(false)
        await model.load(language: "ru")
        XCTAssertEqual(model.loadedLanguage, "ru", "a language change loads the list again")
        let calls = await counter.calls
        XCTAssertEqual(calls, 3)
    }

    func testFailureAtFirstLeavesNoLayer() async {
        let model = LandmarksModel { throw URLError(.timedOut) }
        await model.load(language: "en")
        XCTAssertTrue(model.items.isEmpty)
        XCTAssertNil(model.loadedLanguage, "a later launch of the screen may try again")
    }

    func testRequestIsPublicAndLocalized() async throws {
        StubURLProtocol.install { request in
            (StubURLProtocol.response(request.url!), Data(UITestSupport.landmarksJSON.utf8))
        }
        let client = APIClient(
            baseURL: .success(URL(string: "https://api.example.test")!), tokens: MemoryTokenStore(),
            installID: "install-1", session: StubURLProtocol.session(), language: { "ru" }, onSessionCleared: {}
        )
        let model = LandmarksModel(api: client)
        await model.load(language: "ru")
        XCTAssertEqual(model.items.count, 8)
        let request = try XCTUnwrap(StubURLProtocol.requests.first)
        XCTAssertEqual(request.url?.path, "/v1/landmarks")
        XCTAssertEqual(request.value(forHTTPHeaderField: "Accept-Language"), "ru")
        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
    }
}

private actor Counter {
    private(set) var calls = 0
    private(set) var fail = false
    func bump() { calls += 1 }
    func setFail(_ value: Bool) { fail = value }
}

private extension Landmark {
    static func fixture(name: String) -> Landmark {
        Landmark(id: UUID(), name: name, category: "landmark", icon: nil, lat: 43.1, lon: 77.0, minZoom: 12, rank: 1,
                 region: "almaty")
    }
}
