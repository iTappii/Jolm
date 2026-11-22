import CoreLocation
import Foundation

/// A numbered stop of the shown day, as the map draws it.
struct TripMapStop {
    let placeID: UUID
    let number: Int
    let coordinate: CLLocationCoordinate2D
    /// The day's colour (`TripMapModel.dayColors`): all days at once are told apart by it.
    var colorHex: UInt32 = 0xFF7A00
}

/// One leg of the shown day. `approximate`: no route geometry, a straight line between the stops.
struct TripMapLine {
    let legID: UUID
    let coordinates: [CLLocationCoordinate2D]
    let approximate: Bool
    var colorHex: UInt32 = 0xFF7A00
}
