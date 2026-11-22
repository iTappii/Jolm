import SwiftUI

/// Side panel (SSOT §11.4): recent chats and "New chat". Opens by edge swipe or `isOpen = true`,
/// closes by tapping outside, swiping left, or the close button.
struct SidebarPanel: View {
    @Binding var isOpen: Bool
    let onNewChat: () -> Void
    var onOpenRoutes: () -> Void = {}
    var onOpenFavorites: () -> Void = {}
    /// A guest taps the hint: the sign-in gate opens (nothing is lost — a guest chat has no history anyway).
    var onSignIn: () -> Void = {}
    /// Saved trips of a signed-in user (nil: nothing to list, e.g. a guest); a row opens the full route map.
    var trips: ChatModel.Load<[TripSummary]>?
    var onOpenTrip: (UUID) -> Void = { _ in }
    var onRetryTrips: () -> Void = {}
    /// Trips saved on the device (Ш-42): each row gets a download / downloaded mark.
    var downloads: OfflineTripsModel?
    var onDownloadTrip: (UUID) -> Void = { _ in }
    /// Saved chats of a signed-in user (nil: nothing to list, e.g. a guest).
    var chats: ChatModel.Load<[ChatSummary]>?
    var onOpenChat: (UUID) -> Void = { _ in }
    var onRetryChats: () -> Void = {}
    private var width: CGFloat { typeSize.isAccessibilitySize ? 340 : 300 }
    @Environment(\.locale) private var locale
    @Environment(\.dynamicTypeSize) private var typeSize

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
                // Trips and chats reload while the panel opens, so their rows are inserted mid-animation. Without
                // a geometry group SwiftUI draws such rows at their final place, ahead of the sliding panel;
                // `geometryGroup()` makes them take the panel's animated position.
                panel
                    .geometryGroup()
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
                .frame(minHeight: JolTarget.minimum)
                .accessibilityIdentifier("sidebar-trips-retry")
        case .loaded(let items) where !items.isEmpty:
            VStack(alignment: .leading, spacing: JolSpacing.xs) {
                Text("My trips").font(JolFont.callout.weight(.semibold)).foregroundStyle(JolColor.textSecondary)
                    .accessibilityAddTraits(.isHeader)
                ForEach(items.prefix(5)) { trip in
                    HStack(spacing: JolSpacing.xs) {
                    Button {
                        onOpenTrip(trip.id)
                        isOpen = false
                    } label: {
                        HStack(alignment: typeSize.isAccessibilitySize ? .top : .firstTextBaseline,
                               spacing: JolSpacing.sm) {
                            Image(systemName: "map").accessibilityHidden(true)
                            tripText(trip)
                        }
                        .font(JolFont.body)
                        .foregroundStyle(JolColor.textPrimary)
                        .padding(.vertical, JolSpacing.sm)
                        .padding(.horizontal, JolSpacing.md)
                        .frame(maxWidth: .infinity, minHeight: JolTarget.minimum, alignment: .leading)
                        .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
                    }
                    .buttonStyle(.plain)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("sidebar-trip-row")
                    downloadButton(trip.id)
                    }
                }
                if downloads?.problem != nil {
                    Text("Couldn't download the route. Check your connection.")
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.danger)
                        .accessibilityIdentifier("sidebar-download-problem")
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("sidebar-trips")
        default:
            EmptyView()
        }
    }

    @ViewBuilder private func downloadButton(_ id: UUID) -> some View {
        if let downloads {
            let state = downloads.state(for: id)
            Button { onDownloadTrip(id) } label: {
                Group {
                    switch state {
                    case .none: Image(systemName: "arrow.down.circle")
                    case .downloading: ProgressView()
                    case .saved: Image(systemName: "checkmark.circle.fill").foregroundStyle(JolColor.brand)
                    }
                }
                .font(.title3)
                .frame(width: JolTarget.minimum, height: JolTarget.minimum)
                .contentShape(Rectangle())
                .foregroundStyle(JolColor.textPrimary)
            }
            .buttonStyle(.plain)
            .disabled(state != .none)
            .accessibilityLabel(state == .none ? Text("Download route") : state == .saved
                                ? Text("Route downloaded") : Text("Downloading the route…"))
            .accessibilityIdentifier("sidebar-trip-download")
        }
    }

    private var panel: some View {
        VStack(alignment: .leading, spacing: JolSpacing.lg) {
            header
            // At large type the buttons, trips and chats scroll together, so nothing is pushed off the screen.
            if typeSize.isAccessibilitySize {
                ScrollView { content }
            } else {
                content.frame(maxHeight: .infinity, alignment: .top)
            }
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
        .accessibilityAddTraits(.isModal)
        .accessibilityIdentifier("sidebar-panel")
    }

    private var header: some View {
        HStack(alignment: .top) {
            Text("Recent chats")
                .font(JolFont.title)
                .foregroundStyle(JolColor.textPrimary)
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: JolSpacing.sm)
            Button { isOpen = false } label: {
                Image(systemName: "xmark")
                    .font(.body.weight(.semibold))
                    .frame(width: JolTarget.minimum, height: JolTarget.minimum)
                    .background(JolColor.surface, in: Circle())
                    .foregroundStyle(JolColor.textPrimary)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Close"))
            .accessibilityIdentifier("sidebar-close")
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: JolSpacing.lg) {
            Button {
                onNewChat()
                isOpen = false
            } label: {
                Label("New chat", systemImage: "square.and.pencil")
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.onBrand)
                    .frame(maxWidth: .infinity, minHeight: JolTarget.minimum)
                    .padding(.vertical, JolSpacing.xs)
                    .background(JolColor.brand, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("sidebar-new-chat")
            navigationRow(
                "Ready-made routes", symbol: "point.topleft.down.curvedto.point.bottomright.up",
                identifier: "sidebar-routes", action: onOpenRoutes
            )
            navigationRow("Favorites", symbol: "heart", identifier: "sidebar-favorites", action: onOpenFavorites)
            tripsSection
            recentChats
        }
    }

    private func navigationRow(
        _ title: LocalizedStringKey, symbol: String, identifier: String, action: @escaping () -> Void
    ) -> some View {
        Button {
            action()
            isOpen = false
        } label: {
            Label(title, systemImage: symbol)
                .font(JolFont.headline)
                .foregroundStyle(JolColor.textPrimary)
                .frame(maxWidth: .infinity, minHeight: JolTarget.minimum, alignment: .leading)
                .padding(.vertical, JolSpacing.xs)
                .padding(.horizontal, JolSpacing.md)
                .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(identifier)
    }
}

// The list of recent chats and the text of a trip row.
extension SidebarPanel {
    /// Dates and length of a trip: side by side, one under the other at large type.
    @ViewBuilder private func tripText(_ trip: TripSummary) -> some View {
        let dates = BriefFormatting.dates(start: trip.startDate, end: trip.endDate, locale: locale)
        if typeSize.isAccessibilitySize {
            VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                Text(verbatim: dates ?? "…")
                if let days = trip.days { Text("\(days) days").foregroundStyle(JolColor.textSecondary) }
            }
        } else {
            Text(verbatim: dates ?? "…")
            Spacer(minLength: 0)
            if let days = trip.days { Text("\(days) days").foregroundStyle(JolColor.textSecondary) }
        }
    }

    private func chatRows(_ items: [ChatSummary]) -> some View {
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
                    .lineLimit(typeSize.isAccessibilitySize ? 4 : 2)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, minHeight: JolTarget.minimum, alignment: .leading)
                    .padding(.vertical, JolSpacing.xs)
                    .padding(.horizontal, JolSpacing.md)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("sidebar-chat-row")
            }
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
                    .frame(minHeight: JolTarget.minimum)
                    .accessibilityIdentifier("sidebar-chats-retry")
            }
        case .loaded(let items) where !items.isEmpty:
            // At large type the whole panel scrolls (see `panel`); otherwise the list scrolls under the buttons.
            if typeSize.isAccessibilitySize {
                chatRows(items).accessibilityIdentifier("sidebar-chats")
            } else {
                ScrollView { chatRows(items) }.accessibilityIdentifier("sidebar-chats")
            }
        case nil:
            // A guest chat has no memory and no history (SSOT §3.1): say so instead of "no chats yet".
            Button(action: onSignIn) {
                Text("Sign in to keep your chats and trips.")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.brandText)
                    .multilineTextAlignment(.leading)
                    .frame(minHeight: JolTarget.minimum)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("sidebar-guest-hint")
        default:
            Text("No chats yet")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("sidebar-empty")
        }
    }
}
