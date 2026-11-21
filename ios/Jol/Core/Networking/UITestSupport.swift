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

    private static func summary(_ id: String, _ name: String, _ category: String, _ lat: Double, _ lon: Double,
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
        "photos":[],"hours":[\(days.joined(separator: ","))],"open_now":true,"menu":null,"crowd":null,\
        "data_updated_at":"2026-11-21T00:00:00Z"}
        """
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

final class FixtureURLProtocol: URLProtocol, @unchecked Sendable {
    override static func canInit(with request: URLRequest) -> Bool { true }
    override static func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        let path = request.url?.path ?? ""
        let body: String?
        if path == "/v1/places" {
            body = UITestSupport.placesJSON
        } else if path.hasPrefix("/v1/places/") {
            body = UITestSupport.detailJSON(id: String(path.dropFirst("/v1/places/".count)))
        } else if path == "/v1/curated-routes" {
            body = UITestSupport.routesJSON
        } else if path.hasPrefix("/v1/curated-routes/") {
            body = UITestSupport.routeJSON
        } else {
            body = nil
        }
        let status = body == nil ? 404 : 200
        let data = Data((body ?? "{\"error\":{\"code\":\"not_found\",\"message\":\"stub\"}}").utf8)
        let response = HTTPURLResponse(
            url: request.url ?? URL(fileURLWithPath: "/"), statusCode: status, httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
#endif
