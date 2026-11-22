import SwiftUI

/// «My bookings» (Ш-49, Ш-55): the list of requests with their status, from the profile menu.
struct MyBookingsScreen: View {
    let model: MyBookingsModel
    @Environment(\.locale) private var locale

    var body: some View {
        List {
            switch model.phase {
            case .idle, .loading:
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .accessibilityLabel(Text("Loading"))
                    .accessibilityIdentifier("bookings-loading")
            case .failed:
                VStack(alignment: .leading, spacing: JolSpacing.sm) {
                    Text("Couldn't load your bookings.").foregroundStyle(JolColor.textSecondary)
                    Button("Try again") { Task { await model.load() } }
                        .frame(minHeight: JolTarget.minimum)
                        .accessibilityIdentifier("bookings-retry")
                }
            case .loaded:
                if model.items.isEmpty {
                    Text("No bookings yet. Book a table, a room or tickets from a place's card.")
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.textSecondary)
                        .accessibilityIdentifier("bookings-empty")
                }
                ForEach(model.items) { booking in
                    NavigationLink {
                        BookingDetailScreen(model: model, bookingID: booking.id)
                    } label: {
                        row(booking)
                    }
                    .accessibilityIdentifier("bookings-row")
                    .onAppear {
                        if booking.id == model.items.last?.id { Task { await model.loadMore() } }
                    }
                }
            }
        }
        .navigationTitle(Text("My bookings"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("bookings-screen")
        .task { await model.load() }
        .refreshable { await model.load() }
    }

    private func row(_ booking: Booking) -> some View {
        let kind = BookingKind(rawValue: booking.kind)
        return AdaptiveStack(spacing: JolSpacing.xs, columnAlignment: .leading) {
            VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                Text(verbatim: booking.place?.name ?? "—").font(JolFont.body.weight(.semibold))
                HStack(spacing: JolSpacing.xs) {
                    if let kind { Text(BookingSheet.title(kind)) }
                    if let when = BookingFormatting.when(booking, locale: locale) { Text(verbatim: "· \(when)") }
                }
                .font(JolFont.caption)
                .foregroundStyle(JolColor.textSecondary)
                if let party = booking.partySize, let kind {
                    (Text(BookingSheet.partyLabel(kind)) + Text(verbatim: ": \(party)"))
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.textSecondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            BookingStatusLabel(status: booking.status)
        }
        .frame(minHeight: JolTarget.minimum)
        .accessibilityElement(children: .combine)
    }
}

/// Status with a symbol and a word: the colour is never the only sign.
struct BookingStatusLabel: View {
    let status: String

    var body: some View {
        Label {
            Text(BookingSheet.statusText(status))
        } icon: {
            Image(systemName: BookingSheet.statusSymbol(status))
        }
        .font(JolFont.caption.weight(.semibold))
        .foregroundStyle(Self.color(status))
        .accessibilityIdentifier("booking-row-status")
    }

    static func color(_ status: String) -> Color {
        switch status {
        case "confirmed": JolColor.statusOpen
        case "pending": JolColor.brandText
        case "cancelled": JolColor.textSecondary
        default: JolColor.danger
        }
    }
}

/// One booking: what it is, where it stands, and «Cancel booking» with a confirmation.
struct BookingDetailScreen: View {
    let model: MyBookingsModel
    let bookingID: UUID
    @Environment(\.locale) private var locale
    @State private var confirmCancel = false

    var body: some View {
        Group {
            if let booking = model.booking(id: bookingID) {
                content(booking)
            } else {
                Text("This booking is no longer in your list.")
                    .foregroundStyle(JolColor.textSecondary)
                    .padding(JolSpacing.xl)
            }
        }
        .navigationTitle(Text("Booking"))
        .navigationBarTitleDisplayMode(.inline)
        .onDisappear { model.dismissCancelProblem() }
        .accessibilityIdentifier("booking-detail")
    }

    private func content(_ booking: Booking) -> some View {
        let kind = BookingKind(rawValue: booking.kind)
        return ScrollView {
            VStack(alignment: .leading, spacing: JolSpacing.lg) {
                HStack(spacing: JolSpacing.sm) {
                    Image(systemName: BookingSheet.statusSymbol(booking.status))
                        .font(.title)
                        .foregroundStyle(BookingStatusLabel.color(booking.status))
                        .accessibilityHidden(true)
                    Text(BookingSheet.statusText(booking.status))
                        .font(JolFont.title)
                        .accessibilityAddTraits(.isHeader)
                        .accessibilityIdentifier("booking-detail-status")
                }
                VStack(alignment: .leading, spacing: JolSpacing.sm) {
                    Text(verbatim: booking.place?.name ?? "—").font(JolFont.headline)
                    if let kind { Text(BookingSheet.title(kind)).foregroundStyle(JolColor.textSecondary) }
                    if let when = BookingFormatting.when(booking, locale: locale) {
                        Label { Text(verbatim: when) } icon: { Image(systemName: "calendar") }
                            .accessibilityIdentifier("booking-detail-when")
                    }
                    if let party = booking.partySize, let kind {
                        Label {
                            Text(BookingSheet.partyLabel(kind)) + Text(verbatim: ": \(party)")
                        } icon: {
                            Image(systemName: "person.2")
                        }
                    }
                    if let note = booking.note, !note.isEmpty {
                        Text(verbatim: note).font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
                    }
                }
                if let problem = model.cancelProblem {
                    Text(Self.problemText(problem))
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.danger)
                        .accessibilityIdentifier("booking-cancel-problem")
                }
                if booking.canCancel { cancelButton }
                Text("Nothing was paid. The venue confirms the details with you.")
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.textSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(JolSpacing.lg)
        }
    }

    private var cancelButton: some View {
        let busy = model.cancellingID == bookingID
        return Button(role: .destructive) { confirmCancel = true } label: {
            HStack {
                if busy { ProgressView() }
                Text(busy ? "Cancelling…" : "Cancel booking").font(JolFont.headline)
            }
            .foregroundStyle(JolColor.danger)
            .frame(maxWidth: .infinity, minHeight: JolTarget.minimum)
        }
        .buttonStyle(.bordered)
        .tint(JolColor.danger)
        .disabled(busy)
        .confirmationDialog("Cancel this booking?", isPresented: $confirmCancel, titleVisibility: .visible) {
            Button("Cancel booking", role: .destructive) {
                Task { await model.cancel(bookingID) }
            }
            .accessibilityIdentifier("booking-cancel-confirm")
            Button("Keep booking", role: .cancel) {}
                .accessibilityIdentifier("booking-cancel-keep")
        } message: {
            Text("The venue will be told that you are not coming.")
        }
        .accessibilityIdentifier("booking-cancel")
    }

    static func problemText(_ problem: MyBookingsModel.CancelProblem) -> LocalizedStringKey {
        switch problem {
        case .notCancellable:
            "This booking can't be cancelled any more: it is already cancelled or over. Contact the venue."
        case .network: "No connection. Your booking was not cancelled. Try again."
        case .other: "Couldn't cancel the booking. Try again."
        }
    }
}
