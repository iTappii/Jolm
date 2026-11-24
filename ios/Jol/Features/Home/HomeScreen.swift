import SwiftUI

/// Main screen (SSOT §11.1, §11.4): the map fills the screen; a collapsible chat floats above it;
/// the profile button sits top-right (mirror of the side-panel button); a swipe from the left edge opens the
/// side panel.
struct HomeScreen: View {
    @Environment(AppContainer.self) private var container
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var chatExpanded = true
    @State private var draft = ""
    @State private var sidebarOpen = false
    @State private var profileOpen = false
    @State private var routesOpen = false
    @State private var favoritesOpen = false
    @State private var cardDetent = PlaceCardSheet.cardDetent
    @State private var screenHeight: CGFloat = 874
    /// Height of the on-screen keyboard (0 when hidden): with a live route the card shrinks above it (owner).
    @State private var keyboardHeight: CGFloat = 0
    @State private var projection = MapProjection()

    var body: some View {
        ZStack {
            MapScreen(
                places: container.places,
                chat: container.chat,
                directions: container.directions,
                tripMap: container.tripMap,
                events: container.events,
                projection: projection, landmarks: showsLandmarks ? container.landmarks.items : [],
                bottomInset: mapBottomInset
            )
            if showsLandmarks { landmarksLayer }
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
                if let live = container.chat.state.liveRoute {
                    LiveRouteOverlay(
                        route: live,
                        projection: projection,
                        language: container.language.code,
                        isChoosing: container.chat.isChoosing,
                        error: container.chat.liveRouteError,
                        onChoose: { stop, place in container.chat.chooseAlternative(ord: stop.ord, placeID: place.id) },
                        onOpenPlace: { container.places.select($0.summary) },
                        onDismissError: { container.chat.dismissLiveRouteError() }
                    )
                }
                if container.chat.isBuildingRoute || container.chat.routeBuildFailed {
                    StandaloneBuildBadge(chat: container.chat)
                }
                overlay
                attributionLine
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
                onSignIn: {
                    sidebarOpen = false
                    container.gate.requireAccount {}
                },
                trips: container.auth.isSignedIn ? container.tripMap.summaries : nil,
                onOpenTrip: { id in
                    chatExpanded = false
                    container.tripMap.open(tripID: id)
                },
                onRetryTrips: { container.tripMap.loadSummaries() },
                downloads: container.offline,
                onDownloadTrip: { id in Task { await container.offline.download(tripID: id) } },
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
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillChangeFrameNotification)) { note in
            guard let frame = note.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect else { return }
            withAnimation(.easeOut(duration: 0.25)) { keyboardHeight = max(0, screenHeight - frame.minY) }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillHideNotification)) { _ in
            withAnimation(.easeOut(duration: 0.25)) { keyboardHeight = 0 }
        }
        .animation(.snappy(duration: 0.3), value: chatExpanded)
        .task(id: container.language.code) { await container.landmarks.load(language: container.language.code) }
        .announcingChatChanges(container.chat, language: container.language.code)
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
                container.offline.removeAll() // a saved plan belongs to the account that is gone
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
                // The card never reaches the top button row (side panel / profile), even with the keyboard up.
                Spacer(minLength: Self.topButtonsClearance)
                ChatPanel(
                    model: container.chat,
                    draft: $draft,
                    conversationHeight: cardHeight,
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
            if !chatExpanded { bottomBar }
        }
        // The card ends just above the static attribution line (see `attributionLine`).
        .padding(.bottom, Self.attributionClearance)
        .overlay(alignment: .leading) {
            EdgeSwipeStrip { sidebarOpen = true }
        }
        .overlay(alignment: .topTrailing) { profileButton }
        .overlay(alignment: .topLeading) {
            Button {
                sidebarOpen = true
            } label: {
                Image(systemName: "sidebar.left")
                    .font(.title3)
                    .dynamicTypeSize(...DynamicTypeSize.xxxLarge) // fixed 44 pt button
                    .frame(width: 44, height: 44)
                    .background(.thinMaterial, in: Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Recent chats"))
            .accessibilityHint(Text("Opens the list of chats, trips and favourites"))
            .accessibilityIdentifier("open-sidebar")
            .padding(.leading, JolSpacing.sm)
            .padding(.top, JolSpacing.sm)
        }
    }

    /// «© OpenStreetMap contributors», pinned to the bottom of the screen. It lives outside the overlay that follows
    /// the keyboard and ignores the keyboard safe area: the keyboard slides over it, it never rides up.
}

extension HomeScreen {
    /// The main sights (Ш-69) are not drawn while the live route, the full route map or a way to a place is on the
    /// map: those show their own stops, and the sights would only crowd (or be mistaken for) them.
    var landmarksLayer: some View {
        LandmarksOverlay(
            landmarks: container.landmarks.items,
            projection: projection,
            onOpen: { container.places.select($0.summary) }
        )
        // Behind the open chat the markers cannot be reached, so VoiceOver skips them.
        .accessibilityHidden(chatExpanded)
    }

    var showsLandmarks: Bool {
        !container.landmarks.items.isEmpty && !container.tripMap.isOpen
            && container.chat.state.liveRoute == nil && !container.directions.isActive
    }

    private var attributionLine: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 0)
            Text("© OpenStreetMap contributors")
                .font(.caption2)
                .foregroundStyle(JolColor.textPrimary)
                // A legal line that must stay readable but must not grow over the map: capped like the full map.
                .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(.regularMaterial, in: Capsule())
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.horizontal, JolSpacing.sm)
                .accessibilityIdentifier("osm-attribution")
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .ignoresSafeArea(.keyboard)
        .allowsHitTesting(false)
    }

    private var profileButton: some View {
        Button {
            profileOpen = true
        } label: {
            Image(systemName: "person.crop.circle")
                .font(.title3)
                .dynamicTypeSize(...DynamicTypeSize.xxxLarge) // fixed 44 pt button
                .frame(width: 44, height: 44)
                .background(.thinMaterial, in: Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(Text("Profile"))
        .accessibilityHint(Text("Opens the account menu"))
        .accessibilityIdentifier("open-profile-menu")
        .padding(.trailing, JolSpacing.sm)
        .padding(.top, JolSpacing.sm)
    }

    /// Collapsed chat: the bar has the bottom row to itself, full width.
    private var bottomBar: some View {
        CollapsedChatBar(draft: draft, isTyping: container.chat.isStreaming) { chatExpanded = true }
            .transition(.move(edge: .bottom).combined(with: .opacity))
            .padding(.horizontal, JolSpacing.sm)
    }

    private var gatePresented: Binding<Bool> {
        // While a place card is up, the card presents the sheet itself (a view cannot present two sheets).
        Binding(
            get: { container.gate.isPresenting && container.places.selected == nil },
            set: { container.gate.isPresenting = $0 }
        )
    }

    /// Share of the screen the chat card takes once a conversation is on.
    private static let conversationFraction: CGFloat = 0.68
    /// Height of the top button row (44pt buttons + their padding) the card must stay below.
    private static let topButtonsClearance: CGFloat = 60
    /// Space under the overlay for the static attribution line.
    private static let attributionClearance: CGFloat = 26

    /// A live route (Ш-54) needs room on the map above the chat: the card is shorter while it is drawn.
    private var conversationFraction: CGFloat {
        container.chat.state.liveRoute == nil ? Self.conversationFraction : Self.liveConversationFraction
    }

    private static let liveConversationFraction: CGFloat = 0.5

    /// With the keyboard up and a live route on the map, the card takes this share of the space above the keyboard
    /// (never less than `liveKeyboardCardMin`: header, answer chain and the field stay usable), so the route stays
    /// visible above it while the person keeps typing wishes.
    private static let liveKeyboardCardShare: CGFloat = 0.5
    private static let liveKeyboardCardMin: CGFloat = 250
    /// At accessibility text sizes the header, the chain and the two-row field need more than that (Ш-52).
    private static let liveKeyboardCardMinLarge: CGFloat = 400

    private var liveRouteUnderKeyboard: Bool {
        keyboardHeight > 0 && container.chat.state.liveRoute != nil
    }

    private var cardHeight: CGFloat {
        let normal = screenHeight * conversationFraction
        guard liveRouteUnderKeyboard else { return normal }
        let aboveKeyboard = screenHeight - keyboardHeight
        let floor = typeSize.isAccessibilitySize ? Self.liveKeyboardCardMinLarge : Self.liveKeyboardCardMin
        return min(normal, max(floor, aboveKeyboard * Self.liveKeyboardCardShare))
    }

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
            guard chatExpanded, chatIsActive else { return 0 }
            // The keyboard lifts the card: the map keeps the live route in the strip above both.
            if liveRouteUnderKeyboard { return keyboardHeight + cardHeight + 12 }
            return screenHeight * (conversationFraction + 0.03)
        }
        // At accessibility text sizes the card opens at the taller detent (PlaceCardSheet), keep the pin above it.
        let tall = container.directions.isActive || typeSize.isAccessibilitySize
        let fraction = tall ? PlaceCardSheet.directionsFraction : PlaceCardSheet.cardFraction
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
