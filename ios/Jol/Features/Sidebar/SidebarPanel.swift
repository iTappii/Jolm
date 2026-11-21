import SwiftUI

/// Side panel (SSOT §11.4): recent chats and "New chat". Opens by edge swipe or `isOpen = true`,
/// closes by tapping outside, swiping left, or the close button.
struct SidebarPanel: View {
    @Binding var isOpen: Bool
    let onNewChat: () -> Void
    var onOpenRoutes: () -> Void = {}
    private let width: CGFloat = 300

    var body: some View {
        ZStack(alignment: .leading) {
            if isOpen {
                Color.black.opacity(0.35)
                    .ignoresSafeArea()
                    .onTapGesture { isOpen = false }
                    .accessibilityIdentifier("sidebar-scrim")
                    .accessibilityLabel(Text("Close"))
                    .accessibilityAddTraits(.isButton)
                    .transition(.opacity)
                panel
                    .transition(.move(edge: .leading))
            }
        }
        .animation(.snappy(duration: 0.3), value: isOpen)
    }

    private var panel: some View {
        VStack(alignment: .leading, spacing: JolSpacing.lg) {
            HStack {
                Text("Recent chats")
                    .font(JolFont.title)
                    .foregroundStyle(JolColor.textPrimary)
                    .accessibilityAddTraits(.isHeader)
                Spacer()
                Button { isOpen = false } label: {
                    Image(systemName: "xmark")
                        .font(.body.weight(.semibold))
                        .frame(width: 36, height: 36)
                        .background(JolColor.surface, in: Circle())
                        .foregroundStyle(JolColor.textPrimary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text("Close"))
                .accessibilityIdentifier("sidebar-close")
            }
            Button {
                onNewChat()
                isOpen = false
            } label: {
                Label("New chat", systemImage: "square.and.pencil")
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.onBrand)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, JolSpacing.md)
                    .background(JolColor.brand, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("sidebar-new-chat")
            Button {
                onOpenRoutes()
                isOpen = false
            } label: {
                Label("Ready-made routes", systemImage: "point.topleft.down.curvedto.point.bottomright.up")
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, JolSpacing.md)
                    .padding(.horizontal, JolSpacing.md)
                    .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("sidebar-routes")
            Text("No chats yet")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("sidebar-empty")
            Spacer()
        }
        .padding(JolSpacing.lg)
        .padding(.top, JolSpacing.xl)
        .frame(width: width)
        .frame(maxHeight: .infinity)
        .background(JolColor.surfaceElevated.ignoresSafeArea())
        .gesture(
            DragGesture(minimumDistance: 20)
                .onEnded { value in
                    if value.translation.width < -40 { isOpen = false }
                }
        )
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("sidebar-panel")
    }
}
