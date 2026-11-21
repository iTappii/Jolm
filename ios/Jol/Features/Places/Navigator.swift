import CoreLocation
import Foundation
import UIKit

/// "Open in navigator" links (SSOT §13: only links within the providers' terms, no data copying).
enum Navigator {
    enum App: String, CaseIterable, Identifiable {
        case appleMaps
        case twoGIS

        var id: String { rawValue }
    }

    /// Apple Maps: walking/driving is chosen by the user inside Maps (`dirflg` not forced).
    static func url(for app: App, name: String, coordinate: CLLocationCoordinate2D) -> URL? {
        let lat = String(format: "%.6f", coordinate.latitude)
        let lon = String(format: "%.6f", coordinate.longitude)
        switch app {
        case .appleMaps:
            var components = URLComponents(string: "https://maps.apple.com/")
            components?.queryItems = [
                URLQueryItem(name: "daddr", value: "\(lat),\(lon)"),
                URLQueryItem(name: "q", value: name),
            ]
            return components?.url
        case .twoGIS:
            // 2GIS app scheme (note: lon,lat order). Offered only if the app is installed.
            return URL(string: "dgis://2gis.ru/routeSearch/rsType/car/to/\(lon),\(lat)")
        }
    }

    /// Apple Maps is always available; 2GIS only when `dgis` is installed (`LSApplicationQueriesSchemes`).
    @MainActor
    static func availableApps() -> [App] {
        var apps: [App] = [.appleMaps]
        if let probe = URL(string: "dgis://"), UIApplication.shared.canOpenURL(probe) { apps.append(.twoGIS) }
        return apps
    }
}
