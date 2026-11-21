import SwiftUI

/// Crowd on the place card (Ш-47, SSOT §7.3): the statistics block — only when the server sent `crowd` — and the two
/// ways to add to it: «I'm here» and «Busy / Normal / Quiet». Both send the CURRENT location (one fix, when-in-use).
struct CrowdSection: View {
    let place: PlaceSummary
    let crowd: CrowdBlock?
    @Environment(AppContainer.self) private var container
    @Environment(\.openURL) private var openURL

    private var model: CrowdModel { container.crowd }

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            if let crowd { stats(crowd) }
            actions
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Statistics

    private func stats(_ crowd: CrowdBlock) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.xs) {
            Text("Crowd").font(JolFont.headline)
            if let now = crowd.now {
                Label {
                    Text(Self.nowText(now.label))
                } icon: {
                    Image(systemName: Self.symbol(now.label))
                }
                .font(JolFont.callout.weight(.semibold))
                .foregroundStyle(Self.color(now.label))
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Text(Self.nowText(now.label)))
                .accessibilityIdentifier("place-crowd-now")
            } else {
                Text("No data for this hour yet")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityIdentifier("place-crowd-no-hour")
            }
            if !crowd.today.isEmpty { chart(crowd.today) }
            Text("Based on \(crowd.samples) reports")
                .font(JolFont.caption)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("place-crowd-samples")
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("place-crowd")
    }

    /// Bars of today's hours that have enough reports; the height is the level (0 empty … 1 packed).
    private func chart(_ hours: [CrowdHour]) -> some View {
        HStack(alignment: .bottom, spacing: 3) {
            ForEach(hours, id: \.hour) { hour in
                VStack(spacing: 2) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Self.color(hour.label))
                        .frame(height: max(4, 36 * hour.level))
                    Text("\(hour.hour)").font(.system(size: 9)).foregroundStyle(JolColor.textTertiary)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .frame(height: 52, alignment: .bottom)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("Crowd by hour today"))
        .accessibilityIdentifier("place-crowd-chart")
    }

    // MARK: - Actions

    private var actions: some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            Text("Are you here?").font(JolFont.headline)
            button(.checkIn, title: "I'm here", symbol: "location.fill", id: "place-checkin")
            Text("How crowded is it right now?").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            HStack(spacing: JolSpacing.sm) {
                ForEach(CrowdReportLevel.allCases) { level in
                    button(.report(level), title: Self.levelTitle(level), symbol: Self.levelSymbol(level),
                           id: "place-crowd-\(level.rawValue)")
                }
            }
            if model.placeID == place.id, let outcome = model.outcome { outcomeRow(outcome) }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("place-crowd-actions")
    }

    private func button(_ action: CrowdModel.Action, title: LocalizedStringKey, symbol: String, id: String)
        -> some View {
        Button { perform(action) } label: {
            HStack(spacing: JolSpacing.xs) {
                if model.working == action {
                    ProgressView()
                } else {
                    Image(systemName: symbol)
                }
                Text(title)
            }
            .font(JolFont.callout.weight(.semibold))
            .frame(maxWidth: .infinity)
            .padding(.vertical, JolSpacing.sm)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        }
        .buttonStyle(.plain)
        .foregroundStyle(JolColor.textPrimary)
        .disabled(model.isWorking)
        .accessibilityIdentifier(id)
    }

    /// A guest meets the sign-in gate first (the limits and the metric need a person, SSOT §3.2).
    private func perform(_ action: CrowdModel.Action) {
        if container.auth.isSignedIn {
            model.perform(action, placeID: place.id)
        } else {
            container.gate.requireAccount { model.perform(action, placeID: place.id) }
        }
    }

    @ViewBuilder private func outcomeRow(_ outcome: CrowdModel.Outcome) -> some View {
        let good = Self.isGood(outcome)
        VStack(alignment: .leading, spacing: JolSpacing.xs) {
            Text(Self.outcomeText(outcome))
                .font(JolFont.callout)
                .foregroundStyle(good ? Color.green : JolColor.danger)
                .accessibilityIdentifier("place-crowd-outcome")
            if outcome == .locationDenied {
                Button("Settings") {
                    if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
                }
                .font(JolFont.callout)
            }
        }
    }

    // MARK: - Text

    static func isGood(_ outcome: CrowdModel.Outcome) -> Bool {
        switch outcome {
        case .recorded, .alreadyRecorded: true
        default: false
        }
    }

    static func outcomeText(_ outcome: CrowdModel.Outcome) -> LocalizedStringKey {
        switch outcome {
        case .recorded(.checkIn): "Thanks, you're checked in."
        case .recorded(.report): "Thanks for the report."
        case .alreadyRecorded(.checkIn): "You checked in here a moment ago."
        case .alreadyRecorded(.report): "You already reported this place recently."
        case .tooFar: "You need to be within 200 m of the place."
        case .rateLimited(let seconds?): "Too many reports today. Try again in \(max(1, (seconds + 59) / 60)) min."
        case .rateLimited(nil): "Too many reports today. Try again later."
        case .locationDenied: "Allow location access to do this."
        case .locationUnavailable: "Couldn't get your location. Try again."
        case .failed: "Couldn't send. Try again."
        }
    }

    static func nowText(_ label: String) -> LocalizedStringKey {
        switch label {
        case "busy": "Busy right now"
        case "empty": "Quiet right now"
        default: "Moderately busy right now"
        }
    }

    static func levelTitle(_ level: CrowdReportLevel) -> LocalizedStringKey {
        switch level {
        case .busy: "Busy"
        case .normal: "Normal"
        case .empty: "Quiet"
        }
    }

    static func levelSymbol(_ level: CrowdReportLevel) -> String {
        switch level {
        case .busy: "person.3.fill"
        case .normal: "person.2.fill"
        case .empty: "person.fill"
        }
    }

    static func symbol(_ label: String) -> String {
        switch label {
        case "busy": "person.3.fill"
        case "empty": "person.fill"
        default: "person.2.fill"
        }
    }

    static func color(_ label: String) -> Color {
        switch label {
        case "busy": JolColor.danger
        case "empty": .green
        default: JolColor.brand
        }
    }
}
