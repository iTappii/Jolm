import SwiftUI

/// Transport options of one leg (SSOT §5.3): one row per mode with time, price and distance; tapping a row makes it
/// the leg's way (`POST /v1/trips/{id}/legs/{leg}/mode`). A slow way may arrive after the next stop starts: the
/// server says by how much (`late_by_s`) and the sheet shows it.
struct TripLegSheet: View {
    let model: TripMapModel
    let leg: TripLeg
    @Environment(AppContainer.self) private var container
    @Environment(\.dismiss) private var dismiss

    private var language: String { container.language.code }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: JolSpacing.md) {
                    header
                    if let late = model.lateBy[leg.id], late > 0 {
                        Label {
                            let late = TripFormatting.minutes(late, language: language)
                            Text("This way gets you there \(late) after the next stop starts.")
                        } icon: {
                            Image(systemName: "clock.badge.exclamationmark")
                        }
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.danger)
                        .padding(JolSpacing.md)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(JolColor.danger.opacity(0.1), in: RoundedRectangle(cornerRadius: JolRadius.md))
                        .accessibilityIdentifier("trip-leg-late")
                    }
                    if let problem = model.problem, problem != .outdated {
                        Text(verbatim: problemText(problem))
                            .font(JolFont.caption)
                            .foregroundStyle(JolColor.danger)
                            .accessibilityIdentifier("trip-leg-problem")
                    }
                    if choices.isEmpty {
                        Text("No ways to get there were calculated for this leg.")
                            .font(JolFont.callout)
                            .foregroundStyle(JolColor.textSecondary)
                            .accessibilityIdentifier("trip-leg-empty")
                    }
                    ForEach(choices, id: \.mode) { option in row(option) }
                }
                .padding(JolSpacing.lg)
            }
            .navigationTitle(Text("Getting there"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("trip-leg-done")
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationBackground(JolColor.surfaceElevated)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("trip-leg-sheet")
    }

    /// The leg as it is now (a choice replaces it in the model).
    private var current: TripLeg { model.leg(id: leg.id) ?? leg }
    private var choices: [DirectionOption] { current.modeChoices }

    private func problemText(_ problem: TripMapModel.Problem) -> String {
        switch problem {
        case .network: L10n.string("No connection. Try again.", language: language)
        case .outdated: L10n.string("The plan has changed, so it was reloaded.", language: language)
        case .server(let message): message
        }
    }

    private var header: some View {
        let ends = model.endpoints(of: current)
        return VStack(alignment: .leading, spacing: JolSpacing.xxs) {
            if let from = ends.from, let to = ends.to {
                Text(verbatim: "\(from.place.name) → \(to.place.name)")
                    .font(JolFont.headline)
                    .accessibilityIdentifier("trip-leg-title")
            }
            if current.estimated == true {
                Text("Times are estimated.").font(JolFont.caption).foregroundStyle(JolColor.textSecondary)
            }
        }
    }

    private func row(_ option: DirectionOption) -> some View {
        let chosen = current.activeOption?.mode == option.mode
        return Button { model.chooseMode(leg: current, mode: option.mode) } label: {
            HStack(spacing: JolSpacing.md) {
                Image(systemName: DirectionsFormatting.symbol(option.mode))
                    .font(.title3)
                    .frame(width: 40, height: 40)
                    .background(chosen ? JolColor.brand : JolColor.surface, in: Circle())
                    .foregroundStyle(chosen ? JolColor.onBrand : JolColor.textPrimary)
                VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                    HStack(spacing: JolSpacing.xs) {
                        Text(DirectionsFormatting.title(option.mode))
                        if let ref = option.transitRef { Text(verbatim: ref).foregroundStyle(JolColor.textSecondary) }
                    }
                    .font(JolFont.headline)
                    HStack(spacing: JolSpacing.xs) {
                        if option.recommended {
                            Text("Recommended").foregroundStyle(JolColor.brand).fontWeight(.semibold)
                        }
                        Text(verbatim: DirectionsFormatting.distance(option.distanceM, language: language))
                            .foregroundStyle(JolColor.textSecondary)
                    }
                    .font(JolFont.caption)
                }
                Spacer(minLength: JolSpacing.sm)
                VStack(alignment: .trailing, spacing: JolSpacing.xxs) {
                    Text(verbatim: DirectionsFormatting.duration(option, language: language)).font(JolFont.headline)
                    Text(verbatim: DirectionsFormatting.price(option, language: language))
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.textSecondary)
                }
                if chosen {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(JolColor.brand)
                }
            }
            .foregroundStyle(JolColor.textPrimary)
            .padding(JolSpacing.md)
            .background(JolColor.surface.opacity(chosen ? 1 : 0.6), in: RoundedRectangle(cornerRadius: JolRadius.lg))
            .overlay(
                RoundedRectangle(cornerRadius: JolRadius.lg).stroke(chosen ? JolColor.brand : .clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .disabled(model.isWorking)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(chosen ? [.isButton, .isSelected] : .isButton)
        .accessibilityIdentifier("trip-leg-option-\(option.mode.rawValue)")
    }
}
