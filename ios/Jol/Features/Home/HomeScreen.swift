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
    @State private var savedNote = false
    @State private var cardDetent = PlaceCardSheet.cardDetent
    @State private var screenHeight: CGFloat = 874

    var body: some View {
        ZStack {
            MapScreen(
                places: container.places,
                directions: container.directions,
                bottomInset: mapBottomInset
            )
            if chatExpanded {
                Color.black.opacity(0.12)
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
            }
            overlay
            SidebarPanel(
                isOpen: $sidebarOpen,
                onNewChat: {
                    draft = ""
                    savedNote = false
                    chatExpanded = true
                },
                onOpenRoutes: { routesOpen = true },
                onOpenFavorites: { container.gate.requireAccount { favoritesOpen = true } }
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
            if container.auth.isSignedIn { await container.favorites.load() } else { container.favorites.clear() }
        }
        .sheet(isPresented: $routesOpen) {
            CuratedRoutesSheet(model: container.places)
        }
        .sheet(isPresented: cardPresented) {
            PlaceCardSheet(model: container.places, directions: container.directions, detent: $cardDetent)
        }
        .onChange(of: container.places.selected?.id) { _, id in
            container.directions.reset()
            if id != nil { chatExpanded = false } else { cardDetent = PlaceCardSheet.cardDetent }
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

    /// A personal trip needs an account (SSOT §3.2): a guest is asked to sign in first, the draft stays in place.
    /// The real chat (Ш-32) will start from the closure.
    private func sendDraft() {
        guard !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        container.gate.requireAccount { savedNote = true }
    }

    private var gatePresented: Binding<Bool> {
        // While a place card is up, the card presents the sheet itself (a view cannot present two sheets).
        Binding(
            get: { container.gate.isPresenting && container.places.selected == nil },
            set: { container.gate.isPresenting = $0 }
        )
    }

    private var mapBottomInset: CGFloat {
        if container.places.selected == nil { return 0 }
        let fraction = container.directions.isActive ? PlaceCardSheet.directionsFraction : PlaceCardSheet.cardFraction
        return screenHeight * fraction
    }

    private var cardPresented: Binding<Bool> {
        Binding(
            get: { container.places.selected != nil },
            set: { if !$0 { container.places.clearSelection() } }
        )
    }

    private var overlay: some View {
        VStack(spacing: JolSpacing.sm) {
            if chatExpanded {
                Spacer(minLength: 0)
                ChatPanel(draft: $draft, savedNote: savedNote, onCollapse: { chatExpanded = false }, onSend: sendDraft)
                    .padding(.horizontal, JolSpacing.lg)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                Spacer(minLength: 0)
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
                CollapsedChatBar(draft: draft) { chatExpanded = true }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, JolSpacing.sm)
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
