import CoreLocation
import MapLibre
import Observation
import UIKit

/// Lets SwiftUI draw on top of the map (Ш-54): the live route's pins, edges and duration capsules are SwiftUI views
/// (VoiceOver, 44 pt targets, Dynamic Type) placed at the screen point of a coordinate. The map bumps `version` on
/// every camera frame, which re-renders whatever read `point(for:)`.
@MainActor
@Observable
final class MapProjection {
    private(set) var version = 0
    @ObservationIgnored weak var map: MLNMapView?

    func invalidate() {
        version &+= 1
    }

    /// For calls made while SwiftUI is updating a view (`updateUIView`): changing observed state right there is not
    /// allowed, so the bump goes to the next turn of the run loop.
    func invalidateSoon() {
        Task { @MainActor [weak self] in self?.invalidate() }
    }

    /// Screen point (in the map view's coordinates) of `coordinate`; `nil` while there is no map.
    func point(for coordinate: CLLocationCoordinate2D) -> CGPoint? {
        _ = version
        guard let map, map.bounds.width > 0 else { return nil }
        return map.convert(coordinate, toPointTo: map)
    }
}
