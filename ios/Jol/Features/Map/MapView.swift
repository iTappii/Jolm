import CoreLocation
import MapLibre
import SwiftUI

/// SwiftUI wrapper over MLNMapView. The style is loaded by URL; on top of it the view draws the places
/// layer (clustered GeoJSON source, category pins) and an optional curated route (line + numbered stops).
struct MapView: UIViewRepresentable {
    let styleURL: URL
    var pins: [PlaceSummary] = []
    var pinsVersion = 0
    var routeStops: [PlaceSummary] = []
    var routeID: UUID?
    var selectedID: UUID?
    /// Height of what covers the bottom of the map (card, route bar): the camera keeps the target above it.
    var bottomInset: CGFloat = 0
    var onRegionChange: (GeoBounds) -> Void = { _ in }
    var onSelect: (UUID) -> Void = { _ in }
    var onTapEmpty: () -> Void = {}

    func makeCoordinator() -> MapCoordinator { MapCoordinator() }

    func makeUIView(context: Context) -> MLNMapView {
        let map = MLNMapView(frame: .zero, styleURL: styleURL)
        map.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        map.setCenter(AlmatyCamera.center, zoomLevel: AlmatyCamera.zoom, animated: false)
        map.showsUserLocation = true
        map.logoView.isHidden = false
        map.attributionButton.isHidden = false
        map.delegate = context.coordinator
        context.coordinator.attach(to: map)
        context.coordinator.requestLocationPermission()
        return map
    }

    func updateUIView(_ map: MLNMapView, context: Context) {
        let coordinator = context.coordinator
        coordinator.parent = self
        if map.styleURL != styleURL {
            coordinator.styleWillChange()
            map.styleURL = styleURL
        }
        coordinator.apply(to: map)
    }
}

/// Owns everything MapLibre-specific: style layers, tap handling, camera moves.
@MainActor
final class MapCoordinator: NSObject, @preconcurrency MLNMapViewDelegate, CLLocationManagerDelegate {
    enum Layer {
        static let placesSource = "jol-pins"
        static let cluster = "jol-places-cluster"
        static let clusterCount = "jol-places-cluster-count"
        static let selection = "jol-places-selection"
        static let pin = "jol-places-pin"
        static let routeSource = "jol-route"
        static let routeStopsSource = "jol-route-stops"
        static let routeLine = "jol-route-line"
        static let routeStop = "jol-route-stop"
        static let routeStopNumber = "jol-route-stop-number"
    }

    var parent: MapView?
    private let locationManager = CLLocationManager()
    private weak var map: MLNMapView?
    private var styleReady = false
    private var appliedPinsVersion = -1
    private var appliedRouteID: UUID?
    private var appliedSelection: UUID?
    private var appliedInset: CGFloat = 0

    func attach(to map: MLNMapView) {
        self.map = map
        let tap = UITapGestureRecognizer(target: self, action: #selector(handleTap(_:)))
        for recognizer in map.gestureRecognizers ?? [] where recognizer is UITapGestureRecognizer {
            tap.require(toFail: recognizer)
        }
        map.addGestureRecognizer(tap)
    }

    func requestLocationPermission() {
        locationManager.delegate = self
        if locationManager.authorizationStatus == .notDetermined {
            locationManager.requestWhenInUseAuthorization()
        }
    }

    func styleWillChange() {
        styleReady = false
    }

    // MARK: - MLNMapViewDelegate

    func mapView(_ mapView: MLNMapView, didFinishLoading style: MLNStyle) {
        installLayers(in: style)
        styleReady = true
        appliedPinsVersion = -1
        appliedRouteID = nil
        apply(to: mapView)
        reportRegion(mapView)
    }

    func mapView(_ mapView: MLNMapView, regionDidChangeAnimated animated: Bool) {
        reportRegion(mapView)
    }

    private func reportRegion(_ map: MLNMapView) {
        let bounds = map.visibleCoordinateBounds
        parent?.onRegionChange(GeoBounds(
            west: bounds.sw.longitude, south: bounds.sw.latitude, east: bounds.ne.longitude, north: bounds.ne.latitude
        ))
    }

    // MARK: - Layers

    private func installLayers(in style: MLNStyle) {
        // The Jol styles (maps/style) ship empty `jol-places` / `jol-route` GeoJSON sources with plain layers.
        // The route line is reused as is; the places source is replaced by a clustered one (cluster options
        // cannot be changed on an existing source), so the style's own places layers go away.
        // Everything is removed first because didFinishLoading may fire again for the same style object.
        for id in [Layer.routeStopNumber, Layer.routeStop, Layer.routeLine, Layer.pin, Layer.selection,
                   Layer.clusterCount, Layer.cluster, "jol-places-circle", "jol-places-label"] {
            if let layer = style.layer(withIdentifier: id) { style.removeLayer(layer) }
        }
        for id in [Layer.routeStopsSource, Layer.placesSource, "jol-places"] {
            if let source = style.source(withIdentifier: id) { style.removeSource(source) }
        }
        for entry in PlaceCategoryStyle.allImages {
            style.setImage(entry.style.pinImage(), forName: entry.name)
        }

        let places = MLNShapeSource(identifier: Layer.placesSource, shape: nil, options: [
            .clustered: true,
            .clusterRadius: 44,
            .maximumZoomLevelForClustering: 15,
        ])
        style.addSource(places)

        let clusters = MLNCircleStyleLayer(identifier: Layer.cluster, source: places)
        clusters.predicate = NSPredicate(format: "cluster == YES")
        clusters.circleColor = NSExpression(forConstantValue: JolColor.brandUIColor)
        clusters.circleRadius = NSExpression(forConstantValue: 18)
        clusters.circleStrokeColor = NSExpression(forConstantValue: UIColor.white)
        clusters.circleStrokeWidth = NSExpression(forConstantValue: 2)
        style.addLayer(clusters)

        let counts = MLNSymbolStyleLayer(identifier: Layer.clusterCount, source: places)
        counts.predicate = NSPredicate(format: "cluster == YES")
        counts.text = NSExpression(format: "CAST(point_count, 'NSString')")
        counts.textColor = NSExpression(forConstantValue: UIColor.black)
        counts.textFontSize = NSExpression(forConstantValue: 13)
        counts.textFontNames = NSExpression(forConstantValue: ["Noto Sans Bold"])
        counts.textAllowsOverlap = NSExpression(forConstantValue: true)
        style.addLayer(counts)

        let selection = MLNCircleStyleLayer(identifier: Layer.selection, source: places)
        selection.predicate = NSPredicate(format: "id == %@", "")
        selection.circleColor = NSExpression(forConstantValue: JolColor.brandUIColor.withAlphaComponent(0.25))
        selection.circleRadius = NSExpression(forConstantValue: 24)
        selection.circleStrokeColor = NSExpression(forConstantValue: JolColor.brandUIColor)
        selection.circleStrokeWidth = NSExpression(forConstantValue: 2)
        style.addLayer(selection)

        let pins = MLNSymbolStyleLayer(identifier: Layer.pin, source: places)
        pins.predicate = NSPredicate(format: "cluster != YES")
        pins.iconImageName = NSExpression(forKeyPath: "icon")
        pins.iconAllowsOverlap = NSExpression(forConstantValue: true)
        style.addLayer(pins)

        installRouteLayers(in: style)
    }

    private func installRouteLayers(in style: MLNStyle) {
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

    // MARK: - Applying SwiftUI state

    func apply(to map: MLNMapView) {
        guard styleReady, let style = map.style, let parent else { return }

        if appliedPinsVersion != parent.pinsVersion, let source = style.source(withIdentifier: Layer.placesSource)
            as? MLNShapeSource {
            appliedPinsVersion = parent.pinsVersion
            source.shape = MLNShapeCollectionFeature(shapes: parent.pins.map(Self.feature))
        }

        if appliedRouteID != parent.routeID {
            appliedRouteID = parent.routeID
            applyRoute(parent.routeStops, in: style, map: map)
        }

        if appliedSelection != parent.selectedID {
            appliedSelection = parent.selectedID
            if let layer = style.layer(withIdentifier: Layer.selection) as? MLNCircleStyleLayer {
                layer.predicate = NSPredicate(format: "id == %@", parent.selectedID?.uuidString.lowercased() ?? "")
            }
            if let id = parent.selectedID,
               let target = (parent.routeStops + parent.pins).first(where: { $0.id == id }) {
                map.setCenter(target.coordinate, animated: true)
            }
        }

        if appliedInset != parent.bottomInset {
            appliedInset = parent.bottomInset
            map.setContentInset(
                UIEdgeInsets(top: 0, left: 0, bottom: parent.bottomInset, right: 0),
                animated: true, completionHandler: nil
            )
        }
    }

    private static func feature(_ place: PlaceSummary) -> MLNPointFeature {
        let feature = MLNPointFeature()
        feature.coordinate = place.coordinate
        feature.attributes = [
            "id": place.id.uuidString.lowercased(),
            "name": place.name,
            "icon": PlaceCategoryStyle.imageName(for: place.category),
        ]
        return feature
    }

    private func applyRoute(_ stops: [PlaceSummary], in style: MLNStyle, map: MLNMapView) {
        let lineSource = style.source(withIdentifier: Layer.routeSource) as? MLNShapeSource
        let stopSource = style.source(withIdentifier: Layer.routeStopsSource) as? MLNShapeSource
        guard !stops.isEmpty else {
            lineSource?.shape = nil
            stopSource?.shape = nil
            return
        }
        var coordinates = stops.map(\.coordinate)
        lineSource?.shape = MLNPolylineFeature(coordinates: &coordinates, count: UInt(coordinates.count))
        stopSource?.shape = MLNShapeCollectionFeature(shapes: stops.enumerated().map { index, place in
            let feature = MLNPointFeature()
            feature.coordinate = place.coordinate
            feature.attributes = ["id": place.id.uuidString.lowercased(), "number": String(index + 1)]
            return feature
        })
        map.setVisibleCoordinates(
            &coordinates, count: UInt(coordinates.count),
            edgePadding: UIEdgeInsets(top: 90, left: 50, bottom: 220, right: 50), animated: true
        )
    }

    // MARK: - Taps

    @objc private func handleTap(_ gesture: UITapGestureRecognizer) {
        guard let map, gesture.state == .ended else { return }
        let point = gesture.location(in: map)
        let hitBox = CGRect(x: point.x - 22, y: point.y - 22, width: 44, height: 44)
        let layers: Set<String> = [Layer.pin, Layer.cluster, Layer.routeStop]
        let features = map.visibleFeatures(in: hitBox, styleLayerIdentifiers: layers)
        let nearest = features.min { distance($0, point, map) < distance($1, point, map) }

        guard let nearest else {
            parent?.onTapEmpty()
            return
        }
        if let cluster = nearest as? MLNPointFeatureCluster {
            map.setCenter(cluster.coordinate, zoomLevel: min(map.zoomLevel + 2, 17), animated: true)
        } else if let raw = nearest.attribute(forKey: "id") as? String, let id = UUID(uuidString: raw) {
            parent?.onSelect(id)
        }
    }

    private func distance(_ feature: MLNFeature, _ point: CGPoint, _ map: MLNMapView) -> CGFloat {
        let location = map.convert(feature.coordinate, toPointTo: map)
        return hypot(location.x - point.x, location.y - point.y)
    }
}
