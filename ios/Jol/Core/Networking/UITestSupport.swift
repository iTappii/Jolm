#if DEBUG
import CoreLocation
import Foundation

/// Debug-only support for UI tests (`-JolStubAPI`): a `URLProtocol` that answers the places and curated-route
/// endpoints from fixtures, so tests never depend on a running server, and an offline stub map style.
enum UITestSupport {
    static var isStubbed: Bool { ProcessInfo.processInfo.arguments.contains("-JolStubAPI") }

    /// Fixture place that sits exactly at `AlmatyCamera.center`, i.e. in the middle of the screen at launch.
    static let centerPlaceID = "11111111-1111-4111-8111-111111111111"
    static let secondPlaceID = "22222222-2222-4222-8222-222222222222"
    static let routeID = "33333333-3333-4333-8333-333333333333"

    static func makeSession() -> URLSession {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [FixtureURLProtocol.self]
        return URLSession(configuration: configuration)
    }

    static func summary(_ id: String, _ name: String, _ category: String, _ lat: Double, _ lon: Double,
                        ord: Int? = nil) -> String {
        let order = ord.map { ",\"ord\":\($0)" } ?? ""
        return """
        {"id":"\(id)","name":"\(name)","name_lang":"en","category":"\(category)","kind":"venue","lat":\(lat),\
        "lon":\(lon),"is_public":true,"is_partner":false,"popularity":50\(order)}
        """
    }

    static var placesJSON: String {
        let lat = AlmatyCamera.center.latitude
        let lon = AlmatyCamera.center.longitude
        return "{\"items\":[\(summary(centerPlaceID, "Fixture Museum", "museum", lat, lon)),"
            + "\(summary(secondPlaceID, "Fixture Cafe", "coffee", lat + 0.01, lon + 0.012))]}"
    }

    static func detailJSON(id: String) -> String {
        let second = id == secondPlaceID
        let name = second ? "Fixture Cafe" : "Fixture Museum"
        let category = second
            ? "{\"slug\":\"coffee\",\"name\":\"Coffee\"}"
            : "{\"slug\":\"museum\",\"name\":\"Museum\"}"
        let prices = second ? "{\"avg_check_kzt\":3500}" : "{\"entry_price_kzt\":1500}"
        let lat = AlmatyCamera.center.latitude + (second ? 0.01 : 0)
        let lon = AlmatyCamera.center.longitude + (second ? 0.012 : 0)
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
        let lat = AlmatyCamera.center.latitude
        let lon = AlmatyCamera.center.longitude
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
        case "near": return .located(GeoPoint(AlmatyCamera.center))
        default: return home
        }
    }

    /// In-memory favorites of the stub server (one process = one test).
    private static let favoritesLock = NSLock()
    private nonisolated(unsafe) static var favoriteIDs: [String] = []

    /// `GET /v1/me/favorites` for the stub user, newest first.
    static var favoritesJSON: String {
        favoritesLock.lock(); defer { favoritesLock.unlock() }
        let lat = AlmatyCamera.center.latitude
        let lon = AlmatyCamera.center.longitude
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
        let lat = AlmatyCamera.center.latitude
        let lon = AlmatyCamera.center.longitude
        return "{\"id\":\"\(routeID)\",\"title\":\"Fixture Route\",\"description\":\"Two stops.\",\"items\":["
            + "\(summary(centerPlaceID, "Fixture Museum", "museum", lat, lon, ord: 1)),"
            + "\(summary(secondPlaceID, "Fixture Cafe", "coffee", lat + 0.01, lon + 0.012, ord: 2))]}"
    }
}

@MainActor
final class StubLocationProvider: LocationProviding {
    func currentLocation() async -> LocationResult { UITestSupport.stubLocation }
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
