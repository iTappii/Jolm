#if DEBUG
import CoreLocation
import Foundation

/// Stub of `GET /v1/geocode/reverse` for UI tests (`-JolStubAPI`, Ш-23c):
/// - within 30 m of a fixture place → `kind: place` with that place;
/// - anywhere else → `kind: address` ("Test Street 7", building point = the tapped point);
/// - `-JolStubGeocode point` → the bare point; `building` → an address with the building name "Fixture Hall";
///   `fail` → a 500 (the card must still open as a bare point).
enum UITestGeocode {
    struct Answer {
        var status = 200
        var body: String
    }

    static var mode: String? {
        let arguments = ProcessInfo.processInfo.arguments
        guard let index = arguments.firstIndex(of: "-JolStubGeocode"), index + 1 < arguments.count else { return nil }
        return arguments[index + 1]
    }

    static func answer(url: URL?) -> Answer? {
        guard let url, let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems,
              let lat = items.first(where: { $0.name == "lat" })?.value.flatMap(Double.init),
              let lon = items.first(where: { $0.name == "lon" })?.value.flatMap(Double.init) else { return nil }
        let tapped = CLLocation(latitude: lat, longitude: lon)
        let centerLat = AlmatyCamera.center.latitude
        let centerLon = AlmatyCamera.center.longitude
        let places = [
            (UITestSupport.centerPlaceID, "Fixture Museum", "museum", centerLat, centerLon),
            (UITestSupport.secondPlaceID, "Fixture Cafe", "coffee", centerLat + 0.01, centerLon + 0.012),
        ]
        for (id, name, category, placeLat, placeLon) in places {
            let distance = tapped.distance(from: CLLocation(latitude: placeLat, longitude: placeLon))
            if distance <= 30 {
                let summary = UITestSupport.summary(id, name, category, placeLat, placeLon)
                return Answer(body: "{\"kind\":\"place\",\"place\":\(summary),\"lat\":\(lat),\"lon\":\(lon),"
                    + "\"distance_m\":\(Int(distance))}")
            }
        }
        switch mode {
        case "point": return Answer(body: "{\"kind\":\"point\",\"lat\":\(lat),\"lon\":\(lon)}")
        case "fail": return Answer(status: 500, body: "{\"error\":{\"code\":\"internal\",\"message\":\"stub\"}}")
        case "building":
            return Answer(body: "{\"kind\":\"address\",\"address\":\"Test Street 7\",\"name\":\"Fixture Hall\","
                + "\"lat\":\(lat),\"lon\":\(lon),\"distance_m\":9}")
        default:
            return Answer(body: "{\"kind\":\"address\",\"address\":\"Test Street 7\",\"name\":null,"
                + "\"lat\":\(lat),\"lon\":\(lon),\"distance_m\":9}")
        }
    }
}
#endif
