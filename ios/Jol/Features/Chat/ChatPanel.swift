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
    @Environment(\.dynamicTypeSize) private var typeSize
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
                    .accessibilityLabel(Text("Loading"))
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
                // The field keeps the keyboard after sending; a tap on the conversation puts it away, like in a
                // messenger (buttons in the messages still get their taps).
                .simultaneousGesture(TapGesture().onEnded { focused = false })
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
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("chat-title")
            } else {
                Text("Shall we start the journey?")
                    .font(JolFont.largeTitle)
                    .foregroundStyle(JolColor.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("chat-greeting")
            }
            Spacer(minLength: JolSpacing.sm)
            Button(action: onCollapse) {
                Image(systemName: "chevron.down")
                    .font(.body.weight(.semibold))
                    .dynamicTypeSize(...DynamicTypeSize.xxxLarge) // the icon sits in a fixed circle
                    .frame(width: 36, height: 36)
                    .background(JolColor.surface, in: Circle())
                    .foregroundStyle(JolColor.textPrimary)
                    .minTapTarget()
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Collapse chat"))
            .accessibilityHint(Text("Hides the chat and shows the map"))
            .accessibilityIdentifier("chat-collapse")
        }
    }

    private var inputBar: some View {
        // At accessibility sizes the field takes the whole row and «send» goes under it, so the prompt is not cut.
        let layout = typeSize.isAccessibilitySize
            ? AnyLayout(VStackLayout(alignment: .trailing, spacing: JolSpacing.xs))
            : AnyLayout(HStackLayout(alignment: .bottom, spacing: JolSpacing.sm))
        return layout {
            TextField(inputPrompt, text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .focused($focused)
                .submitLabel(.send)
                .onSubmit(submit)
                // A multi-line field takes the keyboard's «send» key as a new line; one typed new line at the end
                // sends instead (a pasted multi-line text stays as it is).
                .onChange(of: draft) { old, new in
                    guard new.hasSuffix("\n"), new.count == old.count + 1 else { return }
                    draft.removeLast()
                    submit()
                }
                .frame(maxWidth: .infinity, minHeight: JolTarget.minimum, alignment: .leading)
                .contentShape(Rectangle())
                .accessibilityLabel(Text(inputPrompt))
                .accessibilityIdentifier("chat-input")
            Button(action: submit) {
                Image(systemName: "arrow.up")
                    .font(.body.weight(.bold))
                    .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                    .frame(width: 32, height: 32)
                    .background(JolColor.brand.opacity(canSend ? 1 : 0.35), in: Circle())
                    .foregroundStyle(JolColor.onBrand)
                    .minTapTarget()
            }
            .buttonStyle(.plain)
            .disabled(!canSend)
            .accessibilityLabel(Text("Send"))
            .accessibilityHint(Text("Sends your message to Jol"))
            .accessibilityIdentifier("chat-send")
        }
        .padding(.horizontal, JolSpacing.md)
        .padding(.vertical, JolSpacing.xs)
        .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
    }

    private var inputPrompt: LocalizedStringKey {
        isActive ? LocalizedStringKey("Message") : LocalizedStringKey("Where do you want to go?")
    }

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !model.isStreaming && !model.isOpening
    }

    /// Sends the draft and keeps the cursor in the field, like a messenger: the next wish follows without a tap
    /// (owner, 2026-11-22). The keyboard closes only when the person collapses the chat or drags the transcript.
    private func submit() {
        guard canSend else { return }
        let hadFocus = focused
        onSend()
        // The return key resigns the field by itself; give the focus back once that has happened.
        if hadFocus { DispatchQueue.main.async { focused = true } }
    }
}

/// Collapsed chat: a compact bar next to the profile button; tapping it expands the chat. While an answer is being
/// written the bar shows a typing indicator, so a collapsed chat visibly keeps working.
struct CollapsedChatBar: View {
    let draft: String
    var isTyping = false
    let onExpand: () -> Void
    @Environment(\.dynamicTypeSize) private var typeSize

    /// What VoiceOver adds to «Expand chat»: the unsent draft, and that the answer is still being written.
    private var spokenValue: Text {
        var parts: [Text] = []
        if !draft.isEmpty { parts.append(Text(verbatim: draft)) }
        if isTyping { parts.append(Text("Jol is typing")) }
        return .spoken(parts)
    }

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
                    .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                    .foregroundStyle(JolColor.textPrimary)
                    .accessibilityHidden(true)
            }
            .lineLimit(typeSize.isAccessibilitySize ? 3 : 1)
            .padding(.horizontal, JolSpacing.lg)
            .padding(.vertical, JolSpacing.sm)
            .frame(maxWidth: .infinity, minHeight: 48)
            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text("Expand chat"))
        .accessibilityValue(spokenValue)
        .accessibilityHint(Text("Opens the chat"))
        .accessibilityIdentifier("chat-collapsed-bar")
    }
}

enum BriefFormatting {
    static func day(_ iso: String?) -> Date? {
        guard let iso else { return nil }
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = Region.current.timeZone
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: iso)
    }

    /// «5–8 дек.» / «5 – 8 Dec»; a single known date alone; nil when neither is known.
    static func dates(start: String?, end: String?, locale: Locale) -> String? {
        let style = Date.FormatStyle(timeZone: Region.current.timeZone)
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
        "\(kzt.formatted(.number.locale(locale))) \(Region.current.currencySymbol)"
    }
}
