import CoreLocation
import MapLibre
import UIKit

/// Route-related map layers: curated route line and stops, and the way to a place (Ш-23).
extension MapCoordinator {
    func installRouteLayers(in style: MLNStyle) {
        if style.source(withIdentifier: Layer.routeSource) == nil {
            // Style without the Jol overlay (bundled placeholder / UI-test stub): draw the line ourselves.
            let line = MLNShapeSource(identifier: Layer.routeSource, shape: nil, options: nil)
            style.addSource(line)
            let lineLayer = MLNLineStyleLayer(identifier: Layer.routeLine, source: line)
            lineLayer.lineColor = NSExpression(forConstantValue: JolColor.brandUIColor)
            lineLayer.lineWidth = NSExpression(forConstantValue: 4)
            lineLayer.lineCap = NSExpression(forConstantValue: "round")
            lineLayer.lineJoin = NSExpression(forConstantValue: "round")
            style.addLayer(lineLayer)
        }

        let stops = MLNShapeSource(identifier: Layer.routeStopsSource, shape: nil, options: nil)
        style.addSource(stops)
        let stopLayer = MLNCircleStyleLayer(identifier: Layer.routeStop, source: stops)
        stopLayer.circleColor = NSExpression(forConstantValue: JolColor.brandUIColor)
        stopLayer.circleRadius = NSExpression(forConstantValue: 14)
        stopLayer.circleStrokeColor = NSExpression(forConstantValue: UIColor.white)
        stopLayer.circleStrokeWidth = NSExpression(forConstantValue: 2.5)
        style.addLayer(stopLayer)

        let numbers = MLNSymbolStyleLayer(identifier: Layer.routeStopNumber, source: stops)
        numbers.text = NSExpression(forKeyPath: "number")
        numbers.textColor = NSExpression(forConstantValue: UIColor.black)
        numbers.textFontSize = NSExpression(forConstantValue: 14)
        numbers.textFontNames = NSExpression(forConstantValue: ["Noto Sans Bold"])
        numbers.textAllowsOverlap = NSExpression(forConstantValue: true)
        style.addLayer(numbers)
    }

    /// The ways to a place: a white casing, the other variants thin and pale, the chosen one thick, all under the
    /// pins; plus a dot at the origin.
    func installDirectionsLayers(in style: MLNStyle, belowPins pins: MLNStyleLayer) {
        let line = MLNShapeSource(identifier: Layer.directionsSource, shape: nil, options: nil)
        style.addSource(line)
        func make(_ id: String, _ predicate: String?, color: UIColor, width: CGFloat) -> MLNLineStyleLayer {
            let layer = MLNLineStyleLayer(identifier: id, source: line)
            if let predicate { layer.predicate = NSPredicate(format: predicate) }
            layer.lineColor = NSExpression(forConstantValue: color)
            layer.lineWidth = NSExpression(forConstantValue: width)
            layer.lineCap = NSExpression(forConstantValue: "round")
            layer.lineJoin = NSExpression(forConstantValue: "round")
            return layer
        }
        style.insertLayer(make(Layer.directionsCasing, nil, color: .white, width: 9), below: pins)
        style.insertLayer(make(Layer.directionsAlternative, "selected == 0", color: UIColor(hex: 0x93A9D8), width: 5),
                          below: pins)
        style.insertLayer(make(Layer.directionsLine, "selected == 1", color: UIColor(hex: 0x2563EB), width: 6),
                          below: pins)

        let origin = MLNShapeSource(identifier: Layer.directionsOriginSource, shape: nil, options: nil)
        style.addSource(origin)
        let dot = MLNCircleStyleLayer(identifier: Layer.directionsOrigin, source: origin)
        dot.circleColor = NSExpression(forConstantValue: UIColor(hex: 0x2563EB))
        dot.circleRadius = NSExpression(forConstantValue: 8)
        dot.circleStrokeColor = NSExpression(forConstantValue: UIColor.white)
        dot.circleStrokeWidth = NSExpression(forConstantValue: 3)
        style.addLayer(dot)
    }

    func applyDirections(
        _ lines: [DirectionLine], origin: GeoPoint?, refit: Bool, in style: MLNStyle, map: MLNMapView
    ) {
        let lineSource = style.source(withIdentifier: Layer.directionsSource) as? MLNShapeSource
        let originSource = style.source(withIdentifier: Layer.directionsOriginSource) as? MLNShapeSource
        let drawable = lines.filter { $0.coordinates.count >= 2 }
        guard !drawable.isEmpty else {
            lineSource?.shape = nil
            originSource?.shape = nil
            return
        }
        let features = drawable.map { line -> MLNPolylineFeature in
            var coordinates = line.coordinates
            let feature = MLNPolylineFeature(coordinates: &coordinates, count: UInt(coordinates.count))
            feature.attributes = ["selected": line.selected ? 1 : 0]
            return feature
        }
        lineSource?.shape = MLNShapeCollectionFeature(shapes: features)
        if let origin {
            let point = MLNPointFeature()
            point.coordinate = origin.coordinate
            originSource?.shape = point
        }
        guard refit else { return }
        var all = drawable.flatMap(\.coordinates)
        map.setVisibleCoordinates(
            &all, count: UInt(all.count),
            edgePadding: UIEdgeInsets(top: 100, left: 50, bottom: 70, right: 50), animated: true
        )
    }
}
