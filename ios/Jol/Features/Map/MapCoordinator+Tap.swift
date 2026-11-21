import CoreLocation
import MapLibre
import UIKit

extension MapCoordinator.Layer {
    static let tapSource = "jol-tap"
    static let tapHalo = "jol-tap-halo"
    static let tapDot = "jol-tap-dot"
}

/// The point the person tapped that is not a place of ours (Ш-23c): a ring with a dot under the card, so it is clear
/// what the address on the card belongs to.
extension MapCoordinator {
    func installTapLayers(in style: MLNStyle) {
        let source = MLNShapeSource(identifier: Layer.tapSource, shape: nil, options: nil)
        style.addSource(source)

        let halo = MLNCircleStyleLayer(identifier: Layer.tapHalo, source: source)
        halo.circleColor = NSExpression(forConstantValue: JolColor.brandUIColor.withAlphaComponent(0.25))
        halo.circleRadius = NSExpression(forConstantValue: 20)
        style.addLayer(halo)

        let dot = MLNCircleStyleLayer(identifier: Layer.tapDot, source: source)
        dot.circleColor = NSExpression(forConstantValue: JolColor.brandUIColor)
        dot.circleRadius = NSExpression(forConstantValue: 7)
        dot.circleStrokeColor = NSExpression(forConstantValue: UIColor.white)
        dot.circleStrokeWidth = NSExpression(forConstantValue: 2.5)
        style.addLayer(dot)
    }

    func removeTapLayers(from style: MLNStyle) {
        for id in [Layer.tapDot, Layer.tapHalo] {
            if let layer = style.layer(withIdentifier: id) { style.removeLayer(layer) }
        }
        if let source = style.source(withIdentifier: Layer.tapSource) { style.removeSource(source) }
    }

    func applyMarker(_ point: GeoPoint?, in style: MLNStyle, map: MLNMapView) {
        guard let source = style.source(withIdentifier: Layer.tapSource) as? MLNShapeSource else { return }
        guard let point else {
            source.shape = nil
            return
        }
        let feature = MLNPointFeature()
        feature.coordinate = point.coordinate
        source.shape = feature
        map.setCenter(point.coordinate, animated: true)
    }
}
