import SwiftUI
import UIKit

/// Design tokens: colors. Light/dark variants come from dynamic `UIColor`s (follow the system appearance).
enum JolColor {
    static let brandHex: UInt32 = 0xFF7A00

    /// Brand orange `#FF7A00` (same in both themes).
    static let brand = Color(brandUIColor)
    static let brandUIColor = UIColor(hex: brandHex)

    /// Text/icons on a brand-filled surface.
    static let onBrand = Color.black

    static let background = dynamic(light: 0xFFFFFF, dark: 0x000000)
    static let surface = dynamic(light: 0xF5F5F7, dark: 0x1C1C1E)
    static let surfaceElevated = dynamic(light: 0xFFFFFF, dark: 0x2C2C2E)
    static let separator = dynamic(light: 0xE5E5EA, dark: 0x3A3A3C)
    static let textPrimary = dynamic(light: 0x000000, dark: 0xFFFFFF)
    static let textSecondary = dynamic(light: 0x6C6C70, dark: 0xA1A1A6)
    static let textTertiary = dynamic(light: 0x9A9AA0, dark: 0x6C6C70)
    static let danger = dynamic(light: 0xD93025, dark: 0xFF6B60)

    static func dynamic(light: UInt32, dark: UInt32) -> Color {
        Color(UIColor { traits in
            UIColor(hex: traits.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
    }
}
