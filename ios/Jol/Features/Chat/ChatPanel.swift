import SwiftUI

/// Expanded chat card (SSOT §11.1). Empty: the greeting «Начнём путешествие?», input, collapse button. Once a
/// conversation exists: header, the answer chain (full width, SSOT §11.2), the messages, input at the bottom.
struct ChatPanel: View {
    let model: ChatModel
    @Binding var draft: String
    /// Height the card may use while a conversation is on (the map stays visible above it).
    var conversationHeight: CGFloat = 520
    var showsGuestBanner = false
    let onCollapse: () -> Void
    let onSend: () -> Void
    let onRetry: () -> Void
    let onNewChat: () -> Void
    let onOpenRoute: () -> Void
    let onGuestSignIn: () -> Void
    @FocusState private var focused: Bool
    @State private var selectedNode: String?

    private var isActive: Bool { !model.state.isEmpty || model.isOpening || model.openFailed }

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.md) {
            header
            if isActive, !model.state.chainNodes.isEmpty {
                // The answer chain (SSOT §11.2): full card width, under the header, above the messages.
                ChatGraphView(
                    nodes: model.state.chainNodes, brief: model.state.brief ?? ChatBrief(),
                    finished: model.state.isConverged, selected: $selectedNode
                )
                if selectedNode != nil || model.state.isConverged {
                    ChatChainFooter(
                        nodes: model.state.chainNodes, brief: model.state.brief ?? ChatBrief(),
                        theses: model.state.graph, finished: model.state.isConverged, selected: selectedNode,
                        onDeselect: { selectedNode = nil }, onOpenRoute: onOpenRoute
                    )
                }
            }
            if model.isOpening {
                ProgressView()
                    .frame(maxWidth: .infinity, minHeight: 80)
                    .accessibilityIdentifier("chat-opening")
            } else if model.openFailed {
                Text("Couldn't open this chat.")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.danger)
                    .accessibilityIdentifier("chat-open-failed")
            } else if isActive {
                ChatTranscriptView(
                    model: model, onRetry: onRetry, onNewChat: onNewChat,
                    onGuestSignIn: onGuestSignIn, showsGuestBanner: showsGuestBanner
                )
            }
            inputBar
        }
        .padding(JolSpacing.lg)
        .frame(maxHeight: isActive ? conversationHeight : nil)
        // Solid, not translucent: map clusters must not shine through the text.
        .background(JolColor.surfaceElevated, in: RoundedRectangle(cornerRadius: JolRadius.xl))
        .shadow(color: .black.opacity(0.18), radius: 16, y: 6)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("chat-panel")
    }

    private var header: some View {
        HStack(alignment: .top) {
            if isActive {
                Text(verbatim: "Jol")
                    .font(JolFont.title)
                    .foregroundStyle(JolColor.textPrimary)
                    .accessibilityIdentifier("chat-title")
            } else {
                Text("Shall we start the journey?")
                    .font(JolFont.largeTitle)
                    .foregroundStyle(JolColor.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("chat-greeting")
            }
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
    }

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: JolSpacing.sm) {
            TextField(isActive ? "Message" : "Where do you want to go?", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .focused($focused)
                .submitLabel(.send)
                .onSubmit(submit)
                .accessibilityIdentifier("chat-input")
            Button(action: submit) {
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
    }

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !model.isStreaming && !model.isOpening
    }

    private func submit() {
        guard canSend else { return }
        focused = false
        onSend()
    }
}

/// Collapsed chat: a compact bar next to the profile button; tapping it expands the chat. While an answer is being
/// written the bar shows a typing indicator, so a collapsed chat visibly keeps working.
struct CollapsedChatBar: View {
    let draft: String
    var isTyping = false
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
                if isTyping {
                    TypingDots().accessibilityIdentifier("chat-collapsed-typing")
                }
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

enum BriefFormatting {
    static func day(_ iso: String?) -> Date? {
        guard let iso else { return nil }
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "Asia/Almaty")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: iso)
    }

    /// «5–8 дек.» / «5 – 8 Dec»; a single known date alone; nil when neither is known.
    static func dates(start: String?, end: String?, locale: Locale) -> String? {
        let style = Date.FormatStyle(timeZone: TimeZone(identifier: "Asia/Almaty") ?? .current)
            .day().month(.abbreviated).locale(locale)
        switch (day(start), day(end)) {
        case let (from?, to?):
            return from == to ? from.formatted(style) : "\(from.formatted(style)) – \(to.formatted(style))"
        case let (from?, nil): return from.formatted(style)
        case let (nil, to?): return to.formatted(style)
        default: return nil
        }
    }

    static func budget(_ kzt: Int, locale: Locale) -> String {
        "\(kzt.formatted(.number.locale(locale))) ₸"
    }
}
