import SwiftUI

/// Budget of the trip (SSOT §5.2): total against the budget, where the money goes and — when the plan does not fit —
/// the two ways out the server prepared. A variant that still does not fit says so (`feasible: false`).
struct TripBudgetSheet: View {
    let model: TripMapModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale
    @Environment(AppContainer.self) private var container

    var body: some View {
        NavigationStack {
            ScrollView {
                if let trip = model.trip {
                    content(trip).padding(JolSpacing.lg)
                }
            }
            .navigationTitle(Text("Trip budget"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.accessibilityIdentifier("trip-budget-done")
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationBackground(JolColor.surfaceElevated)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("trip-budget-sheet")
    }

    private var language: String { container.language.code }

    private func kzt(_ value: Int) -> String { TripFormatting.kzt(value, locale: locale) }

    private func content(_ trip: TripOverview) -> some View {
        let detail = trip.budgetDetail
        let over = detail?.isOver ?? trip.budget?.isOver ?? false
        return VStack(alignment: .leading, spacing: JolSpacing.lg) {
            summary(trip, over: over)
            if let lines = detail?.breakdown?.lines, !lines.isEmpty {
                VStack(alignment: .leading, spacing: JolSpacing.xs) {
                    ForEach(lines) { line in
                        HStack {
                            Text(LocalizedStringKey(line.label))
                            Spacer()
                            Text(verbatim: kzt(line.value))
                        }
                        .font(JolFont.callout)
                    }
                }
                .accessibilityIdentifier("trip-budget-breakdown")
            }
            if over || trip.budgetChoice != nil { overBudget(trip) }
            if let problem = model.problem, problem != .outdated {
                Text("Couldn't apply the choice. Try again.")
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.danger)
                    .accessibilityIdentifier("trip-budget-problem")
            }
        }
    }

    private func summary(_ trip: TripOverview, over: Bool) -> some View {
        let detail = trip.budgetDetail
        let total = trip.totalCostKzt ?? detail?.totalKzt
        let budget = trip.budgetKzt ?? detail?.budgetKzt
        let shortfall = detail?.shortfallKzt ?? trip.budget?.shortfallKzt ?? 0
        return VStack(alignment: .leading, spacing: JolSpacing.xs) {
            if let total {
                Text(verbatim: kzt(total)).font(JolFont.largeTitle).accessibilityIdentifier("trip-budget-total")
            }
            if let budget {
                Text("of \(kzt(budget)) for the whole trip")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.textSecondary)
            }
            if over {
                Label {
                    Text(shortfall > 0 ? "Over budget by \(kzt(shortfall))" : "Over budget")
                } icon: {
                    Image(systemName: "exclamationmark.triangle.fill")
                }
                .font(JolFont.headline)
                .foregroundStyle(JolColor.danger)
                .accessibilityIdentifier("trip-budget-over")
            } else if let remaining = detail?.remainingKzt ?? trip.budget?.remainingKzt {
                Text("\(kzt(remaining)) left").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            }
        }
    }

    // MARK: - Over budget

    @ViewBuilder private func overBudget(_ trip: TripOverview) -> some View {
        let detail = trip.budgetDetail
        if let choice = trip.budgetChoice {
            Text(chosenText(choice))
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("trip-budget-chosen")
        } else if let detail, detail.hasVariants {
            Text("Two ways to fit the budget").font(JolFont.headline)
            if let drop = detail.dropPlaces {
                variantCard(
                    id: "drop_places", title: "Remove some places", variant: drop,
                    lines: drop.removed.map { "− \($0.name)" }
                )
            }
            if let cheaper = detail.cheaper {
                variantCard(
                    id: "cheaper", title: "Cheaper alternatives", variant: cheaper,
                    lines: cheaper.swaps.map { swap in
                        swap.to.map { "\(swap.from.name) → \($0.name)" } ?? "− \(swap.from.name)"
                    } + (cheaper.lodgingChanged ? [L10n.string("Cheaper lodging", language: language)] : [])
                )
            }
            Button { model.choose(budget: "keep") } label: {
                Text("Keep the plan as it is")
                    .font(JolFont.callout.weight(.semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, JolSpacing.md)
                    .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            }
            .buttonStyle(.plain)
            .foregroundStyle(JolColor.textPrimary)
            .disabled(model.isWorking)
            .accessibilityIdentifier("trip-budget-keep")
        }
    }

    private func chosenText(_ choice: String) -> LocalizedStringKey {
        switch choice {
        case "drop_places": "You chose to remove some places."
        case "cheaper": "You chose cheaper alternatives."
        default: "You kept the plan as it is."
        }
    }

    private func variantCard(
        id: String, title: LocalizedStringKey, variant: BudgetVariant, lines: [String]
    ) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            Text(title).font(JolFont.headline)
            HStack {
                Text("Saves \(kzt(variant.savesKzt))")
                Spacer()
                Text("Total \(kzt(variant.totalKzt))")
            }
            .font(JolFont.callout)
            ForEach(lines.filter { !$0.isEmpty }, id: \.self) { line in
                Text(verbatim: line).font(JolFont.caption).foregroundStyle(JolColor.textSecondary)
            }
            if !variant.feasible {
                Label("Still \(kzt(variant.shortfallKzt)) over budget", systemImage: "exclamationmark.triangle.fill")
                    .font(JolFont.caption.weight(.semibold))
                    .foregroundStyle(JolColor.danger)
                    .accessibilityIdentifier("trip-budget-infeasible-\(id)")
            }
            Button { model.choose(budget: id) } label: {
                Text("Choose this")
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.onBrand)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, JolSpacing.md)
                    .background(JolColor.brand, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            }
            .buttonStyle(.plain)
            .disabled(model.isWorking)
            .accessibilityIdentifier("trip-budget-choose-\(id)")
        }
        .padding(JolSpacing.md)
        .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("trip-budget-variant-\(id)")
    }
}
