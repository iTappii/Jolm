import SwiftUI

/// Scrollable body of an active chat: messages, proposal buttons, failure, route card.
struct ChatTranscriptView: View {
    /// Height of the fade band at the top of the transcript, under the chain strip.
    private static let topFade: CGFloat = 32
    let model: ChatModel
    let onRetry: () -> Void
    let onNewChat: () -> Void
    let onGuestSignIn: () -> Void
    var showsGuestBanner = false

    private var state: ChatState { model.state }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: JolSpacing.md) {
                    ForEach(state.messages) { message in
                        MessageRow(message: message, state: state.proposals[message.proposalID ?? UUID()]) { accept in
                            if let id = message.proposalID { model.decide(id, accept: accept) }
                        }
                        .id(message.id)
                    }
                    if state.isStreaming, state.messages.last?.role != .assistant {
                        TypingDots().accessibilityIdentifier("chat-typing")
                    }
                    if let failure = state.failure {
                        FailureRow(failure: failure, onRetry: onRetry, onNewChat: onNewChat)
                    }
                    if let route = state.route {
                        RouteCard(route: route)
                    }
                    if showsGuestBanner {
                        Button(action: onGuestSignIn) {
                            Label("Sign in to build a personal route", systemImage: "person.badge.key")
                                .font(JolFont.callout.weight(.semibold))
                                .foregroundStyle(JolColor.textPrimary)
                                .padding(.horizontal, JolSpacing.md)
                                .padding(.vertical, JolSpacing.sm)
                                .background(JolColor.surface, in: Capsule())
                                .overlay(Capsule().stroke(JolColor.brand, lineWidth: 1))
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("chat-guest-signin")
                    }
                    Color.clear.frame(height: 1).id("chat-bottom")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .scrollDismissesKeyboard(.interactively)
            // Pinned to the newest message when the card changes height (keyboard up with a live route).
            .defaultScrollAnchor(.bottom)
            // Room for the fade below, so the first message is fully visible when scrolled to the top.
            .contentMargins(.top, Self.topFade, for: .scrollContent)
            // A clean top boundary under the chain strip: scrolled-up messages dissolve instead of being sliced
            // (the top third of the band is fully clear, so no half-line peeks out under the labels).
            .mask {
                VStack(spacing: 0) {
                    LinearGradient(
                        stops: [.init(color: .clear, location: 0), .init(color: .clear, location: 0.3),
                                .init(color: .black, location: 1)],
                        startPoint: .top, endPoint: .bottom
                    )
                    .frame(height: Self.topFade)
                    Color.black
                }
            }
            .onChange(of: state.messages.last?.text) { scrollToBottom(proxy) }
            .onChange(of: state.messages.count) { scrollToBottom(proxy) }
            .onChange(of: state.isConverged) { scrollToBottom(proxy) }
            .onChange(of: state.failure) { scrollToBottom(proxy) }
            .onAppear { proxy.scrollTo("chat-bottom", anchor: .bottom) }
        }
        .accessibilityIdentifier("chat-transcript")
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy) {
        withAnimation(.easeOut(duration: 0.25)) { proxy.scrollTo("chat-bottom", anchor: .bottom) }
    }
}

private struct MessageRow: View {
    let message: ChatMessage
    let state: ProposalState?
    let onDecide: (Bool) -> Void

    var body: some View {
        switch message.role {
        case .user:
            Text(verbatim: message.text)
                .font(JolFont.body)
                .foregroundStyle(JolColor.onBrand)
                .padding(.horizontal, JolSpacing.md)
                .padding(.vertical, JolSpacing.sm)
                .background(JolColor.brand, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.leading, JolSpacing.xxl)
                .accessibilityIdentifier("chat-message-user")
        case .assistant:
            VStack(alignment: .leading, spacing: JolSpacing.sm) {
                Text(verbatim: message.text)
                    .font(JolFont.body)
                    .foregroundStyle(JolColor.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityIdentifier("chat-message-assistant")
                if message.proposalID != nil, let state {
                    ProposalButtons(state: state, onDecide: onDecide)
                }
            }
            .padding(.trailing, JolSpacing.lg)
        }
    }
}

/// Accept / Decline under a weather proposal (SSOT §7.1).
private struct ProposalButtons: View {
    let state: ProposalState
    let onDecide: (Bool) -> Void

    var body: some View {
        switch state {
        case .pending, .failed:
            VStack(alignment: .leading, spacing: JolSpacing.xs) {
                HStack(spacing: JolSpacing.sm) {
                    Button { onDecide(true) } label: {
                        Text("Accept")
                            .font(JolFont.callout.weight(.semibold))
                            .foregroundStyle(JolColor.onBrand)
                            .padding(.horizontal, JolSpacing.lg)
                            .padding(.vertical, JolSpacing.sm)
                            .background(JolColor.brand, in: Capsule())
                    }
                    .accessibilityIdentifier("proposal-accept")
                    Button { onDecide(false) } label: {
                        Text("Decline")
                            .font(JolFont.callout.weight(.semibold))
                            .foregroundStyle(JolColor.textPrimary)
                            .padding(.horizontal, JolSpacing.lg)
                            .padding(.vertical, JolSpacing.sm)
                            .background(JolColor.surface, in: Capsule())
                    }
                    .accessibilityIdentifier("proposal-decline")
                }
                .buttonStyle(.plain)
                if state == .failed {
                    Text("Couldn't apply this change. Try again.")
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.danger)
                        .accessibilityIdentifier("proposal-error")
                }
            }
        case .working:
            ProgressView().accessibilityIdentifier("proposal-working")
        case .accepted:
            status("Accepted", systemImage: "checkmark.circle.fill", tint: JolColor.brand)
        case .declined:
            status("Declined", systemImage: "xmark.circle", tint: JolColor.textSecondary)
        case .expired:
            status("No longer relevant", systemImage: "clock.arrow.circlepath", tint: JolColor.textSecondary)
        }
    }

    private func status(_ key: LocalizedStringKey, systemImage: String, tint: Color) -> some View {
        Label(key, systemImage: systemImage)
            .font(JolFont.callout.weight(.semibold))
            .foregroundStyle(tint)
            .accessibilityIdentifier("proposal-status")
    }
}

private struct FailureRow: View {
    let failure: ChatFailure
    let onRetry: () -> Void
    let onNewChat: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            message
                .font(JolFont.callout)
                .foregroundStyle(JolColor.danger)
                .accessibilityIdentifier("chat-error")
            if failure.canRetry {
                Button(action: onRetry) {
                    Label("Try again", systemImage: "arrow.clockwise")
                        .font(JolFont.callout.weight(.semibold))
                        .foregroundStyle(JolColor.textPrimary)
                        .padding(.horizontal, JolSpacing.md)
                        .padding(.vertical, JolSpacing.sm)
                        .background(JolColor.surface, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("chat-retry")
            } else {
                Button(action: onNewChat) {
                    Label("New chat", systemImage: "square.and.pencil")
                        .font(JolFont.callout.weight(.semibold))
                        .foregroundStyle(JolColor.onBrand)
                        .padding(.horizontal, JolSpacing.md)
                        .padding(.vertical, JolSpacing.sm)
                        .background(JolColor.brand, in: Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("chat-full-new")
            }
        }
    }

    @ViewBuilder private var message: some View {
        switch failure {
        case .busy:
            Text("Jol is still answering. Try again in a moment.")
        case .full:
            Text("This chat is full. Start a new chat to continue.")
        case .rateLimited(let seconds):
            if let seconds, seconds > 0 {
                Text("Too many messages. Try again in \(seconds) s.")
            } else {
                Text("Too many messages. Try again later.")
            }
        case .server(let message):
            if message.isEmpty { Text("Something went wrong.") } else { Text(verbatim: message) }
        case .network:
            Text("No connection. Check the network and try again.")
        case .other:
            Text("Something went wrong.")
        }
    }
}

/// "Route ready": the assistant offers the full map (Ш-37 builds the real screen; until then a day list).
private struct RouteCard: View {
    let route: RouteReady

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            Label("Route ready", systemImage: "checkmark.seal.fill")
                .font(JolFont.headline)
                .foregroundStyle(JolColor.textPrimary)
            if route.days > 0 {
                Text("\(route.days) days")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.textSecondary)
            }
            if let budget = route.budget, budget.isOver {
                Label("Over budget", systemImage: "exclamationmark.triangle.fill")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.danger)
                    .accessibilityIdentifier("route-over-budget")
            }
        }
        .padding(JolSpacing.md)
        .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("chat-route-card")
    }
}

/// Three pulsing dots: the assistant is writing.
struct TypingDots: View {
    @State private var phase = false

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3, id: \.self) { index in
                Circle()
                    .fill(JolColor.textSecondary)
                    .frame(width: 6, height: 6)
                    .scaleEffect(phase ? 1 : 0.55)
                    .opacity(phase ? 1 : 0.4)
                    .animation(.easeInOut(duration: 0.55).repeatForever().delay(Double(index) * 0.18), value: phase)
            }
        }
        .onAppear { phase = true }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("Jol is typing"))
    }
}
