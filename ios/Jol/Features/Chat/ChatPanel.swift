import SwiftUI

/// Expanded chat card: greeting, input, collapse button (top-right). The real chat arrives with Ш-32; until then
/// sending only passes the registration gate (Ш-28) and the text stays in the field.
struct ChatPanel: View {
    @Binding var draft: String
    var savedNote = false
    let onCollapse: () -> Void
    let onSend: () -> Void
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
            HStack(alignment: .bottom, spacing: JolSpacing.sm) {
                TextField("Where do you want to go?", text: $draft, axis: .vertical)
                    .lineLimit(1...4)
                    .focused($focused)
                    .submitLabel(.send)
                    .onSubmit(onSend)
                    .accessibilityIdentifier("chat-input")
                Button(action: onSend) {
                    Image(systemName: "arrow.up")
                        .font(.body.weight(.bold))
                        .frame(width: 32, height: 32)
                        .background(JolColor.brand.opacity(canSend ? 1 : 0.35), in: Circle())
                        .foregroundStyle(JolColor.onBrand)
                }
                .buttonStyle(.plain)
                .disabled(!canSend)
                .accessibilityLabel(Text("Send"))
                .accessibilityIdentifier("chat-send")
            }
            .padding(JolSpacing.md)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            if savedNote {
                Text("The chat is coming soon. Your message is saved.")
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityIdentifier("chat-saved-note")
            }
        }
        .padding(JolSpacing.lg)
        .background(JolColor.surfaceElevated, in: RoundedRectangle(cornerRadius: JolRadius.xl))
        .shadow(color: .black.opacity(0.18), radius: 16, y: 6)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("chat-panel")
    }

    private var canSend: Bool { !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
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
