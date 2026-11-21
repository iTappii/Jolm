import SwiftUI

/// Accessibility helpers (Ш-52): colours that keep their contrast in both themes, and the 44 pt tap target
/// (`AdaptiveStack` lives in AdaptiveLayout.swift).
extension JolColor {
    /// The brand orange as TEXT or a thin icon on a light/dark surface: `#FF7A00` on white is only 2.7:1, this is 5:1
    /// in light and the plain brand in dark (8:1 on black). Fills keep `brand` (black text on it is 8:1).
    static let brandText = dynamic(light: 0xB35400, dark: 0xFF7A00)
    /// "Open now": system green on white is 2.4:1.
    static let statusOpen = dynamic(light: 0x1E7B34, dark: 0x30D158)
}

extension View {
    /// At least 44 × 44 pt to hit, whatever the content looks like (HIG).
    func minTapTarget() -> some View {
        frame(minWidth: 44, minHeight: 44).contentShape(Rectangle())
    }
}
