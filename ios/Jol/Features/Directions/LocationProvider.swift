import CoreLocation
import Foundation

enum LocationResult: Equatable, Sendable {
    case located(GeoPoint)
    /// The user refused (or restricted) location access.
    case denied
    /// Access is fine but no fix arrived (timeout, no signal).
    case unavailable
}

/// One-shot current location. A protocol so tests and UI tests can substitute it.
@MainActor
protocol LocationProviding: AnyObject {
    func currentLocation() async -> LocationResult
    /// Ш-68: the last fix if the user ALREADY granted access and it is fresh. Never asks for permission and never
    /// waits (used while sending a chat message); `nil` means "unknown", the server then uses the city centre.
    func knownLocation() -> GeoPoint?
}

extension LocationProviding {
    func knownLocation() -> GeoPoint? { nil }
}

/// `CLLocationManager` wrapper: asks for when-in-use permission if it was never asked, then returns one fix.
@MainActor
final class CoreLocationProvider: NSObject, LocationProviding, @preconcurrency CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var pending: CheckedContinuation<LocationResult, Never>?
    private var timeout: Task<Void, Never>?

    /// A fix younger than this is reused without a new request.
    private static let freshness: TimeInterval = 120
    /// How old a fix may be to go along with a chat message (a tourist walks ~80 m a minute).
    private static let knownFreshness: TimeInterval = 600
    private static let timeoutSeconds = 10

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyHundredMeters
    }

    func currentLocation() async -> LocationResult {
        switch manager.authorizationStatus {
        case .denied, .restricted:
            return .denied
        default:
            break
        }
        if let location = manager.location, -location.timestamp.timeIntervalSinceNow < Self.freshness {
            return .located(GeoPoint(location.coordinate))
        }
        finish(.unavailable)  // a second request supersedes a stuck one
        return await withCheckedContinuation { continuation in
            pending = continuation
            if manager.authorizationStatus == .notDetermined {
                manager.requestWhenInUseAuthorization()  // continues in locationManagerDidChangeAuthorization
            } else {
                requestFix()
            }
        }
    }

    func knownLocation() -> GeoPoint? {
        switch manager.authorizationStatus {
        case .authorizedWhenInUse, .authorizedAlways:
            break
        default:
            return nil  // not asked / refused: no prompt here
        }
        if let location = manager.location, -location.timestamp.timeIntervalSinceNow < Self.knownFreshness {
            return GeoPoint(location.coordinate)
        }
        if pending == nil { manager.requestLocation() }  // warms up the next message; permission is already granted
        return nil
    }

    private func requestFix() {
        manager.requestLocation()
        timeout?.cancel()
        timeout = Task { [weak self] in
            try? await Task.sleep(for: .seconds(Self.timeoutSeconds))
            guard !Task.isCancelled else { return }
            self?.finish(.unavailable)
        }
    }

    private func finish(_ result: LocationResult) {
        timeout?.cancel()
        timeout = nil
        let continuation = pending
        pending = nil
        continuation?.resume(returning: result)
    }

    // MARK: - CLLocationManagerDelegate

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard pending != nil else { return }
        switch manager.authorizationStatus {
        case .denied, .restricted: finish(.denied)
        case .notDetermined: break
        default: requestFix()
        }
    }

    func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let location = locations.last else { return }
        finish(.located(GeoPoint(location.coordinate)))
    }

    func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        if (error as? CLError)?.code == .denied {
            finish(.denied)
        } else {
            finish(.unavailable)
        }
    }
}
