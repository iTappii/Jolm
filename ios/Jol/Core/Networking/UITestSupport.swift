#if DEBUG
import CoreLocation
import Foundation
import SwiftUI

/// Debug-only support for UI tests (`-JolStubAPI`): a `URLProtocol` that answers the places and curated-route
/// endpoints from fixtures, so tests never depend on a running server, and an offline stub map style.
enum UITestSupport {
    /// `-JolForceTheme dark|light`: the screen is drawn in that theme whatever the simulator's appearance is (other
    /// sessions on the same Mac flip the shared appearance mid-test, which made themed screenshots unreliable).
    static var forcedColorScheme: ColorScheme? {
        let arguments = ProcessInfo.processInfo.arguments
        guard let index = arguments.firstIndex(of: "-JolForceTheme"), index + 1 < arguments.count else { return nil }
        switch arguments[index + 1] {
        case "dark": return .dark
        case "light": return .light
        default: return nil
        }
    }

    /// The stub map opens at this zoom (above `PlacePinVisibility.streetZoom`) unless `-JolStartCamera` says otherwise.
    static let stubStreetZoom = 15.5

    static var isStubbed: Bool { ProcessInfo.processInfo.arguments.contains("-JolStubAPI") }
    /// `-JolDemo` (with `-JolStubAPI`): a clean demo for a screen recording — plain phrases drive the live route,
    /// the built trip is made of the same stops, no fixture pins or ad events on the map.
    static var isDemo: Bool { ProcessInfo.processInfo.arguments.contains("-JolDemo") }

    /// Fixture place that sits exactly at `Region.current.center`, i.e. in the middle of the screen at launch.
    static let centerPlaceID = "11111111-1111-4111-8111-111111111111"
    static let secondPlaceID = "22222222-2222-4222-8222-222222222222"
    /// A third fixture place ~150 m from the museum, with a logo (`asset:` = an image bundled in the app).
    static let logoPlaceID = "44444444-4444-4444-8444-444444444444"
    static let routeID = "33333333-3333-4333-8333-333333333333"

    static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [FixtureURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    static func summary(_ id: String, _ name: String, _ category: String, _ lat: Double, _ lon: Double,
                        ord: Int? = nil, logo: String? = nil) -> String {
        let order = ord.map { ",\"ord\":\($0)" } ?? ""
        let logoField = logo.map { ",\"logo_url\":\"\($0)\"" } ?? ""
        return """
        {"id":"\(id)","name":"\(name)","name_lang":"en","category":"\(category)","kind":"venue","lat":\(lat),\
        "lon":\(lon),"is_public":true,"is_partner":false,"popularity":50\(order)\(logoField)}
        """
    }

    static var placesJSON: String {
        if isDemo { return "{\"items\":[]}" }
        let lat = Region.current.center.latitude
        let lon = Region.current.center.longitude
        let logo = "asset:StubLogo"
        let bakery = summary(logoPlaceID, "Fixture Bakery", "bakery", lat + 0.0012, lon + 0.0016, logo: logo)
        return "{\"items\":[\(summary(centerPlaceID, "Fixture Museum", "museum", lat, lon)),"
            + "\(summary(secondPlaceID, "Fixture Cafe", "coffee", lat + 0.01, lon + 0.012)),\(bakery)]}"
    }

    /// Main sights (Ш-69): six in Almaty (the first two appear at zoom 12, the rest closer) and two in Turkestan.
    /// The city overview of the stub (zoom 11) shows none of them.
    struct LandmarkFixture {
        let id: String
        let name: String
        let category: String
        let icon: String
        let lat: Double
        let lon: Double
        let minZoom: Double
        let rank: Int
        let region: String
    }

    static let landmarkFixtures: [LandmarkFixture] = [
        .init(id: "a0000000-0000-4000-8000-000000000001", name: "Medeu", category: "landmark", icon: "skating_rink",
              lat: 43.1575, lon: 77.0594, minZoom: 12, rank: 1, region: "almaty"),
        .init(id: "a0000000-0000-4000-8000-000000000002", name: "Kok-Tobe", category: "viewpoint", icon: "tv_tower",
              lat: 43.2330, lon: 76.9749, minZoom: 12, rank: 2, region: "almaty"),
        .init(id: "a0000000-0000-4000-8000-000000000003", name: "Zenkov Cathedral", category: "religious",
              icon: "cathedral", lat: 43.2582, lon: 76.9549, minZoom: 12.5, rank: 3, region: "almaty"),
        .init(id: "a0000000-0000-4000-8000-000000000004", name: "Green Bazaar", category: "market", icon: "bazaar",
              lat: 43.2646, lon: 76.9578, minZoom: 12.5, rank: 4, region: "almaty"),
        .init(id: "a0000000-0000-4000-8000-000000000005", name: "Central Mosque", category: "religious",
              icon: "mosque", lat: 43.2373, lon: 76.9425, minZoom: 13, rank: 5, region: "almaty"),
        .init(id: "a0000000-0000-4000-8000-000000000006", name: "Park of the First President", category: "park",
              icon: "park", lat: 43.2130, lon: 76.9215, minZoom: 13, rank: 6, region: "almaty"),
        .init(id: "a0000000-0000-4000-8000-000000000007", name: "Yasawi Mausoleum", category: "historic",
              icon: "mausoleum", lat: 43.2975, lon: 68.2722, minZoom: 12, rank: 1, region: "turkestan"),
        .init(id: "a0000000-0000-4000-8000-000000000008", name: "Charyn Canyon", category: "landmark",
              icon: "canyon", lat: 43.3500, lon: 79.0850, minZoom: 12, rank: 1, region: "charyn"),
    ]

    static var landmarksJSON: String {
        if isDemo { return "{\"landmarks\":[]}" }
        let items = landmarkFixtures.map { item in
            "{\"id\":\"\(item.id)\",\"name\":\"\(item.name)\",\"category\":\"\(item.category)\","
                + "\"icon\":\"\(item.icon)\",\"lat\":\(item.lat),\"lon\":\(item.lon),"
                + "\"min_zoom\":\(item.minZoom),\"rank\":\(item.rank),"
                + "\"region\":\"\(item.region)\"}"
        }
        return "{\"landmarks\":[\(items.joined(separator: ","))]}"
    }

    static func detailJSON(id: String) -> String {
        let second = id == secondPlaceID
        let sight = landmarkFixtures.first { $0.id == id }
        let bakery = id == logoPlaceID
        let name = sight?.name ?? (second ? "Fixture Cafe" : bakery ? "Fixture Bakery" : "Fixture Museum")
        let category = second
            ? "{\"slug\":\"coffee\",\"name\":\"Coffee\"}"
            : "{\"slug\":\"museum\",\"name\":\"Museum\"}"
        let prices = second ? "{\"avg_check_kzt\":3500}" : "{\"entry_price_kzt\":1500}"
        let lat = sight?.lat ?? Region.current.center.latitude + (second ? 0.01 : bakery ? 0.0012 : 0)
        let lon = sight?.lon ?? Region.current.center.longitude + (second ? 0.012 : bakery ? 0.0016 : 0)
        // Ш-70: the museum has a rating and hours; the cafe is open round the clock and has no reviews; the bakery
        // is closed today and carries a logo.
        let rating = second ? "null" : bakery ? "{\"average\":5.0,\"count\":1}" : "{\"average\":4.6,\"count\":23}"
        let today = second ? "{\"opens\":null,\"closes\":null,\"open_now\":true,\"open_24h\":true,"
            + "\"closed_today\":false}"
            : bakery ? "{\"opens\":null,\"closes\":null,\"open_now\":false,\"open_24h\":false,\"closed_today\":true}"
            : "{\"opens\":\"10:00\",\"closes\":\"23:00\",\"open_now\":true,\"open_24h\":false,\"closed_today\":false}"
        let logo = bakery ? "\"asset:StubLogo\"" : "null"
        var days: [String] = []
        for day in 0..<7 {
            days.append("{\"weekday\":\(day),\"intervals\":[{\"opens\":\"09:00\",\"closes\":\"18:00\"}]}")
        }
        return """
        {"id":"\(id)","name":"\(name)","name_lang":"en","names":{},"description":"A fixture place used by UI tests.",\
        "category":\(category),"kind":"venue","setting":null,"lat":\(lat),"lon":\(lon),\
        "address":"1 Test Street, Almaty","website":null,"prices":\(prices),"typical_visit_min":90,\
        "is_public":true,"is_partner":false,"is_mountain":false,"elevation_m":null,"popularity":50,\
        "photos":[],"hours":[\(days.joined(separator: ","))],"open_now":true,"menu":null,\
        "crowd":\(second ? crowdJSON : "null"),"events":[\(second ? eventsItemsJSON : "")],\
        "booking":\(second ? "{\"available\":true,\"kinds\":[\"table\",\"ticket\"]}" : "null"),\
        "rating":\(rating),"today":\(today),"logo_url":\(logo),\
        "data_updated_at":"2026-11-21T00:00:00Z"}
        """
    }

    /// The cafe has crowd statistics (the museum has none: `crowd: null`), events and a booking partner.
    static let crowdJSON = """
    {"now":{"level":0.8,"label":"busy","samples":4},"today":[{"hour":10,"level":0.3,"label":"empty","samples":3},\
    {"hour":12,"level":0.6,"label":"normal","samples":5},{"hour":14,"level":0.8,"label":"busy","samples":4}],\
    "samples":12,"updated_at":"2026-11-21T10:00:00+05:00"}
    """

    static let adEventID = "99999999-9999-4999-8999-999999999999"
    static let plainEventID = "99999999-9999-4999-8999-999999999998"

    /// A promoted event (the server sets `is_ad` only for non-public places) and an ordinary one.
    static var eventsItemsJSON: String {
        if isDemo { return "" }
        let lat = Region.current.center.latitude
        let lon = Region.current.center.longitude
        return """
        {"id":"\(adEventID)","title":"Fixture Jazz Night","title_lang":"en","description":"Live jazz.",\
        "starts_at":"2026-12-06T19:00:00+05:00","ends_at":"2026-12-06T22:00:00+05:00","price_kzt":5000,\
        "organizer":"Fixture Club","category":"concert","lat":\(lat + 0.03),"lon":\(lon - 0.04),\
        "place":null,"is_ad":true,"ad_label":"Ad"},\
        {"id":"\(plainEventID)","title":"Fixture Street Fair","title_lang":"en","description":null,\
        "starts_at":"2026-12-06T12:00:00+05:00","ends_at":null,"price_kzt":0,"organizer":null,\
        "category":"festival","lat":\(lat - 0.03),"lon":\(lon + 0.04),"place":null,"is_ad":false,"ad_label":null}
        """
    }

    /// The Ш-22a contract: a flat `options` list with `group`, `variant`, `arrive_at`, `congestion`.
    /// Pages: walk (2 variants), transit (bus recommended + metro with congestion), taxi; no scooter / car.
    /// Geometries are polyline6 lines from (43.231, 76.935) to the fixture museum.
    static var directionsJSON: String {
        """
        {"options":[\
        {"mode":"walk","group":"walk","variant":0,"duration_s":1260,"distance_m":1640,"cost_kzt_min":0,\
        "cost_kzt_max":0,"geometry":"oprmqAotvvqC_|BozDg{C_|Bg{CowH","approximate":false,"recommended":false,\
        "arrive_at":"2026-11-21T14:20:00+05:00","congestion":null},\
        {"mode":"walk","group":"walk","variant":1,"duration_s":1500,"distance_m":1900,"cost_kzt_min":0,\
        "cost_kzt_max":0,"geometry":"oprmqAotvvqC_|Bn}@owHonT","approximate":false,"recommended":false,\
        "arrive_at":"2026-11-21T14:24:00+05:00","congestion":null},\
        {"mode":"bus","group":"transit","variant":0,"duration_s":780,"distance_m":1900,"cost_kzt_min":120,\
        "cost_kzt_max":120,"geometry":"oprmqAotvvqCwyEotLwyEozD","approximate":true,"recommended":true,\
        "arrive_at":"2026-11-21T14:35:00+05:00","congestion":null,\
        "steps":[{"type":"walk","duration_s":120,"distance_m":150,"geometry":"oprmqAotvvqC"},\
        {"type":"ride","duration_s":600,"distance_m":1600,"geometry":"oprmqAotvvqC","route_ref":"92",\
        "kind":"bus","n_stops":4}]},\
        {"mode":"metro","group":"transit","variant":1,"duration_s":900,"distance_m":2100,"cost_kzt_min":100,\
        "cost_kzt_max":100,"geometry":"oprmqAotvvqCg{Cg{C_|BozD","approximate":true,"recommended":false,\
        "arrive_at":"2026-11-21T14:38:00+05:00","congestion":{"level":"medium"}},\
        {"mode":"taxi","group":"taxi","variant":0,"duration_s":420,"duration_s_min":420,"duration_s_max":660,\
        "distance_m":1750,"cost_kzt_min":900,"cost_kzt_max":1500,"geometry":"oprmqAotvvqC_|BozD",\
        "approximate":false,"recommended":false,"arrive_at":"2026-11-21T14:31:00+05:00","congestion":null}]}
        """
    }

    /// Where the stubbed "user" is: `-JolStubLocation denied|unavailable|outside` simulate the fallbacks.
    static var stubLocation: LocationResult {
        let arguments = ProcessInfo.processInfo.arguments
        let home = LocationResult.located(GeoPoint(lat: 43.2310, lon: 76.9350))
        guard let index = arguments.firstIndex(of: "-JolStubLocation"), index + 1 < arguments.count else {
            return home
        }
        switch arguments[index + 1] {
        case "denied": return .denied
        case "unavailable": return .unavailable
        case "outside": return .located(GeoPoint(lat: 37.33, lon: -122.03))
        // Standing at the fixture museum (the crowd check-in needs to be within 200 m of the place).
        case "near": return .located(GeoPoint(Region.current.center))
        default: return home
        }
    }

    /// In-memory favorites of the stub server (one process = one test).
    private static let favoritesLock = NSLock()
    private nonisolated(unsafe) static var favoriteIDs: [String] = []

    /// `GET /v1/me/favorites` for the stub user, newest first.
    static var favoritesJSON: String {
        favoritesLock.lock(); defer { favoritesLock.unlock() }
        let lat = Region.current.center.latitude
        let lon = Region.current.center.longitude
        let items = favoriteIDs.map { id -> String in
            let second = id == secondPlaceID
            let place = second ? summary(id, "Fixture Cafe", "coffee", lat + 0.01, lon + 0.012)
                : summary(id, "Fixture Museum", "museum", lat, lon)
            return String(place.dropLast()) + ",\"address\":\"1 Test Street\",\"created_at\":\"2026-11-21T00:00:00Z\"}"
        }
        return "{\"items\":[\(items.joined(separator: ","))]}"
    }

    static func setFavorite(_ id: String, _ on: Bool) {
        favoritesLock.lock(); defer { favoritesLock.unlock() }
        favoriteIDs.removeAll { $0 == id }
        if on { favoriteIDs.insert(id, at: 0) }
    }

    static var routesJSON: String {
        "{\"items\":[{\"id\":\"\(routeID)\",\"title\":\"Fixture Route\",\"description\":\"Two stops.\","
            + "\"places_count\":2}]}"
    }

    static var routeJSON: String {
        let lat = Region.current.center.latitude
        let lon = Region.current.center.longitude
        return "{\"id\":\"\(routeID)\",\"title\":\"Fixture Route\",\"description\":\"Two stops.\",\"items\":["
            + "\(summary(centerPlaceID, "Fixture Museum", "museum", lat, lon, ord: 1)),"
            + "\(summary(secondPlaceID, "Fixture Cafe", "coffee", lat + 0.01, lon + 0.012, ord: 2))]}"
    }
}

@MainActor
final class StubLocationProvider: LocationProviding {
    func currentLocation() async -> LocationResult { UITestSupport.stubLocation }

    func knownLocation() -> GeoPoint? {
        if case .located(let point) = UITestSupport.stubLocation { return point }
        return nil
    }
}

final class FixtureURLProtocol: URLProtocol, @unchecked Sendable {
    /// Set by `stopLoading`: a replayed event stream stops when the client cancels.
    nonisolated(unsafe) var stopped = false

    override static func canInit(with request: URLRequest) -> Bool { true }
    override static func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let path = request.url?.path ?? ""
        if UITestExtraStub.isOffline {
            client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
            return
        }
        if let extra = UITestExtraStub.answer(
            method: request.httpMethod ?? "GET", path: path,
            ifNoneMatch: request.value(forHTTPHeaderField: "If-None-Match"),
            signedIn: request.value(forHTTPHeaderField: "Authorization") != nil
        ) {
            if path == "/v1/devices" || path == "/v1/analytics/events" {
                // Read with `xcrun simctl spawn booted log show --predicate 'eventMessage CONTAINS "JolStub"'`.
                let auth = request.value(forHTTPHeaderField: "Authorization") != nil
                NSLog("JolStub %@ auth=%d body=%@", path, auth ? 1 : 0, "\(requestBody())")
            }
            finish(with: extra)
            return
        }
        if ChatStub.handles(path) { startChat(path: path) } else { startPlain(path: path) }
    }

    private func startPlain(path: String) {
        var status = 200
        var headers = ["Content-Type": "application/json"]
        var body: String?
        if let answer = UITestPlaceActions.answer(
            method: request.httpMethod ?? "GET", path: path, payload: requestBody(),
            signedIn: request.value(forHTTPHeaderField: "Authorization") != nil
        ) {
            (status, body) = (answer.status, answer.body)
            headers.merge(answer.headers) { _, new in new }
        } else if path == "/v1/geocode/reverse", let answer = UITestGeocode.answer(url: request.url) {
            (status, body) = (answer.status, answer.body)
        } else if let fixed = Self.fixture(path: path) {
            body = fixed
        } else if path == "/v1/me/favorites" || path.hasPrefix("/v1/me/favorites/") {
            if request.value(forHTTPHeaderField: "Authorization") == nil {
                (status, body) = (401, "{\"error\":{\"code\":\"unauthorized\",\"message\":\"stub\"}}")
            } else if path == "/v1/me/favorites" {
                body = UITestSupport.favoritesJSON
            } else {
                UITestSupport.setFavorite(String(path.dropFirst("/v1/me/favorites/".count)),
                                          request.httpMethod == "PUT")
                (status, body) = (204, "")
            }
        } else if path.hasPrefix("/v1/auth/otp/") || path == "/v1/me" {
            (status, body) = authAnswer(path: path, payload: requestBody(), headers: &headers)
        }
        if body == nil && status == 200 { status = 404 }
        let notFound = "{\"error\":{\"code\":\"not_found\",\"message\":\"stub\"}}"
        let data = Data((body ?? (status == 404 ? notFound : "")).utf8)
        let response = HTTPURLResponse(
            url: request.url ?? URL(fileURLWithPath: "/"), statusCode: status, httpVersion: "HTTP/1.1",
            headerFields: headers
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    /// Fixed answers of the read-only endpoints.
    private static func fixture(path: String) -> String? {
        switch path {
        case "/v1/places": UITestSupport.placesJSON
        case "/v1/landmarks": UITestSupport.landmarksJSON
        case "/v1/directions": UITestSupport.directionsJSON
        case "/v1/curated-routes": UITestSupport.routesJSON
        case _ where path.hasPrefix("/v1/places/"):
            UITestSupport.detailJSON(id: String(path.dropFirst("/v1/places/".count)))
        case _ where path.hasPrefix("/v1/curated-routes/"): UITestSupport.routeJSON
        default: nil
        }
    }

    func requestBody() -> [String: Any] {
        var data = request.httpBody
        if data == nil, let stream = request.httpBodyStream {
            stream.open()
            var collected = Data()
            var buffer = [UInt8](repeating: 0, count: 2048)
            while stream.hasBytesAvailable {
                let count = stream.read(&buffer, maxLength: buffer.count)
                if count <= 0 { break }
                collected.append(buffer, count: count)
            }
            stream.close()
            data = collected
        }
        return data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] } ?? [:]
    }

    /// Sign-in fixtures: any destination gets a code; `123456` is the right one; `ratelimit@…` gets a 429
    /// with `Retry-After: 2`; `/v1/me` answers for the signed-in stub user.
    private func authAnswer(path: String, payload: [String: Any], headers: inout [String: String]) -> (Int, String?) {
        let destination = (payload["destination"] as? String) ?? ""
        switch path {
        case "/v1/auth/otp/request":
            if destination.hasPrefix("ratelimit") {
                headers["Retry-After"] = "2"
                return (429, "{\"error\":{\"code\":\"otp_rate_limited\",\"message\":\"Try again later\"}}")
            }
            return (204, "")
        case "/v1/auth/otp/verify":
            if (payload["code"] as? String) == "123456" {
                return (200, "{\"access_token\":\"stub-access\",\"refresh_token\":\"stub-refresh\"}")
            }
            if (payload["code"] as? String) == "111111" {
                return (401, "{\"error\":{\"code\":\"otp_expired\",\"message\":\"Code expired\"}}")
            }
            return (401, "{\"error\":{\"code\":\"otp_invalid\",\"message\":\"Invalid or expired code\"}}")
        case "/v1/me":
            return (200, "{\"id\":\"00000000-0000-4000-8000-000000000001\",\"email\":\"tourist@example.com\"}")
        default:
            return (404, nil)
        }
    }

    override func stopLoading() { stopped = true }
}
#endif
