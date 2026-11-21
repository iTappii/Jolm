import SwiftUI

/// Stack that lays its content out in a row, and in a column at accessibility Dynamic Type sizes, so wide rows
/// (title + price, label + button) wrap instead of squeezing the text.
struct AdaptiveStack<Content: View>: View {
    @Environment(\.dynamicTypeSize) private var typeSize
    var spacing: CGFloat = JolSpacing.sm
    var rowAlignment: VerticalAlignment = .center
    var columnAlignment: HorizontalAlignment = .leading
    @ViewBuilder var content: Content

    var body: some View {
        let layout = typeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: columnAlignment, spacing: spacing))
            : AnyLayout(HStackLayout(alignment: rowAlignment, spacing: spacing))
        layout { content }
    }
}

/// Minimum size of a tap target (Apple HIG).
enum JolTarget {
    static let minimum: CGFloat = 44
}

extension Text {
    /// Joins pieces into one VoiceOver phrase, separated by commas (`Text` has `+` but no `+=`).
    static func spoken(_ parts: [Text]) -> Text {
        guard let first = parts.first else { return Text(verbatim: "") }
        return parts.dropFirst().reduce(first) { $0 + Text(verbatim: ", ") + $1 }
    }
}
