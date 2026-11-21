import SwiftUI

/// The stops of one day with the legs between them (full route map panel): tap a stop for its card, a leg for its
/// transport options, the minus button removes a stop.
struct TripDayListView: View {
    let model: TripMapModel
    let day: TripDay
    let onSelectPlace: (TripPlace) -> Void
    @Environment(\.locale) private var locale
    @Environment(AppContainer.self) private var container

    var body: some View {
        dayList(day)
    }

    private func dayList(_ day: TripDay) -> some View {
        LazyVStack(alignment: .leading, spacing: JolSpacing.xs) {
            if day.items.isEmpty {
                Text("Free day")
                    .foregroundStyle(JolColor.textSecondary)
                    .padding(.vertical, JolSpacing.md)
                    .accessibilityIdentifier("trip-free-day")
            }
            ForEach(Array(day.items.enumerated()), id: \.element.id) { index, item in
                if let leg = day.leg(to: item) { legRow(leg) }
                stopRow(item, number: index + 1)
            }
        }
        .padding(.bottom, JolSpacing.xl)
    }

    private func stopRow(_ item: TripDayItem, number: Int) -> some View {
        HStack(spacing: JolSpacing.md) {
            Button { onSelectPlace(item.place) } label: {
                HStack(spacing: JolSpacing.md) {
                    Text("\(number)")
                        .font(JolFont.callout.weight(.bold))
                        .foregroundStyle(JolColor.onBrand)
                        .frame(width: 28, height: 28)
                        .background(Color(model.dayColor), in: Circle())
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
                    Spacer(minLength: JolSpacing.xs)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .foregroundStyle(JolColor.textPrimary)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("trip-stop-\(number)")
            Button { model.remove(item) } label: {
                Image(systemName: "minus.circle")
                    .font(.title3)
                    .foregroundStyle(JolColor.textTertiary)
                    .frame(width: 36, height: 36)
            }
            .buttonStyle(.plain)
            .disabled(model.isWorking)
            .accessibilityLabel(Text("Remove from the route"))
            .accessibilityIdentifier("trip-stop-remove-\(number)")
        }
        .padding(.vertical, JolSpacing.xs)
    }

    private func stopCaption(_ item: TripDayItem) -> some View {
        HStack(spacing: JolSpacing.xs) {
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

    private func legRow(_ leg: TripLeg) -> some View {
        let option = leg.activeOption
        let late = model.lateBy[leg.id] ?? 0
        return Button { model.selectLeg(leg.id) } label: {
            HStack(spacing: JolSpacing.sm) {
                Image(systemName: DirectionsFormatting.symbol(option?.mode ?? .walk))
                    .frame(width: 28)
                    .foregroundStyle(JolColor.textSecondary)
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
                Image(systemName: "chevron.right").font(.caption).foregroundStyle(JolColor.textTertiary)
            }
            .font(JolFont.caption)
            .foregroundStyle(JolColor.textSecondary)
            .padding(.vertical, JolSpacing.xs)
            .padding(.horizontal, JolSpacing.sm)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("trip-leg-row")
    }
}
