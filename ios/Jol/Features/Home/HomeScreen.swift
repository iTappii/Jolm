import SwiftUI

/// Main screen (SSOT §11.1, §11.4): the map fills the screen; a collapsible chat floats above it;
/// the profile button sits bottom-left; a swipe from the left edge opens the side panel.
struct HomeScreen: View {
    @Environment(AppContainer.self) private var container
    @State private var chatExpanded = true
    @State private var draft = ""
    @State private var sidebarOpen = false
    @State private var profileOpen = false
    @State private var routesOpen = false
    @State private var favoritesOpen = false
    @State private var cardDetent = PlaceCardSheet.cardDetent
    @State private var screenHeight: CGFloat = 874

    var body: some View {
        ZStack {
            MapScreen(
                places: container.places,
                chat: container.chat,
                directions: container.directions,
                tripMap: container.tripMap,
                events: container.events,
                bottomInset: mapBottomInset
            )
            if chatExpanded {
                Color.black.opacity(0.12)
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
            }
            if container.tripMap.isOpen {
                TripMapOverlay(
                    model: container.tripMap,
                    panelVisible: container.places.selected == nil && container.events.selected == nil,
                    panelHeight: screenHeight * TripMapOverlay.panelFraction,
                    onSelectPlace: { container.places.select($0.summary) }
                )
            } else {
                overlay
            }
            SidebarPanel(
                isOpen: $sidebarOpen,
                onNewChat: {
                    draft = ""
                    container.chat.newChat()
                    chatExpanded = true
                },
                onOpenRoutes: { routesOpen = true },
                onOpenFavorites: { container.gate.requireAccount { favoritesOpen = true } },
                trips: container.auth.isSignedIn ? container.tripMap.summaries : nil,
                onOpenTrip: { id in
                    chatExpanded = false
                    container.tripMap.open(tripID: id)
                },
                onRetryTrips: { container.tripMap.loadSummaries() },
                chats: container.auth.isSignedIn ? container.chat.recent : nil,
                onOpenChat: { id in
                    draft = ""
                    container.chat.open(id)
                    chatExpanded = true
                },
                onRetryChats: { container.chat.loadRecent() }
            )
        }
        .background(
            GeometryReader { proxy in
                Color.clear
                    .onAppear { screenHeight = proxy.size.height }
                    .onChange(of: proxy.size.height) { _, height in screenHeight = height }
            }
            .ignoresSafeArea()
        )
        .animation(.snappy(duration: 0.3), value: chatExpanded)
        .sheet(isPresented: $profileOpen) {
            ProfileMenuSheet()
        }
        .sheet(
            isPresented: gatePresented,
            onDismiss: { container.gate.sheetDismissed() },
            content: { AccountGateSheet() }
        )
        .sheet(isPresented: $favoritesOpen) {
            FavoritesSheet(model: container.favorites) { container.places.select($0) }
        }
        .task(id: container.auth.isSignedIn) {
            if container.auth.isSignedIn {
                await container.favorites.load()
            } else {
                container.favorites.clear()
                container.chat.clearRecent()
                container.tripMap.close()
                container.tripMap.clearSummaries()
                container.chat.reset() // a saved chat belongs to the account that is gone
            }
        }
        .onChange(of: sidebarOpen) { _, open in
            if open, container.auth.isSignedIn {
                container.chat.loadRecent()
                container.tripMap.loadSummaries()
            }
        }
        .onChange(of: container.tripMap.isOpen) { _, open in
            if open {
                container.events.clearSelection()
                container.places.clearSelection()
            }
        }
        .onChange(of: container.tripMap.editRevision) { _, _ in
            // An edit on the full map changed the plan: the pins behind the chat follow it.
            if container.chat.tripID == container.tripMap.tripID { container.chat.loadTrip() }
        }
        .sheet(isPresented: eventPresented) {
            EventCardSheet(events: container.events, places: container.places)
        }
        .sheet(isPresented: $routesOpen) {
            CuratedRoutesSheet(model: container.places)
        }
        .sheet(isPresented: cardPresented) {
            PlaceCardSheet(model: container.places, directions: container.directions, detent: $cardDetent)
        }
        .onChange(of: container.places.selected?.id) { _, id in
            container.directions.reset()
            if id != nil {
                chatExpanded = false
                container.events.clearSelection()
            } else {
                cardDetent = PlaceCardSheet.cardDetent
            }
        }
        .onChange(of: container.events.selected?.id) { _, id in
            if id != nil { chatExpanded = false }
        }
        .onChange(of: container.directions.isActive) { _, active in
            cardDetent = active ? PlaceCardSheet.directionsDetent : PlaceCardSheet.cardDetent
        }
        .onChange(of: container.places.activeRoute?.id) { _, id in
            if id != nil {
                routesOpen = false
                chatExpanded = false
            }
        }
    }

    /// A personal trip needs an account (SSOT §3.2). A signed-in user writes to a saved chat. A guest talks to the
    /// simple guest chat, unless the message asks for a personal trip: then the sign-in sheet comes first, the draft
    /// stays in the field, and after signing in the same text goes into a new saved chat.
    private func sendDraft() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !container.chat.isStreaming else { return }
        if container.auth.isSignedIn {
            submit(text, signedIn: true)
        } else if ChatModel.wantsPersonalTrip(text) {
            container.gate.requireAccount { submit(text, signedIn: true) }
        } else {
            submit(text, signedIn: false)
        }
    }

    private func submit(_ text: String, signedIn: Bool) {
        if draft.trimmingCharacters(in: .whitespacesAndNewlines) == text { draft = "" }
        container.chat.send(text, signedIn: signedIn)
    }

    /// The guest chat's "sign in to build a personal route": the last question moves into a saved chat.
    private func guestSignIn() {
        container.gate.requireAccount {
            if let text = container.chat.lastUserText() { submit(text, signedIn: true) }
        }
    }

    private var showsGuestBanner: Bool {
        let chat = container.chat
        return chat.isGuestTranscript && !chat.isStreaming && chat.state.messages.last?.role == .assistant
    }

    private var overlay: some View {
        VStack(spacing: JolSpacing.sm) {
            if chatExpanded {
                Spacer(minLength: 0)
                ChatPanel(
                    model: container.chat,
                    draft: $draft,
                    conversationHeight: screenHeight * Self.conversationFraction,
                    showsGuestBanner: showsGuestBanner,
                    onCollapse: { chatExpanded = false },
                    onSend: sendDraft,
                    onRetry: { container.chat.retry() },
                    onNewChat: {
                        draft = ""
                        container.chat.newChat()
                    },
                    onOpenRoute: {
                        chatExpanded = false
                        if let id = container.chat.tripID { container.tripMap.open(tripID: id) }
                    },
                    onGuestSignIn: guestSignIn
                )
                .padding(.horizontal, JolSpacing.lg)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                if !chatIsActive { Spacer(minLength: 0) }
            } else {
                Spacer(minLength: 0)
            }
            RouteBar(model: container.places)
            attribution
            bottomBar
        }
        // Keeps the bar above MapLibre's logo / attribution ornaments at the bottom of the map.
        .padding(.bottom, 44)
        .overlay(alignment: .leading) {
            EdgeSwipeStrip { sidebarOpen = true }
        }
        .overlay(alignment: .topLeading) {
            Button {
                sidebarOpen = true
            } label: {
                Image(systemName: "sidebar.left")
                    .font(.title3)
                    .frame(width: 44, height: 44)
                    .background(.thinMaterial, in: Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Recent chats"))
            .accessibilityIdentifier("open-sidebar")
            .padding(.leading, JolSpacing.sm)
            .padding(.top, JolSpacing.sm)
        }
    }

    private var attribution: some View {
        Text("© OpenStreetMap contributors")
            .font(.caption2)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(.thinMaterial, in: Capsule())
            .frame(maxWidth: .infinity, alignment: .trailing)
            .padding(.horizontal, JolSpacing.sm)
            .accessibilityIdentifier("osm-attribution")
    }

    private var bottomBar: some View {
        HStack(spacing: JolSpacing.sm) {
            Button {
                profileOpen = true
            } label: {
                Image(systemName: "person.crop.circle")
                    .font(.title2)
                    .frame(width: 48, height: 48)
                    .background(.thinMaterial, in: Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Profile"))
            .accessibilityIdentifier("open-profile-menu")
            if !chatExpanded {
                CollapsedChatBar(draft: draft, isTyping: container.chat.isStreaming) { chatExpanded = true }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, JolSpacing.sm)
    }
}

extension HomeScreen {
    private var gatePresented: Binding<Bool> {
        // While a place card is up, the card presents the sheet itself (a view cannot present two sheets).
        Binding(
            get: { container.gate.isPresenting && container.places.selected == nil },
            set: { container.gate.isPresenting = $0 }
        )
    }

    /// Share of the screen the chat card takes once a conversation is on.
    private static let conversationFraction: CGFloat = 0.56

    private var chatIsActive: Bool {
        let chat = container.chat
        return !chat.state.isEmpty || chat.isOpening || chat.openFailed
    }

    private var mapBottomInset: CGFloat {
        if container.events.selected != nil { return screenHeight * PlaceCardSheet.cardFraction }
        if container.tripMap.isOpen, container.places.selected == nil {
            return screenHeight * TripMapOverlay.panelFraction
        }
        if container.places.selected == nil {
            // The live map keeps its pins above the open conversation.
            return chatExpanded && chatIsActive ? screenHeight * (Self.conversationFraction + 0.08) : 0
        }
        let fraction = container.directions.isActive ? PlaceCardSheet.directionsFraction : PlaceCardSheet.cardFraction
        return screenHeight * fraction
    }

    private var eventPresented: Binding<Bool> {
        Binding(
            get: { container.events.selected != nil },
            set: { if !$0 { container.events.clearSelection() } }
        )
    }

    private var cardPresented: Binding<Bool> {
        Binding(
            get: { container.places.selected != nil },
            set: { if !$0 { container.places.clearSelection() } }
        )
    }
}

/// Invisible strip on the left edge. Only this strip listens for the open-panel swipe, so the map keeps
/// its own pan gesture everywhere else.
private struct EdgeSwipeStrip: View {
    let onOpen: () -> Void

    var body: some View {
        Color.clear
            .frame(width: 24)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 12)
                    .onEnded { value in
                        if value.translation.width > 40, abs(value.translation.height) < value.translation.width {
                            onOpen()
                        }
                    }
            )
            .accessibilityIdentifier("sidebar-edge")
            .accessibilityHidden(true)
    }
}
