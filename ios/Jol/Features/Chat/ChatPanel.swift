import SwiftUI

/// Expanded chat card: greeting, input, collapse button (top-right). Sending arrives with Ш-32:
/// for now the field only keeps the text.
struct ChatPanel: View {
    @Binding var draft: String
    let onCollapse: () -> Void
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.lg) {
            HStack(alignment: .top) {
                Text("Shall we start the journey?")
                    .font(JolFont.largeTitle)
                    .foregroundStyle(JolColor.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("chat-greeting")
                Spacer(minLength: JolSpacing.sm)
                Button(action: onCollapse) {
                    Image(systemName: "chevron.down")
                        .font(.body.weight(.semibold))
                        .frame(width: 36, height: 36)
                        .background(JolColor.surface, in: Circle())
                        .foregroundStyle(JolColor.textPrimary)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(Text("Collapse chat"))
                .accessibilityIdentifier("chat-collapse")
            }
            TextField("Where do you want to go?", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .focused($focused)
                .padding(JolSpacing.md)
                .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                .accessibilityIdentifier("chat-input")
        }
        .padding(JolSpacing.lg)
        .background(JolColor.surfaceElevated, in: RoundedRectangle(cornerRadius: JolRadius.xl))
        .shadow(color: .black.opacity(0.18), radius: 16, y: 6)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("chat-panel")
    }
}

/// Collapsed chat: a compact bar next to the profile button; tapping it expands the chat.
struct CollapsedChatBar: View {
    let draft: String
    let onExpand: () -> Void

    var body: some View {
        Button(action: onExpand) {
            HStack {
                if draft.isEmpty {
                    Text("Shall we start the journey?")
                        .foregroundStyle(JolColor.textSecondary)
                } else {
                    Text(verbatim: draft)
                        .foregroundStyle(JolColor.textPrimary)
                }
                Spacer(minLength: JolSpacing.sm)
                Image(systemName: "chevron.up")
                    .font(.body.weight(.semibold))
                    .foregroundStyle(JolColor.textPrimary)
            }
            .lineLimit(1)
            .padding(.horizontal, JolSpacing.lg)
            .frame(maxWidth: .infinity)
            .frame(height: 48)
            .background(.thinMaterial, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text("Expand chat"))
        .accessibilityIdentifier("chat-collapsed-bar")
    }
}
