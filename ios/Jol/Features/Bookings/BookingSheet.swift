import SwiftUI

/// The booking request of a place with a partner (Ш-49, SSOT §9): kind, date and time, party size → the server asks
/// the partner. The answer is shown as a status; nothing is paid in the app.
struct BookingSheet: View {
    let place: PlaceSummary
    let kinds: [BookingKind]
    @Environment(AppContainer.self) private var container
    @Environment(\.dismiss) private var dismiss
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var kind: BookingKind
    @State private var start = BookingSheet.defaultStart(hour: 19)
    @State private var end = BookingSheet.defaultStart(hour: 12, daysAhead: 2)
    @State private var party = 2
    @State private var note = ""

    init(place: PlaceSummary, kinds: [BookingKind]) {
        self.place = place
        self.kinds = kinds
        _kind = State(initialValue: kinds.first ?? .table)
    }

    private var model: BookingModel { container.bookings }

    var body: some View {
        NavigationStack {
            Group {
                if let booking = model.booking {
                    result(booking)
                } else {
                    form
                }
            }
            .navigationTitle(Text("Book"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(model.booking == nil ? "Cancel" : "Done") { dismiss() }
                        .accessibilityIdentifier("booking-close")
                }
            }
        }
        .presentationDetents([.large])
        .presentationBackground(JolColor.surfaceElevated)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("booking-sheet")
        .onAppear { model.reset() }
    }

    // MARK: - Form

    private var form: some View {
        Form {
            Section {
                Text(verbatim: place.name).font(JolFont.headline)
            }
            if kinds.count > 1 {
                Section {
                    kindPicker
                        .accessibilityIdentifier("booking-kind")
                }
            }
            Section {
                if kind.needsStart {
                    DatePicker(
                        kind == .room ? "Check-in" : "Date and time", selection: $start, in: Date()...,
                        displayedComponents: kind == .room ? [.date] : [.date, .hourAndMinute]
                    )
                    .accessibilityIdentifier("booking-start")
                }
                if kind.needsEnd {
                    DatePicker("Check-out", selection: $end, in: start..., displayedComponents: [.date])
                        .accessibilityIdentifier("booking-end")
                }
                Stepper(value: $party, in: 1...20) {
                    HStack {
                        Text(Self.partyLabel(kind))
                        Spacer()
                        Text("\(party)").foregroundStyle(JolColor.textSecondary)
                            .accessibilityIdentifier("booking-party-value")
                    }
                }
                .accessibilityIdentifier("booking-party")
                TextField("Note for the venue (optional)", text: $note)
                    .accessibilityIdentifier("booking-note")
            }
            .environment(\.timeZone, PlaceFormatting.almaty)
            Section {
                if case .failed(let failure) = model.state {
                    Text(Self.failureText(failure))
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.danger)
                        .accessibilityIdentifier("booking-error")
                }
                Button { submit() } label: {
                    HStack {
                        Spacer()
                        if model.isSending { ProgressView() } else { Text("Send request").font(JolFont.headline) }
                        Spacer()
                    }
                }
                .disabled(model.isSending)
                .accessibilityIdentifier("booking-submit")
            } footer: {
                Text("This is a request to the venue. Nothing is paid in the app.")
            }
        }
        .onChange(of: kind) { _, _ in model.edit() }
    }

    /// Segments for few/short options; a menu at accessibility sizes, where segments would be cut off.
    @ViewBuilder private var kindPicker: some View {
        let picker = Picker("What to book", selection: $kind) {
            ForEach(kinds) { item in Text(Self.title(item)).tag(item) }
        }
        if typeSize.isAccessibilitySize {
            picker.pickerStyle(.menu)
        } else {
            picker.pickerStyle(.segmented)
        }
    }

    private func submit() {
        model.submit(BookingRequest(
            placeID: place.id, kind: kind, partySize: party,
            startsAt: kind.needsStart ? Self.iso(kind == .room ? Self.at(start, hour: 14) : start) : nil,
            endsAt: kind.needsEnd ? Self.iso(Self.at(max(end, start), hour: 12)) : nil,
            note: note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ? nil : note.trimmingCharacters(in: .whitespacesAndNewlines)
        ))
    }

    // MARK: - Result

    private func result(_ booking: Booking) -> some View {
        ScrollView { VStack(spacing: JolSpacing.lg) {
            Image(systemName: Self.statusSymbol(booking.status))
                .font(.system(size: 56))
                .foregroundStyle(Self.statusColor(booking.status))
                .accessibilityHidden(true)
            Text(Self.statusText(booking.status))
                .font(JolFont.title)
                .multilineTextAlignment(.center)
                .accessibilityIdentifier("booking-status")
            VStack(spacing: JolSpacing.xs) {
                Text(verbatim: booking.place?.name ?? place.name).font(JolFont.headline)
                Text(Self.title(BookingKind(rawValue: booking.kind) ?? kind))
                    .foregroundStyle(JolColor.textSecondary)
                if let party = booking.partySize {
                    (Text(Self.partyLabel(BookingKind(rawValue: booking.kind) ?? kind)) + Text(verbatim: ": \(party)"))
                        .foregroundStyle(JolColor.textSecondary)
                }
            }
            if booking.status == "pending" {
                Button("Check the status") { model.refresh() }
                    .frame(minHeight: JolTarget.minimum)
                    .accessibilityIdentifier("booking-refresh")
            }
            Text("Nothing was paid. The venue confirms the details with you.")
                .font(JolFont.caption)
                .foregroundStyle(JolColor.textSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(JolSpacing.xl) }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("booking-result")
    }

    // MARK: - Text

    static func title(_ kind: BookingKind) -> LocalizedStringKey {
        switch kind {
        case .table: "Table"
        case .room: "Room"
        case .ticket: "Tickets"
        case .food: "Food order"
        }
    }

    static func partyLabel(_ kind: BookingKind) -> LocalizedStringKey {
        switch kind {
        case .table, .food: "People"
        case .room: "Guests"
        case .ticket: "Tickets"
        }
    }

    static func statusText(_ status: String) -> LocalizedStringKey {
        switch status {
        case "confirmed": "Confirmed"
        case "pending": "Waiting for the venue"
        case "declined": "The venue declined"
        case "cancelled": "Cancelled"
        default: "Couldn't reach the venue"
        }
    }

    static func statusSymbol(_ status: String) -> String {
        switch status {
        case "confirmed": "checkmark.circle.fill"
        case "pending": "clock.fill"
        default: "xmark.octagon.fill"
        }
    }

    static func statusColor(_ status: String) -> Color {
        switch status {
        case "confirmed": .green
        case "pending": JolColor.brand
        default: JolColor.danger
        }
    }

    static func failureText(_ failure: BookingModel.Failure) -> LocalizedStringKey {
        switch failure {
        case .notSupported: "This venue doesn't take this kind of request."
        case .unavailable: "The venue can't take this. Try another time or party size."
        case .invalid: "Check the date: it must be in the future."
        case .rateLimited: "Too many requests today. Try again later."
        case .signedOut: "Sign in to book."
        case .network: "No connection. Try again."
        case .other: "Couldn't send the request. Try again."
        }
    }

    // MARK: - Dates (Almaty)

    private static var calendar: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = PlaceFormatting.almaty
        return calendar
    }

    static func defaultStart(hour: Int, daysAhead: Int = 1) -> Date {
        let day = calendar.date(byAdding: .day, value: daysAhead, to: Date()) ?? Date()
        return calendar.date(bySettingHour: hour, minute: 0, second: 0, of: day) ?? day
    }

    static func at(_ date: Date, hour: Int) -> Date {
        calendar.date(bySettingHour: hour, minute: 0, second: 0, of: date) ?? date
    }

    /// ISO time with the Almaty offset (`2026-12-05T19:00:00+05:00`).
    static func iso(_ date: Date) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.timeZone = PlaceFormatting.almaty
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.string(from: date)
    }
}
