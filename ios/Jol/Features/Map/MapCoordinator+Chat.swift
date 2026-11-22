import MapLibre
import UIKit

/// The live map behind the chat (Ш-32): every place the assistant names appears as an orange dot that grows in
/// with a short pulse; the camera moves to show them all.
extension MapCoordinator {
    private static let dotRadius: CGFloat = 11
    private static let haloRadius: CGFloat = 26

    func installChatLayers(in style: MLNStyle) {
        let source = MLNShapeSource(identifier: Layer.chatSource, shape: nil, options: nil)
        style.addSource(source)

        let halo = MLNCircleStyleLayer(identifier: Layer.chatHalo, source: source)
        halo.circleColor = NSExpression(forConstantValue: JolColor.brandUIColor.withAlphaComponent(0.28))
        halo.circleRadius = NSExpression(forConstantValue: Self.haloRadius)
        style.addLayer(halo)

        let dot = MLNCircleStyleLayer(identifier: Layer.chatDot, source: source)
        dot.circleColor = NSExpression(forConstantValue: JolColor.brandUIColor)
        dot.circleRadius = NSExpression(forConstantValue: Self.dotRadius)
        dot.circleStrokeColor = NSExpression(forConstantValue: UIColor.white)
        dot.circleStrokeWidth = NSExpression(forConstantValue: 2.5)
        style.addLayer(dot)

        let label = MLNSymbolStyleLayer(identifier: Layer.chatLabel, source: source)
        label.text = NSExpression(forKeyPath: "name")
        label.textFontNames = NSExpression(forConstantValue: ["Noto Sans Bold"])
        label.textFontSize = NSExpression(forConstantValue: 12)
        label.textColor = NSExpression(forConstantValue: UIColor.black)
        label.textHaloColor = NSExpression(forConstantValue: UIColor.white)
        label.textHaloWidth = NSExpression(forConstantValue: 1.5)
        label.textOffset = NSExpression(forConstantValue: NSValue(cgVector: CGVector(dx: 0, dy: 1.4)))
        label.textAnchor = NSExpression(forConstantValue: "top")
        label.textOptional = NSExpression(forConstantValue: true)
        style.addLayer(label)
    }

    func applyChatPlaces(_ places: [MapPlace], in style: MLNStyle, map: MLNMapView) {
        guard let source = style.source(withIdentifier: Layer.chatSource) as? MLNShapeSource,
              let dot = style.layer(withIdentifier: Layer.chatDot) as? MLNCircleStyleLayer,
              let halo = style.layer(withIdentifier: Layer.chatHalo) as? MLNCircleStyleLayer else { return }
        source.shape = MLNShapeCollectionFeature(shapes: places.map { place in
            let feature = MLNPointFeature()
            feature.coordinate = CLLocationCoordinate2D(latitude: place.lat, longitude: place.lon)
            feature.attributes = ["id": place.id.uuidString.lowercased(), "name": place.name]
            return feature
        })
        guard !places.isEmpty else { return }

        // Pop-in: start from nothing, then let MapLibre interpolate the radius up.
        let instant = MLNTransition(duration: 0, delay: 0)
        dot.circleRadiusTransition = instant
        halo.circleRadiusTransition = instant
        dot.circleRadius = NSExpression(forConstantValue: 0)
        halo.circleRadius = NSExpression(forConstantValue: 0)
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(50))
            dot.circleRadiusTransition = MLNTransition(duration: 0.45, delay: 0)
            dot.circleRadius = NSExpression(forConstantValue: Self.dotRadius)
            halo.circleRadiusTransition = MLNTransition(duration: 0.9, delay: 0)
            halo.circleRadius = NSExpression(forConstantValue: Self.haloRadius)
        }

        var coordinates = places.map { CLLocationCoordinate2D(latitude: $0.lat, longitude: $0.lon) }
        map.setVisibleCoordinates(
            &coordinates, count: UInt(coordinates.count),
            edgePadding: UIEdgeInsets(top: 110, left: 60, bottom: 40, right: 60), animated: true
        )
    }
}

/// The live route (Ш-54): the camera follows it as it grows. Its pins and edges are SwiftUI (`LiveRouteOverlay`).
extension MapCoordinator {
    func fitLiveRoute(_ route: LiveRoute?, map: MLNMapView) {
        parent?.projection?.invalidateSoon()
        guard let route, !route.isEmpty else { return }
        var coordinates = route.coordinates
        if case .center(let center, let zoom) = CameraFit.plan(for: coordinates, singleZoom: CameraFit.liveSingleStopZoom) {
            map.setCenter(center, zoomLevel: zoom, animated: true)
            return
        }
        // The maths (padding above the chat card, tighter with the keyboard up) lives in `CameraFit`.
        let padding = CameraFit.liveRoutePadding(
            mapHeight: map.bounds.height, targetInset: parent?.bottomInset ?? 0, currentInset: map.contentInset.bottom)
        map.setVisibleCoordinates(&coordinates, count: UInt(coordinates.count), edgePadding: padding, animated: true)
    }
}

extension MapCoordinator {
    func mapView(_ mapView: MLNMapView, regionIsChangingWith reason: MLNCameraChangeReason) {
        parent?.projection?.invalidate()
    }

    func mapView(_ mapView: MLNMapView, regionDidChangeWith reason: MLNCameraChangeReason, animated: Bool) {
        parent?.projection?.invalidate()
        reportRegion(mapView)
    }

    func applyLiveRoute(_ parent: MapView, map: MLNMapView) {
        parent.projection?.map = map
        // Refit when the route changes, and when the space under it does (keyboard, chat collapsed or expanded).
        let insetChanged = parent.liveRoute != nil && liveFit.inset != parent.bottomInset
        guard liveFit.route != parent.liveRoute || insetChanged else { return }
        liveFit = LiveRouteFit(route: parent.liveRoute, inset: parent.bottomInset)
        fitLiveRoute(parent.liveRoute, map: map)
    }
}

/// What the camera was last fitted to for the live route: the route and the map's bottom inset at that moment.
struct LiveRouteFit {
    var route: LiveRoute?
    var inset: CGFloat = -1
}
