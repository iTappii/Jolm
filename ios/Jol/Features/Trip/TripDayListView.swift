import SwiftUI

/// The stops of one day with the legs between them (full route map panel): tap a stop for its card, a leg for its
/// transport options, the minus button removes a stop.
struct TripDayListView: View {
    let model: TripMapModel
    let day: TripDay
    /// Position of the day in the trip: the colour of its badges, and (in the "All days" list) the identifiers.
    var dayIndex: Int?
    /// "All days" lists every day, so the row identifiers carry the day number.
    var identifiesDay = false
    let onSelectPlace: (TripPlace) -> Void
    @Environment(\.locale) private var locale
    @Environment(AppContainer.self) private var container
    @ScaledMetric(relativeTo: .callout) private var badgeSize: CGFloat = 28

    private var shownIndex: Int { dayIndex ?? model.dayIndex }

    private func suffix(_ number: Int) -> String {
        identifiesDay ? "d\(shownIndex + 1)-\(number)" : "\(number)"
    }

    var body: some View {
        dayList(day)
    }

    private func dayList(_ day: TripDay) -> some View {
        LazyVStack(alignment: .leading, spacing: JolSpacing.xs) {
            transferBanner(day)
            if day.items.isEmpty && !day.isTransfer {
                Text("Free day")
                    .foregroundStyle(JolColor.textSecondary)
                    .padding(.vertical, JolSpacing.md)
                    .accessibilityIdentifier("trip-free-day")
            }
            ForEach(Array(day.items.enumerated()), id: \.element.id) { index, item in
                if let leg = day.leg(to: item) { legRow(leg) }
                stopRow(item, number: index + 1)
            }
            overnightLine(day)
        }
        .padding(.bottom, JolSpacing.xl)
    }

    // MARK: - Intercity (Ш-62)

    /// «Travel to Turkestan» above a transfer day's list.
    @ViewBuilder private func transferBanner(_ day: TripDay) -> some View {
        if let title = IntercityFormatting.transferTitle(day, language: container.language.code) {
            let mode = day.intercityLeg?.intercity?.mode
            HStack(spacing: JolSpacing.sm) {
                Image(systemName: IntercityFormatting.symbol(mode)).accessibilityHidden(true)
                Text(verbatim: title).font(JolFont.callout.weight(.semibold))
            }
            .foregroundStyle(Color(TripMapModel.dayColor(shownIndex)))
            .padding(.vertical, JolSpacing.xs)
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.isHeader)
            .accessibilityIdentifier(identifiesDay ? "trip-transfer-d\(shownIndex + 1)" : "trip-transfer")
        }
    }

    /// «Overnight: Saty» under the day's last stop.
    @ViewBuilder private func overnightLine(_ day: TripDay) -> some View {
        if let line = IntercityFormatting.overnightLine(day, language: container.language.code) {
            HStack(spacing: JolSpacing.sm) {
                Image(systemName: "moon.stars.fill").accessibilityHidden(true)
                Text(verbatim: line).font(JolFont.callout)
            }
            .foregroundStyle(JolColor.textSecondary)
            .padding(.vertical, JolSpacing.xs)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier(identifiesDay ? "trip-overnight-d\(shownIndex + 1)" : "trip-overnight")
        }
    }

    /// A leg between two cities: the way, the approximate time and the price range.
    private func intercityRow(_ leg: TripLeg, _ info: IntercityInfo) -> some View {
        let language = container.language.code
        return Button { model.selectLeg(leg.id) } label: {
            HStack(spacing: JolSpacing.sm) {
                Image(systemName: IntercityFormatting.symbol(info.mode))
                    .frame(width: 28)
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                    HStack(spacing: JolSpacing.xs) {
                        Text(verbatim: IntercityFormatting.title(info.mode, language: language))
                            .fontWeight(.semibold)
                        if let seconds = leg.travelS {
                            Text(verbatim: "· " + IntercityFormatting.duration(seconds: seconds, language: language))
                        }
                    }
                    HStack(spacing: JolSpacing.xs) {
                        if let price = IntercityFormatting.priceRange(info, locale: locale) { Text(verbatim: price) }
                        if info.approximate { Text("Approximate") }
                    }
                }
                Spacer()
                if !model.isSavedCopy {
                    Image(systemName: "chevron.right").font(.caption).foregroundStyle(JolColor.textTertiary)
                        .accessibilityHidden(true)
                }
            }
            .font(JolFont.caption)
            .foregroundStyle(JolColor.textSecondary)
            .padding(.vertical, JolSpacing.xs)
            .frame(minHeight: JolTarget.minimum)
            .padding(.horizontal, JolSpacing.sm)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(verbatim: IntercityFormatting.spoken(leg, language: language) ?? ""))
        .accessibilityHint(Text("Shows the details"))
        .accessibilityIdentifier("trip-intercity-leg")
    }

    private func stopRow(_ item: TripDayItem, number: Int) -> some View {
        AdaptiveStack(spacing: JolSpacing.xs) {
            Button { onSelectPlace(item.place) } label: {
                AdaptiveStack(spacing: JolSpacing.md) {
                    Text("\(number)")
                        .font(JolFont.callout.weight(.bold))
                        .foregroundStyle(JolColor.onBrand)
                        .frame(width: badgeSize, height: badgeSize)
                        .background(Color(TripMapModel.dayColor(shownIndex)), in: Circle())
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                        HStack(spacing: JolSpacing.xs) {
                            Text(verbatim: item.place.name).font(JolFont.body.weight(.semibold))
                            if item.mustHave == true {
                                Image(systemName: "star.fill").font(.caption).foregroundStyle(JolColor.brand)
                                    .accessibilityLabel(Text("Must-have"))
                            }
                        }
                        stopCaption(item)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .foregroundStyle(JolColor.textPrimary)
            .accessibilityElement(children: .combine)
            .accessibilityHint(Text("Opens the place card"))
            .accessibilityIdentifier("trip-stop-\(suffix(number))")
            if !model.isSavedCopy { actionButtons(item, number: number) }
        }
        .padding(.vertical, JolSpacing.xs)
    }

    /// Replace and remove, 44 pt each; they sit next to the stop (side by side, below it at large type).
    private func actionButtons(_ item: TripDayItem, number: Int) -> some View {
        HStack(spacing: 0) {
            Button { model.beginReplace(item) } label: {
                Image(systemName: "arrow.triangle.2.circlepath")
                    .font(.title3)
                    .foregroundStyle(JolColor.textSecondary)
                    .frame(width: JolTarget.minimum, height: JolTarget.minimum)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(model.isWorking)
            .accessibilityLabel(Text("Replace this place"))
            .accessibilityValue(Text(verbatim: item.place.name))
            .accessibilityIdentifier("trip-stop-replace-\(suffix(number))")
            Button { model.remove(item) } label: {
                Image(systemName: "minus.circle")
                    .font(.title3)
                    .foregroundStyle(JolColor.textSecondary)
                    .frame(width: JolTarget.minimum, height: JolTarget.minimum)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(model.isWorking)
            .accessibilityLabel(Text("Remove from the route"))
            .accessibilityValue(Text(verbatim: item.place.name))
            .accessibilityIdentifier("trip-stop-remove-\(suffix(number))")
        }
    }

    private func stopCaption(_ item: TripDayItem) -> some View {
        AdaptiveStack(spacing: JolSpacing.xs) {
            if let time = item.startTime {
                Text(verbatim: item.endTime.map { "\(time)–\($0)" } ?? time).monospacedDigit()
            }
            if let name = item.place.categoryName ?? item.place.category { Text(verbatim: "· \(name)") }
            if let cost = item.estCostKzt, cost > 0 { Text(verbatim: "· \(TripFormatting.kzt(cost, locale: locale))") }
            if item.rainExposed == true {
                Image(systemName: "cloud.rain").accessibilityLabel(Text("Open air"))
            }
        }
        .font(JolFont.caption)
        .foregroundStyle(JolColor.textSecondary)
    }

    @ViewBuilder private func legRow(_ leg: TripLeg) -> some View {
        if let info = leg.intercity {
            intercityRow(leg, info)
        } else {
            routeLegRow(leg)
        }
    }

    private func routeLegRow(_ leg: TripLeg) -> some View {
        let option = leg.activeOption
        let late = model.lateBy[leg.id] ?? 0
        return Button { model.selectLeg(leg.id) } label: {
            HStack(spacing: JolSpacing.sm) {
                Image(systemName: DirectionsFormatting.symbol(option?.mode ?? .walk))
                    .frame(width: 28)
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityHidden(true)
                if let option {
                    Text(verbatim: DirectionsFormatting.duration(option, language: container.language.code))
                    Text(verbatim: "· " + DirectionsFormatting.price(option, language: container.language.code))
                } else {
                    Text("Way not calculated")
                }
                if late > 0 {
                    Image(systemName: "clock.badge.exclamationmark").foregroundStyle(JolColor.danger)
                        .accessibilityLabel(Text("Arrives late"))
                }
                Spacer()
                if !model.isSavedCopy {
                    Image(systemName: "chevron.right").font(.caption).foregroundStyle(JolColor.textTertiary)
                        .accessibilityHidden(true)
                }
            }
            .font(JolFont.caption)
            .foregroundStyle(JolColor.textSecondary)
            .padding(.vertical, JolSpacing.xs)
            .frame(minHeight: JolTarget.minimum)
            .padding(.horizontal, JolSpacing.sm)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(legLabel(leg, option: option, late: late))
        .accessibilityHint(Text("Shows the ways to get there"))
        .accessibilityIdentifier("trip-leg-row")
    }

    /// «Walk, 12 min, Free, Arrives late» — the row's spoken form (its icons are decorative).
    private func legLabel(_ leg: TripLeg, option: DirectionOption?, late: Int) -> Text {
        guard let option else { return Text("Way not calculated") }
        let language = container.language.code
        var parts = [
            Text(DirectionsFormatting.title(option.mode)),
            Text(verbatim: DirectionsFormatting.duration(option, language: language)),
            Text(verbatim: DirectionsFormatting.price(option, language: language))
        ]
        if late > 0 { parts.append(Text("Arrives late")) }
        return Text.spoken(parts)
    }
}
