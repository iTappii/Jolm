import CoreLocation
import Foundation

/// The legs of the shown days as map lines, with the intercity transfers (Ш-62).
extension TripMapModel {
    var lines: [TripMapLine] {
        let everyItem = Dictionary(
            days.flatMap(\.items).map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        return drawnDays.flatMap { index, day in
            let hex = Self.dayColors[index % Self.dayColors.count]
            let byID = Dictionary(day.items.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
            return day.legs.compactMap { leg -> TripMapLine? in
                if leg.intercity != nil {
                    // A transfer leaves from a stop of an earlier day or from where the night was spent (Ш-62).
                    guard let to = everyItem[leg.toItemID]?.place.coordinate,
                          let from = leg.fromItemID.flatMap({ everyItem[$0]?.place.coordinate })
                            ?? transferOrigin(dayIndex: index) else { return nil }
                    return TripMapLine(legID: leg.id, coordinates: [from, to], approximate: true, colorHex: hex)
                }
                guard let from = leg.fromItemID.flatMap({ byID[$0] }), let to = byID[leg.toItemID] else { return nil }
                if let option = leg.activeOption {
                    let line = option.line
                    if line.count >= 2 {
                        return TripMapLine(legID: leg.id, coordinates: line, approximate: false, colorHex: hex)
                    }
                }
                return TripMapLine(
                    legID: leg.id, coordinates: [from.place.coordinate, to.place.coordinate], approximate: true,
                    colorHex: hex
                )
            }
        }
    }

    /// Where the previous day ended: the night's place, else its last stop (the start of a transfer with no stop).
    func transferOrigin(dayIndex: Int) -> CLLocationCoordinate2D? {
        guard days.indices.contains(dayIndex - 1) else { return nil }
        let previous = days[dayIndex - 1]
        return previous.overnight?.coordinate ?? previous.items.last?.place.coordinate
    }

    /// What the camera fits besides the stops and lines (Ш-62): the places where the drawn days' nights are spent,
    /// so a day that ends in another city shows both ends.
    var fitExtras: [CLLocationCoordinate2D] {
        drawnDays.compactMap { $0.day.overnight?.coordinate }
    }
}
