import SwiftUI

/// VoiceOver announcements for what changes on screen while the person is talking to the chat (Ш-52): a new node of
/// the answer chain, a new stop of the live route, the finished route. The chat card and the map are not in the
/// focus when the answer arrives, so without this a VoiceOver user would not learn that the plan grew.
/// Only live changes are announced (`isStreaming`): opening a saved chat shows everything at once and stays silent.
struct ChatAnnouncements: ViewModifier {
    let chat: ChatModel
    let language: String

    private var locale: Locale { Locale(identifier: language) }

    func body(content: Content) -> some View {
        content
            .onChange(of: chat.state.chainNodes.count) { old, new in
                guard chat.isStreaming, new > old, let node = chat.state.chainNodes.last else { return }
                post(ChainLabels.spoken(node, index: new - 1, brief: chat.state.brief ?? ChatBrief(), locale: locale))
            }
            .onChange(of: chat.state.liveRoute?.stops.count ?? 0) { old, new in
                guard chat.isStreaming, new > old, let route = chat.state.liveRoute, let stop = route.stops.last else {
                    return
                }
                post(LiveRouteFormatting.spokenStop(number: new, name: stop.place.name, language: language))
            }
            .onChange(of: chat.state.isConverged) { _, ready in
                if ready { post(L10n.string("Route ready", language: language)) }
            }
    }

    private func post(_ text: String) {
        AccessibilityNotification.Announcement(text).post()
    }
}

extension View {
    func announcingChatChanges(_ chat: ChatModel, language: String) -> some View {
        modifier(ChatAnnouncements(chat: chat, language: language))
    }
}
