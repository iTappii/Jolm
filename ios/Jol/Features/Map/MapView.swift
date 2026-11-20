import CoreLocation
import MapLibre
import SwiftUI

/// SwiftUI wrapper over MLNMapView. The style is loaded by URL.
struct MapView: UIViewRepresentable {
    let styleURL: URL

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> MLNMapView {
        let map = MLNMapView(frame: .zero, styleURL: styleURL)
        map.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        map.setCenter(AlmatyCamera.center, zoomLevel: AlmatyCamera.zoom, animated: false)
        map.showsUserLocation = true
        map.logoView.isHidden = false
        map.attributionButton.isHidden = false
        map.delegate = context.coordinator
        context.coordinator.requestLocationPermission()
        return map
    }

    func updateUIView(_ map: MLNMapView, context: Context) {
        if map.styleURL != styleURL {
            map.styleURL = styleURL
        }
    }

    final class Coordinator: NSObject, MLNMapViewDelegate, CLLocationManagerDelegate {
        private let locationManager = CLLocationManager()

        func requestLocationPermission() {
            locationManager.delegate = self
            if locationManager.authorizationStatus == .notDetermined {
                locationManager.requestWhenInUseAuthorization()
            }
        }
    }
}
