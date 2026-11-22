import SwiftUI

/// «Replace this place» (Ш-55): the places a stop can be swapped for (`GET …/items/{id}/alternatives`: similar, nearby,
/// not yet in the trip). A tap swaps the stop (`POST …/replace`); the sheet closes and the day is re-read.
struct TripReplaceSheet: View {
    let model: TripMapModel
    @Environment(AppContainer.self) private var container
    @Environment(\.dismiss) private var dismiss
    @Environment(\.locale) private var locale

    private var language: String { container.language.code }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: JolSpacing.md) {
                    if let name = model.replacing?.name {
                        Text("Instead of \(name)")
                            .font(JolFont.callout)
                            .foregroundStyle(JolColor.textSecondary)
                            .accessibilityIdentifier("trip-replace-subject")
                    }
                    if let problem = model.problem, problem != .outdated {
                        Text(verbatim: problemText(problem))
                            .font(JolFont.caption)
                            .foregroundStyle(JolColor.danger)
                            .accessibilityIdentifier("trip-replace-problem")
                    }
                    content
                }
                .padding(JolSpacing.lg)
            }
            .navigationTitle(Text("Replace this place"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Cancel") { dismiss() }.accessibilityIdentifier("trip-replace-cancel")
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationBackground(JolColor.surfaceElevated)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("trip-replace-sheet")
        .alert(
            Text("Replace a must-have?"),
            isPresented: Binding(
                get: { model.pendingReplacement != nil }, set: { if !$0 { model.cancelReplacement() } }
            )
        ) {
            Button("Replace anyway", role: .destructive) { model.confirmReplacement() }
                .accessibilityIdentifier("trip-replace-confirm")
            Button("Keep it", role: .cancel) { model.cancelReplacement() }
                .accessibilityIdentifier("trip-replace-keep")
        } message: {
            Text("\(model.replacing?.name ?? "") is something you asked for. Replace it anyway?")
        }
    }

    @ViewBuilder private var content: some View {
        switch model.alternatives {
        case .idle, .loading:
            ProgressView()
                .frame(maxWidth: .infinity)
                .padding(.vertical, JolSpacing.xl)
                .accessibilityLabel(Text("Loading"))
                .accessibilityIdentifier("trip-replace-loading")
        case .failed:
            VStack(alignment: .leading, spacing: JolSpacing.md) {
                Text("Couldn't load the places.").foregroundStyle(JolColor.textSecondary)
                Button("Try again") { model.retryAlternatives() }
                    .frame(minHeight: JolTarget.minimum)
                    .accessibilityIdentifier("trip-replace-retry")
            }
        case .loaded(let items):
            if items.isEmpty {
                Text("No similar places nearby.")
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityIdentifier("trip-replace-empty")
            }
            ForEach(items) { item in row(item) }
        }
    }

    private func row(_ item: TripAlternative) -> some View {
        Button { model.replace(with: item) } label: {
            AdaptiveStack(spacing: JolSpacing.md) {
                VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                    Text(verbatim: item.name).font(JolFont.body.weight(.semibold))
                    if let category = item.categoryName ?? item.category {
                        Text(verbatim: category).font(JolFont.caption).foregroundStyle(JolColor.textSecondary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                VStack(alignment: .trailing, spacing: JolSpacing.xxs) {
                    if let price = item.priceKzt, price > 0 {
                        Text(verbatim: TripFormatting.kzt(price, locale: locale)).font(JolFont.callout)
                    }
                    if let distance = item.distanceM {
                        Text(verbatim: DirectionsFormatting.distance(distance, language: language))
                            .font(JolFont.caption)
                            .foregroundStyle(JolColor.textSecondary)
                    }
                }
            }
            .foregroundStyle(JolColor.textPrimary)
            .padding(JolSpacing.md)
            .frame(maxWidth: .infinity, minHeight: JolTarget.minimum, alignment: .leading)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(model.isWorking)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(rowLabel(item))
        .accessibilityHint(Text("Replaces the stop with this place"))
        .accessibilityIdentifier("trip-replace-option")
    }

    /// «Museum of Arts, Museum, 3,000 ₸, 450 m» — the row's spoken form.
    private func rowLabel(_ item: TripAlternative) -> Text {
        var parts = [Text(verbatim: item.name)]
        if let category = item.categoryName ?? item.category { parts.append(Text(verbatim: category)) }
        if let price = item.priceKzt, price > 0 {
            parts.append(Text(verbatim: TripFormatting.kzt(price, locale: locale)))
        }
        if let distance = item.distanceM {
            parts.append(Text(verbatim: DirectionsFormatting.distance(distance, language: language)))
        }
        return Text.spoken(parts)
    }

    private func problemText(_ problem: TripMapModel.Problem) -> String {
        switch problem {
        case .network: L10n.string("No connection. Try again.", language: language)
        case .noReplacement: L10n.string("No other place fits this day.", language: language)
        case .server(let message): message
        case .outdated: ""
        }
    }
}
