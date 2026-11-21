import SwiftUI

/// Stub for a feature screen that is not built yet.
struct PlaceholderScreen: View {
    let title: LocalizedStringKey
    let systemImage: String

    var body: some View {
        VStack(spacing: JolSpacing.md) {
            Image(systemName: systemImage)
                .font(.system(size: 40))
                .foregroundStyle(JolColor.brand)
            Text(title)
                .font(JolFont.title)
                .foregroundStyle(JolColor.textPrimary)
            Text("Coming soon")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JolColor.background)
    }
}
