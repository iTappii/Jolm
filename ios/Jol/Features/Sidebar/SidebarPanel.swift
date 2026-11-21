import SwiftUI

/// Side panel (SSOT §11.4): recent chats and "New chat". Opens by edge swipe or `isOpen = true`,
/// closes by tapping outside, swiping left, or the close button.
struct SidebarPanel: View {
    @Binding var isOpen: Bool
    let onNewChat: () -> Void
    var onOpenRoutes: () -> Void = {}
    var onOpenFavorites: () -> Void = {}
    /// Saved trips of a signed-in user (nil: nothing to list, e.g. a guest); a row opens the full route map.
    var trips: ChatModel.Load<[TripSummary]>?
    var onOpenTrip: (UUID) -> Void = { _ in }
    var onRetryTrips: () -> Void = {}
    /// Saved chats of a signed-in user (nil: nothing to list, e.g. a guest).
    var chats: ChatModel.Load<[ChatSummary]>?
    var onOpenChat: (UUID) -> Void = { _ in }
    var onRetryChats: () -> Void = {}
    private let width: CGFloat = 300
    @Environment(\.locale) private var locale

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

    @ViewBuilder private var tripsSection: some View {
        switch trips {
        case .failed:
            Button("Couldn't load trips. Try again.", action: onRetryTrips)
                .font(JolFont.callout)
                .accessibilityIdentifier("sidebar-trips-retry")
        case .loaded(let items) where !items.isEmpty:
            VStack(alignment: .leading, spacing: JolSpacing.xs) {
                Text("My trips").font(JolFont.callout.weight(.semibold)).foregroundStyle(JolColor.textSecondary)
                ForEach(items.prefix(5)) { trip in
                    Button {
                        onOpenTrip(trip.id)
                        isOpen = false
                    } label: {
                        HStack(spacing: JolSpacing.sm) {
                            Image(systemName: "map")
                            let dates = BriefFormatting.dates(start: trip.startDate, end: trip.endDate, locale: locale)
                            Text(verbatim: dates ?? "…")
                            Spacer(minLength: 0)
                            if let days = trip.days { Text("\(days) days").foregroundStyle(JolColor.textSecondary) }
                        }
                        .font(JolFont.body)
                        .foregroundStyle(JolColor.textPrimary)
                        .padding(.vertical, JolSpacing.sm)
                        .padding(.horizontal, JolSpacing.md)
                        .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("sidebar-trip-row")
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("sidebar-trips")
        default:
            EmptyView()
        }
    }

    @ViewBuilder private var recentChats: some View {
        switch chats {
        case .loading:
            ProgressView()
                .frame(maxWidth: .infinity)
                .accessibilityIdentifier("sidebar-chats-loading")
        case .failed:
            VStack(alignment: .leading, spacing: JolSpacing.sm) {
                Text("Couldn't load chats.")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.textSecondary)
                Button("Try again", action: onRetryChats)
                    .accessibilityIdentifier("sidebar-chats-retry")
            }
        case .loaded(let items) where !items.isEmpty:
            ScrollView {
                LazyVStack(alignment: .leading, spacing: JolSpacing.xs) {
                    ForEach(items) { item in
                        Button {
                            onOpenChat(item.id)
                            isOpen = false
                        } label: {
                            Group {
                                if let title = item.displayTitle {
                                    Text(verbatim: title)
                                } else {
                                    Text("New chat")
                                }
                            }
                            .font(JolFont.body)
                            .foregroundStyle(JolColor.textPrimary)
                            .lineLimit(2)
                            .multilineTextAlignment(.leading)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, JolSpacing.sm)
                            .padding(.horizontal, JolSpacing.md)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("sidebar-chat-row")
                    }
                }
            }
            .accessibilityIdentifier("sidebar-chats")
        case nil:
            // A guest chat has no memory and no history (SSOT §3.1): say so instead of "no chats yet".
            Text("Sign in to keep your chats and trips.")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("sidebar-guest-hint")
        default:
            Text("No chats yet")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("sidebar-empty")
        }
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
            Button {
                onOpenFavorites()
                isOpen = false
            } label: {
                Label("Favorites", systemImage: "heart")
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, JolSpacing.md)
                    .padding(.horizontal, JolSpacing.md)
                    .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("sidebar-favorites")
            tripsSection
            recentChats
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
