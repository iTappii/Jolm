import MapLibre
import UIKit

/// Ordinary place pins (Ш-70): drawn from street zoom only, a venue's logo instead of the category icon once it is
/// loaded, and never under a main sight's drawing or label (Ш-69).
extension MapCoordinator {
    /// Most logos asked for in one pass: a dense street is loaded over a few camera stops, not in one burst.
    private static let logoBatch = 40
    /// Margin around a sight's marker and label inside which an ordinary pin is not drawn, points.
    private static let landmarkClearance: CGFloat = 16

    /// Called when the camera stops, the pins change or the sights do.
    func refreshPins(_ map: MLNMapView) {
        guard styleReady, let style = map.style, let parent else { return }
        let showing = PlacePinVisibility.showsPins(atZoom: map.zoomLevel)
        let visible = showing ? visiblePins(parent.pins, map: map) : []

        let hidden = showing ? hiddenUnderLandmarks(visible, landmarks: parent.landmarks, map: map) : []
        if hidden != appliedHidden {
            appliedHidden = hidden
            if let layer = style.layer(withIdentifier: Layer.pin) as? MLNSymbolStyleLayer {
                layer.predicate = hidden.isEmpty ? nil : NSPredicate(format: "NOT (id IN %@)", hidden)
            }
        }

        loadLogos(for: visible, style: style, map: map)
        #if DEBUG
        reportDebug(map)
        // The symbol layer is laid out a frame or two after the source changes, and the map may not go idle again.
        Task { @MainActor [weak self, weak map] in
            for delay in [0.4, 1.2, 2.5] {
                try? await Task.sleep(for: .seconds(delay))
                guard let self, let map else { return }
                self.reportDebug(map)
            }
        }
        #endif
    }

    /// The sights changed (they come from the server after launch, or hide while a route is drawn).
    func applyLandmarks(_ landmarks: [Landmark], map: MLNMapView) {
        let ids = landmarks.map(\.id)
        guard appliedLandmarkIDs != ids else { return }
        appliedLandmarkIDs = ids
        refreshPins(map)
    }

    private func visiblePins(_ pins: [PlaceSummary], map: MLNMapView) -> [PlaceSummary] {
        let bounds = map.visibleCoordinateBounds
        return pins.filter {
            $0.lat >= bounds.sw.latitude && $0.lat <= bounds.ne.latitude
                && $0.lon >= bounds.sw.longitude && $0.lon <= bounds.ne.longitude
        }
    }

    /// Ids of the pins that sit under a drawn sight: the sight's own place and any pin inside its frame.
    private func hiddenUnderLandmarks(_ pins: [PlaceSummary], landmarks: [Landmark], map: MLNMapView) -> [String] {
        guard !landmarks.isEmpty else { return [] }
        let placed = LandmarkLayout.visible(landmarks, zoom: map.zoomLevel, viewport: map.bounds) {
            map.convert($0, toPointTo: map)
        }
        guard !placed.isEmpty else { return [] }
        let frames = placed.map {
            LandmarkLayout.frame(of: $0.landmark, at: $0.point)
                .insetBy(dx: -Self.landmarkClearance, dy: -Self.landmarkClearance)
        }
        let sights = Set(placed.map(\.landmark.id))
        let hidden = pins.filter { pin in
            sights.contains(pin.id) || frames.contains { $0.contains(map.convert(pin.coordinate, toPointTo: map)) }
        }
        return hidden.map { $0.id.uuidString.lowercased() }.sorted()
    }

    private func loadLogos(for pins: [PlaceSummary], style: MLNStyle, map: MLNMapView) {
        let wanted = pins.filter { $0.logoURL != nil && !logoReady.contains($0.id) && !logoRequested.contains($0.id) }
        for pin in wanted.prefix(Self.logoBatch) {
            guard let url = pin.logoURL else { continue }
            logoRequested.insert(pin.id)
            Task { [weak self, weak map] in
                guard let image = await PlaceLogoStore.shared.pinImage(for: url),
                      let self, let map, let style = map.style, self.styleReady else { return }
                style.setImage(image, forName: "logo-\(pin.id.uuidString.lowercased())")
                self.logoReady.insert(pin.id)
                self.appliedPinsVersion = -1  // redraw the source with the logo as this pin's icon
                self.apply(to: map)
            }
        }
    }

    #if DEBUG
    /// UI tests / screenshots: the stub opens at street zoom (Ш-70, where the fixture pins are drawn; they are hidden
    /// below it); `-JolStartCamera 43.297,68.272,12` (lat,lon,zoom) overrides it (Ш-59).
    static func applyDebugCamera(_ map: MLNMapView) {
        if UITestSupport.isStubbed {
            map.setCenter(Region.current.center, zoomLevel: max(Region.current.zoom, UITestSupport.stubStreetZoom),
                          animated: false)
        }
        if let spec = UserDefaults.standard.string(forKey: "JolStartCamera") {
            let parts = spec.split(separator: ",").compactMap { Double($0) }
            if parts.count == 3 {
                map.setCenter(CLLocationCoordinate2D(latitude: parts[0], longitude: parts[1]),
                              zoomLevel: parts[2], animated: false)
            }
        }
    }
    #endif

    #if DEBUG
    /// The first layout may have reset the camera set before it, so the style's load applies it once more.
    func applyDebugCameraOnce(_ map: MLNMapView) {
        guard !debugCameraApplied else { return }
        debugCameraApplied = true
        Self.applyDebugCamera(map)
    }

    func mapViewDidBecomeIdle(_ mapView: MLNMapView) {
        reportDebug(mapView)
    }

    /// UI tests (`-JolStubAPI`) read what is really drawn: pins in the layer now, logos among them, cluster layers.
    func reportDebug(_ map: MLNMapView) {
        guard UITestSupport.isStubbed, let style = map.style else { return }
        let drawn = map.visibleFeatures(in: map.bounds, styleLayerIdentifiers: [Layer.pin])
        let logos = drawn.filter { ($0.attribute(forKey: "icon") as? String)?.hasPrefix("logo-") == true }
        let clusters = style.layer(withIdentifier: Layer.cluster) == nil ? 0 : 1
        parent?.projection?.debugPins = "pins:\(drawn.count),logos:\(logos.count),clusters:\(clusters)"
    }
    #endif
}
