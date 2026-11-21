import SwiftUI
import UIKit

/// Visual style of a place category: SF Symbol + group color. The map style (`maps/style`) has no sprite
/// with category icons, so pin images are rendered from SF Symbols at runtime and registered with
/// `MLNStyle.setImage(_:forName:)`.
struct PlaceCategoryStyle: Equatable {
    let symbol: String
    let colorHex: UInt32

    static let fallback = PlaceCategoryStyle(symbol: "mappin", colorHex: JolColor.brandHex)

    private static let sights: UInt32 = 0xE8590C
    private static let culture: UInt32 = 0x7048E8
    private static let nature: UInt32 = 0x2F9E44
    private static let shopping: UInt32 = 0x1C7ED6
    private static let food: UInt32 = 0xD6336C
    private static let stay: UInt32 = 0x0C8599

    /// Leaf slugs from `GET /v1/categories` (migration 0002). Unknown slugs fall back by prefix, then `fallback`.
    static let bySlug: [String: PlaceCategoryStyle] = [
        "landmark": .init(symbol: "building.columns", colorHex: sights),
        "monument": .init(symbol: "flag", colorHex: sights),
        "historic": .init(symbol: "building.columns", colorHex: sights),
        "religious": .init(symbol: "sparkle", colorHex: sights),
        "museum": .init(symbol: "building.columns", colorHex: culture),
        "gallery": .init(symbol: "paintpalette", colorHex: culture),
        "theatre": .init(symbol: "theatermasks", colorHex: culture),
        "entertainment": .init(symbol: "ticket", colorHex: culture),
        "amusement": .init(symbol: "sparkles", colorHex: culture),
        "spa": .init(symbol: "drop", colorHex: culture),
        "park": .init(symbol: "tree", colorHex: nature),
        "garden": .init(symbol: "leaf", colorHex: nature),
        "mountain": .init(symbol: "mountain.2", colorHex: nature),
        "viewpoint": .init(symbol: "binoculars", colorHex: nature),
        "lake": .init(symbol: "drop", colorHex: nature),
        "ski": .init(symbol: "figure.skiing.downhill", colorHex: nature),
        "market": .init(symbol: "cart", colorHex: shopping),
        "mall": .init(symbol: "bag", colorHex: shopping),
        "restaurant": .init(symbol: "fork.knife", colorHex: food),
        "coffee": .init(symbol: "cup.and.saucer", colorHex: food),
        "bakery": .init(symbol: "birthday.cake", colorHex: food),
        "bar": .init(symbol: "wineglass", colorHex: food),
        "nightclub": .init(symbol: "music.note", colorHex: food),
        "hotel": .init(symbol: "bed.double", colorHex: stay),
        "hostel": .init(symbol: "bed.double", colorHex: stay),
        "guest_house": .init(symbol: "house", colorHex: stay),
    ]

    static func style(for slug: String?) -> PlaceCategoryStyle {
        guard let slug else { return fallback }
        if let style = bySlug[slug] { return style }
        if slug.hasPrefix("cafe_") { return .init(symbol: "fork.knife", colorHex: food) }
        return fallback
    }

    /// Name of the style image for a category slug.
    static func imageName(for slug: String?) -> String {
        guard let slug, bySlug[slug] != nil || slug.hasPrefix("cafe_") else { return "pin-default" }
        return "pin-\(slug.hasPrefix("cafe_") ? "cafe" : slug)"
    }

    /// Every (image name, style) pair the map needs registered.
    static var allImages: [(name: String, style: PlaceCategoryStyle)] {
        var images: [(String, PlaceCategoryStyle)] = [
            ("pin-default", fallback), ("pin-cafe", style(for: "cafe_oriental")),
        ]
        for (slug, style) in bySlug { images.append(("pin-\(slug)", style)) }
        return images
    }

    var color: Color { Color(UIColor(hex: colorHex)) }

    /// Round pin: colored disc, white ring, white symbol.
    func pinImage(diameter: CGFloat = 30) -> UIImage {
        let size = CGSize(width: diameter, height: diameter)
        return UIGraphicsImageRenderer(size: size).image { _ in
            let rect = CGRect(origin: .zero, size: size).insetBy(dx: 1.5, dy: 1.5)
            UIColor(hex: colorHex).setFill()
            UIBezierPath(ovalIn: rect).fill()
            UIColor.white.setStroke()
            let ring = UIBezierPath(ovalIn: rect)
            ring.lineWidth = 2
            ring.stroke()
            let configuration = UIImage.SymbolConfiguration(pointSize: diameter * 0.42, weight: .semibold)
            let glyph = (UIImage(systemName: symbol, withConfiguration: configuration)
                ?? UIImage(systemName: "mappin", withConfiguration: configuration))?
                .withTintColor(.white, renderingMode: .alwaysOriginal)
            if let glyph {
                let origin = CGPoint(x: (size.width - glyph.size.width) / 2, y: (size.height - glyph.size.height) / 2)
                glyph.draw(at: origin)
            }
        }
    }
}
