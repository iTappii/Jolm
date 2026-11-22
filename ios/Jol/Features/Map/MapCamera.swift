import CoreLocation
import UIKit

/// Pure camera-fitting maths (Ш-63), kept apart from MapLibre so it can be unit-tested.
enum CameraFit {
    /// Zoom for a day with a single stop (or stops on top of each other) on the trip map: close enough to read the
    /// street, never the "building filling the screen" MapLibre picks for a zero-size box.
    static let singleStopZoom: Double = 15
    /// Zoom for the only stop of the live route.
    static let liveSingleStopZoom: Double = 14
    /// Boxes smaller than this (degrees, about 55 m) count as a single point.
    static let degenerateSpan: Double = 0.0005

    enum Plan: Equatable {
        case center(CLLocationCoordinate2D, zoom: Double)
        case bounds
    }

    /// A single point or a degenerate box is centred at a sensible zoom; anything bigger is fitted to the box.
    static func plan(for coordinates: [CLLocationCoordinate2D], singleZoom: Double) -> Plan? {
        guard let first = coordinates.first else { return nil }
        let lats = coordinates.map(\.latitude), lons = coordinates.map(\.longitude)
        let minLat = lats.min() ?? first.latitude, maxLat = lats.max() ?? first.latitude
        let minLon = lons.min() ?? first.longitude, maxLon = lons.max() ?? first.longitude
        guard maxLat - minLat < degenerateSpan, maxLon - minLon < degenerateSpan else { return .bounds }
        return .center(
            CLLocationCoordinate2D(latitude: (minLat + maxLat) / 2, longitude: (minLon + maxLon) / 2),
            zoom: singleZoom)
    }

    /// Edge padding that lands the live route above the chat card (`targetInset` = height of what covers the map's
    /// bottom). `setVisibleCoordinates` adds its padding to the map's CURRENT content inset, which may still be
    /// animating towards `targetInset`, so the padding asks for the wanted inset minus the current one.
    /// A narrow strip above the card (keyboard up) gets tighter margins, so the route is not drawn tiny.
    static func liveRoutePadding(mapHeight: CGFloat, targetInset: CGFloat, currentInset: CGFloat) -> UIEdgeInsets {
        let tight = mapHeight - targetInset < 420
        let margin: CGFloat = tight ? 52 : 84
        let bottom = max(margin, targetInset + margin - currentInset)
        return UIEdgeInsets(top: tight ? 56 : 72, left: 56, bottom: bottom, right: 56)
    }
}

extension CLLocationCoordinate2D: @retroactive Equatable {
    public static func == (lhs: CLLocationCoordinate2D, rhs: CLLocationCoordinate2D) -> Bool {
        lhs.latitude == rhs.latitude && lhs.longitude == rhs.longitude
    }
}
