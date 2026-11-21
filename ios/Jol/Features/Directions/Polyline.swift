import CoreLocation
import Foundation

/// Encoded polyline decoder. The server sends polyline6 (Valhalla): 1e-6 degree precision, lat before lon.
enum Polyline {
    /// Malformed input yields the points decoded before the error (never a crash).
    static func decode(_ encoded: String, precision: Int = 6) -> [CLLocationCoordinate2D] {
        let scale = pow(10.0, Double(precision))
        let bytes = Array(encoded.utf8)
        var index = 0
        var lat = 0
        var lon = 0
        var result: [CLLocationCoordinate2D] = []

        func nextValue() -> Int? {
            var shift = 0
            var accumulated = 0
            while index < bytes.count {
                let chunk = Int(bytes[index]) - 63
                index += 1
                guard chunk >= 0, shift < 60 else { return nil }
                accumulated |= (chunk & 0x1F) << shift
                shift += 5
                if chunk < 0x20 {
                    return accumulated & 1 == 1 ? ~(accumulated >> 1) : accumulated >> 1
                }
            }
            return nil
        }

        while index < bytes.count {
            guard let dLat = nextValue(), let dLon = nextValue() else { break }
            lat += dLat
            lon += dLon
            result.append(CLLocationCoordinate2D(latitude: Double(lat) / scale, longitude: Double(lon) / scale))
        }
        return result
    }
}
