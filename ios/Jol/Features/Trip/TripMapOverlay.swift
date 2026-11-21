import SwiftUI

/// The full route map on top of the main map (SSOT §11.3): close button and day switcher at the top, the day's
/// stops and legs in a panel at the bottom, budget summary with the over-budget choice, transport options of a leg.
/// The map itself (numbered stops, legs in the day's colour) is drawn by `MapScreen`.
struct TripMapOverlay: View {
    let model: TripMapModel
    /// The panel hides while a place or event card is up (it has its own sheet).
    let panelVisible: Bool
    let panelHeight: CGFloat
    let onSelectPlace: (TripPlace) -> Void
    @Environment(\.locale) private var locale
    @Environment(AppContainer.self) private var container
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var budgetOpen = false

    var body: some View {
        VStack(spacing: JolSpacing.sm) {
            topBar
                .dynamicTypeSize(...DynamicTypeSize.accessibility1)
            Spacer(minLength: 0)
            attribution
                .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
            if panelVisible { panel }
        }
        .padding(.bottom, panelVisible ? 0 : 44)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("trip-map")
        .sheet(isPresented: $budgetOpen) {
            TripBudgetSheet(model: model)
        }
        .sheet(item: legBinding) { leg in
            TripLegSheet(model: model, leg: leg)
        }
        .alert(
            Text("Remove a must-have?"),
            isPresented: Binding(get: { model.pendingRemoval != nil }, set: { if !$0 { model.cancelRemoval() } })
        ) {
            Button("Remove anyway", role: .destructive) { model.confirmRemoval() }
                .accessibilityIdentifier("trip-remove-confirm")
            Button("Keep it", role: .cancel) { model.cancelRemoval() }
                .accessibilityIdentifier("trip-remove-keep")
        } message: {
            Text("\(model.pendingRemoval?.name ?? "") is something you asked for. Remove it anyway?")
        }
    }

    private var legBinding: Binding<TripLeg?> {
        Binding(
            get: { model.selectedLegID.flatMap { model.leg(id: $0) } },
            set: { if $0 == nil { model.clearLeg() } }
        )
    }

    // MARK: - Top

    private var topBar: some View {
        HStack(spacing: JolSpacing.sm) {
            Button { model.close() } label: {
                Image(systemName: "xmark")
                    .font(.body.weight(.semibold))
                    .frame(width: 44, height: 44)
                    .background(.thinMaterial, in: Circle())
                    .foregroundStyle(JolColor.textPrimary)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(Text("Close the route map"))
            .accessibilityIdentifier("trip-map-close")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: JolSpacing.xs) {
                    ForEach(Array(model.days.enumerated()), id: \.element.id) { index, day in
                        dayChip(index: index, day: day)
                    }
                }
            }
            .accessibilityIdentifier("trip-day-switcher")
        }
        .padding(.horizontal, JolSpacing.sm)
        .padding(.top, JolSpacing.sm)
    }

    private func dayChip(index: Int, day: TripDay) -> some View {
        let selected = index == model.dayIndex
        return Button { model.selectDay(index) } label: {
            HStack(spacing: JolSpacing.xs) {
                Circle().fill(Color(TripMapModel.dayColor(index))).frame(width: 10, height: 10)
                    .accessibilityHidden(true)
                Text("Day \(index + 1)").font(JolFont.callout.weight(.semibold))
                Text(verbatim: TripFormatting.dayDate(day.date, locale: locale)).font(JolFont.caption)
            }
            .padding(.horizontal, JolSpacing.md)
            .padding(.vertical, JolSpacing.sm)
            .frame(minHeight: JolTarget.minimum)
            .foregroundStyle(JolColor.textPrimary)
            .background(
                selected ? AnyShapeStyle(JolColor.surfaceElevated) : AnyShapeStyle(.thinMaterial), in: Capsule()
            )
            .overlay(Capsule().stroke(selected ? Color(TripMapModel.dayColor(index)) : .clear, lineWidth: 2))
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
        .accessibilityIdentifier("trip-day-chip-\(index + 1)")
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
            .accessibilityHidden(true)
    }

    // MARK: - Panel

    private var panel: some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            switch model.phase {
            case .idle, .loading:
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                    .accessibilityLabel(Text("Loading"))
                    .accessibilityIdentifier("trip-loading")
            case .failed:
                VStack(spacing: JolSpacing.md) {
                    Text("Couldn't load the route.").foregroundStyle(JolColor.textSecondary)
                    Button("Try again") { model.retry() }.accessibilityIdentifier("trip-retry")
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            case .loaded:
                loadedPanel
            }
        }
        .padding(.horizontal, JolSpacing.lg)
        .padding(.top, JolSpacing.md)
        .frame(maxWidth: .infinity)
        .frame(height: typeSize.isAccessibilitySize ? panelHeight / Self.panelFraction * 0.7 : panelHeight)
        .background(
            JolColor.surfaceElevated.clipShape(UnevenRoundedRectangle(
                topLeadingRadius: JolRadius.xl, topTrailingRadius: JolRadius.xl
            )).ignoresSafeArea(edges: .bottom)
        )
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("trip-panel")
    }

    /// Share of the screen the panel takes; `HomeScreen` keeps the map's camera above it.
    static let panelFraction: CGFloat = 0.45

    @ViewBuilder private var loadedPanel: some View {
        if let day = model.day {
            if typeSize.isAccessibilitySize {
                // Large type: header, warnings and stops scroll together so the list is never squeezed out.
                ScrollView {
                    VStack(alignment: .leading, spacing: JolSpacing.sm) {
                        dayHeader(day)
                        warnings
                        TripDayListView(model: model, day: day, onSelectPlace: onSelectPlace)
                    }
                }
                .accessibilityIdentifier("trip-day-list")
            } else {
                dayHeader(day)
                warnings
                ScrollView {
                    TripDayListView(model: model, day: day, onSelectPlace: onSelectPlace)
                }
                .accessibilityIdentifier("trip-day-list")
            }
        }
    }

    private func dayHeader(_ day: TripDay) -> some View {
        AdaptiveStack(rowAlignment: .firstTextBaseline) {
            HStack(alignment: .firstTextBaseline) {
                Text("Day \(model.dayIndex + 1)")
                    .font(JolFont.headline)
                    .foregroundStyle(Color(model.dayColor))
                    .accessibilityIdentifier("trip-day-title")
                    .accessibilityAddTraits(.isHeader)
                Text(verbatim: TripFormatting.dayDate(day.date, locale: locale))
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.textSecondary)
            }
            if !typeSize.isAccessibilitySize { Spacer() }
            budgetChip
        }
    }

    private var budgetChip: some View {
        let over = model.trip?.budgetDetail?.isOver ?? model.trip?.budget?.isOver ?? false
        let total = model.trip?.totalCostKzt ?? model.trip?.budget?.totalKzt
        return Button { budgetOpen = true } label: {
            HStack(spacing: JolSpacing.xs) {
                if over { Image(systemName: "exclamationmark.triangle.fill").accessibilityHidden(true) }
                if let total {
                    Text(verbatim: TripFormatting.kzt(total, locale: locale))
                } else {
                    Text("Budget")
                }
            }
            .font(JolFont.callout.weight(.semibold))
            .foregroundStyle(over ? JolColor.danger : JolColor.textPrimary)
            .padding(.horizontal, JolSpacing.md)
            .padding(.vertical, JolSpacing.xs + 2)
            .frame(minHeight: JolTarget.minimum)
            .background(JolColor.surface, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(budgetLabel(total: total, over: over))
        .accessibilityHint(Text("Opens the budget"))
        .accessibilityIdentifier("trip-budget-chip")
    }

    private func budgetLabel(total: Int?, over: Bool) -> Text {
        var parts = [Text("Budget")]
        if let total { parts.append(Text(verbatim: TripFormatting.kzt(total, locale: locale))) }
        if over { parts.append(Text("Over budget")) }
        return Text.spoken(parts)
    }

    @ViewBuilder private var warnings: some View {
        if let trip = model.trip, trip.budgetDetail?.isOver ?? trip.budget?.isOver ?? false {
            Button { budgetOpen = true } label: {
                AdaptiveStack(spacing: JolSpacing.sm) {
                    Image(systemName: "exclamationmark.triangle.fill").accessibilityHidden(true)
                    overText(trip).multilineTextAlignment(.leading)
                    Spacer(minLength: 0)
                    if trip.needsBudgetChoice { Text("Choose").fontWeight(.semibold) }
                }
                .font(JolFont.caption)
                .foregroundStyle(JolColor.danger)
                .padding(JolSpacing.sm)
                .background(JolColor.danger.opacity(0.1), in: RoundedRectangle(cornerRadius: JolRadius.md))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("trip-over-budget")
        }
        if let problem = model.problem {
            Button { model.dismissProblem() } label: {
                problemText(problem)
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.danger)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("trip-problem")
        }
    }

    private func overText(_ trip: TripOverview) -> Text {
        let shortfall = trip.budgetDetail?.shortfallKzt ?? trip.budget?.shortfallKzt ?? 0
        let amount = TripFormatting.kzt(shortfall, locale: locale)
        return shortfall > 0 ? Text("Over budget by \(amount)") : Text("Over budget")
    }

    private func problemText(_ problem: TripMapModel.Problem) -> Text {
        switch problem {
        case .network: Text("No connection. Try again.")
        case .outdated: Text("The plan has changed, so it was reloaded.")
        case .server(let message): Text(verbatim: message)
        }
    }
}
