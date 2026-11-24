import CoreLocation
import SwiftUI
import UIKit

/// Which main sights are on the screen and where (Ш-69): the zoom rule, the viewport, and a greedy collision pass so
/// markers and their labels never overlap (the more important sight, the lower `rank`, keeps its place).
enum LandmarkLayout {
    static let markerSize: CGFloat = 34
    static let labelGap: CGFloat = 2
    static let labelHeight: CGFloat = 20
    static let maxLabelWidth: CGFloat = 120
    /// A little outside the screen still counts as visible: a marker slides in rather than pops in.
    static let viewportMargin: CGFloat = 40

    struct Placed: Equatable {
        let landmark: Landmark
        let point: CGPoint
    }

    /// Estimated label width (the real text is not measured: the overlay caps its own width the same way).
    static func labelWidth(for name: String) -> CGFloat {
        min(maxLabelWidth, 14 + CGFloat(name.count) * 6.5)
    }

    /// The marker plus its label below, as one rectangle.
    static func frame(of landmark: Landmark, at point: CGPoint) -> CGRect {
        let width = max(markerSize, labelWidth(for: landmark.name))
        return CGRect(
            x: point.x - width / 2, y: point.y - markerSize / 2,
            width: width, height: markerSize + labelGap + labelHeight
        )
    }

    static func visible(
        _ landmarks: [Landmark], zoom: Double, viewport: CGRect, blockers: [CGRect] = [],
        point: (CLLocationCoordinate2D) -> CGPoint?
    ) -> [Placed] {
        let area = viewport.insetBy(dx: -viewportMargin, dy: -viewportMargin)
        let ordered = landmarks.sorted {
            ($0.rank, $0.minZoom, $0.name) < ($1.rank, $1.minZoom, $1.name)
        }
        var taken = blockers
        var result: [Placed] = []
        for landmark in ordered where landmark.isVisible(atZoom: zoom) {
            guard let position = point(landmark.coordinate), area.contains(position) else { continue }
            let rect = frame(of: landmark, at: position)
            if taken.contains(where: { $0.intersects(rect) }) { continue }
            taken.append(rect)
            result.append(Placed(landmark: landmark, point: position))
        }
        return result
    }
}

/// The line drawings of the sights (Ш-69): one original vector per key, in the asset catalog as template images
/// (sources: `Resources/Landmarks/*.svg`).
enum LandmarkIcon {
    static let keys: Set<String> = [
        "mosque", "cathedral", "tv_tower", "skating_rink", "ski_cable_car", "bazaar", "park", "museum", "monument",
        "mausoleum", "canyon", "mountain_lake", "ferris_wheel", "theatre", "stadium", "square",
    ]

    /// Asset name for a server key, `nil` for an unknown or missing one (the category pin is drawn instead).
    static func assetName(for key: String?) -> String? {
        guard let key, keys.contains(key) else { return nil }
        return "landmark-\(key)"
    }
}

/// Colours of the drawings and labels: the map style's muted label colours (`maps/style/build_styles.py`).
enum LandmarkPalette {
    static let drawing = Color(UIColor {
        $0.userInterfaceStyle == .dark ? UIColor(hex: 0xA39E94) : UIColor(hex: 0x6E685D)
    })
    static let label = Color(UIColor {
        $0.userInterfaceStyle == .dark ? UIColor(hex: 0xECE8E0) : UIColor(hex: 0x2B2926)
    })
    static let halo = Color(UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: 0x17181B) : .white })
}
