import CoreLocation
import MapLibre
import UIKit

/// The full route map's layers (Ш-37) and the event pins (Ш-48).
extension MapCoordinator {
    private static let eventColor = UIColor(hex: 0x7C3AED)

    func installTripLayers(in style: MLNStyle) {
        let legs = MLNShapeSource(identifier: Layer.tripSource, shape: nil, options: nil)
        style.addSource(legs)
        func make(_ id: String, _ predicate: String, color: UIColor, width: CGFloat) -> MLNLineStyleLayer {
            let layer = MLNLineStyleLayer(identifier: id, source: legs)
            layer.predicate = NSPredicate(format: predicate)
            layer.lineColor = NSExpression(forConstantValue: color)
            layer.lineWidth = NSExpression(forConstantValue: width)
            layer.lineCap = NSExpression(forConstantValue: "round")
            layer.lineJoin = NSExpression(forConstantValue: "round")
            return layer
        }
        let casing = make(Layer.tripCasing, "approx == 0 OR approx == 1", color: .white, width: 9)
        style.addLayer(casing)
        style.addLayer(make(Layer.tripLine, "approx == 0", color: JolColor.brandUIColor, width: 5))
        let dashed = make(Layer.tripDashed, "approx == 1", color: JolColor.brandUIColor, width: 4)
        dashed.lineDashPattern = NSExpression(forConstantValue: [2, 2])
        style.addLayer(dashed)

        let stops = MLNShapeSource(identifier: Layer.tripStopsSource, shape: nil, options: nil)
        style.addSource(stops)
        let circle = MLNCircleStyleLayer(identifier: Layer.tripStop, source: stops)
        circle.circleColor = NSExpression(forConstantValue: UIColor.white)
        circle.circleRadius = NSExpression(forConstantValue: 14)
        circle.circleStrokeColor = NSExpression(forConstantValue: JolColor.brandUIColor)
        circle.circleStrokeWidth = NSExpression(forConstantValue: 4)
        style.addLayer(circle)

        let numbers = MLNSymbolStyleLayer(identifier: Layer.tripStopNumber, source: stops)
        numbers.text = NSExpression(forKeyPath: "number")
        numbers.textColor = NSExpression(forConstantValue: UIColor.black)
        numbers.textFontSize = NSExpression(forConstantValue: 14)
        numbers.textFontNames = NSExpression(forConstantValue: ["Noto Sans Bold"])
        numbers.textAllowsOverlap = NSExpression(forConstantValue: true)
        style.addLayer(numbers)
    }

    func installEventLayers(in style: MLNStyle) {
        let source = MLNShapeSource(identifier: Layer.eventsSource, shape: nil, options: nil)
        style.addSource(source)
        let dot = MLNCircleStyleLayer(identifier: Layer.eventDot, source: source)
        dot.circleColor = NSExpression(forConstantValue: Self.eventColor)
        dot.circleRadius = NSExpression(forConstantValue: 10)
        dot.circleStrokeColor = NSExpression(forConstantValue: UIColor.white)
        dot.circleStrokeWidth = NSExpression(forConstantValue: 3)
        style.addLayer(dot)

        let label = MLNSymbolStyleLayer(identifier: Layer.eventLabel, source: source)
        label.text = NSExpression(forKeyPath: "caption")
        label.textFontNames = NSExpression(forConstantValue: ["Noto Sans Bold"])
        label.textFontSize = NSExpression(forConstantValue: 12)
        label.textColor = NSExpression(forConstantValue: Self.eventColor)
        label.textHaloColor = NSExpression(forConstantValue: UIColor.white)
        label.textHaloWidth = NSExpression(forConstantValue: 1.5)
        label.textOffset = NSExpression(forConstantValue: NSValue(cgVector: CGVector(dx: 0, dy: 1.3)))
        label.textAnchor = NSExpression(forConstantValue: "top")
        label.textOptional = NSExpression(forConstantValue: true)
        style.addLayer(label)
    }

    /// Draws the full route map's day and the event pins when their versions changed.
    func applyTripAndEvents(_ parent: MapView, style: MLNStyle, map: MLNMapView) {
        if appliedTripVersion != parent.tripVersion || appliedTripFitVersion != parent.tripFitVersion {
            let refit = appliedTripFitVersion != parent.tripFitVersion
            appliedTripVersion = parent.tripVersion
            appliedTripFitVersion = parent.tripFitVersion
            applyTrip(stops: parent.tripStops, lines: parent.tripLines, color: parent.tripColor, refit: refit, map: map)
        }
        if appliedEventsVersion != parent.eventsVersion {
            appliedEventsVersion = parent.eventsVersion
            applyEvents(parent.events, in: style)
        }
    }

    private func applyTrip(
        stops: [TripMapStop], lines: [TripMapLine], color: UIColor, refit: Bool, map: MLNMapView
    ) {
        guard let style = map.style else { return }
        for id in [Layer.tripLine, Layer.tripDashed] {
            (style.layer(withIdentifier: id) as? MLNLineStyleLayer)?.lineColor = NSExpression(forConstantValue: color)
        }
        (style.layer(withIdentifier: Layer.tripStop) as? MLNCircleStyleLayer)?.circleStrokeColor =
            NSExpression(forConstantValue: color)
        let legSource = style.source(withIdentifier: Layer.tripSource) as? MLNShapeSource
        let stopSource = style.source(withIdentifier: Layer.tripStopsSource) as? MLNShapeSource
        let legFeatures = lines.map { line -> MLNPolylineFeature in
            var coordinates = line.coordinates
            let feature = MLNPolylineFeature(coordinates: &coordinates, count: UInt(coordinates.count))
            feature.attributes = ["leg": line.legID.uuidString.lowercased(), "approx": line.approximate ? 1 : 0]
            return feature
        }
        legSource?.shape = legFeatures.isEmpty ? nil : MLNShapeCollectionFeature(shapes: legFeatures)
        stopSource?.shape = stops.isEmpty ? nil : MLNShapeCollectionFeature(shapes: stops.map { stop in
            let feature = MLNPointFeature()
            feature.coordinate = stop.coordinate
            feature.attributes = ["id": stop.placeID.uuidString.lowercased(), "number": String(stop.number)]
            return feature
        })
        guard refit else { return }
        var all = stops.map(\.coordinate) + lines.flatMap(\.coordinates)
        guard !all.isEmpty else { return }
        map.setVisibleCoordinates(
            &all, count: UInt(all.count),
            edgePadding: UIEdgeInsets(top: 130, left: 50, bottom: 90, right: 50), animated: true
        )
    }

    func applyEvents(_ events: [EventItem], in style: MLNStyle) {
        guard let source = style.source(withIdentifier: Layer.eventsSource) as? MLNShapeSource else { return }
        source.shape = events.isEmpty ? nil : MLNShapeCollectionFeature(shapes: events.map { event in
            let feature = MLNPointFeature()
            feature.coordinate = event.coordinate
            let caption = event.visibleAdLabel.map { "\($0) · \(event.title)" } ?? event.title
            feature.attributes = ["event": event.id.uuidString.lowercased(), "caption": caption]
            return feature
        })
    }
}
