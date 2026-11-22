import SwiftUI

/// Bonus account (SSOT §10.3): balance, the rate "1 bonus ≈ 1 ₸", spending (soon), history of accruals.
struct BonusScreen: View {
    let model: BonusModel
    @Environment(\.locale) private var locale

    var body: some View {
        List {
            summary
            history
        }
        .navigationTitle(Text("Bonuses"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityIdentifier("bonus-screen")
        .task { await model.load() }
        .refreshable { await model.load() }
    }

    private var summary: some View {
        Section {
            VStack(alignment: .leading, spacing: JolSpacing.xs) {
                if let balance = model.balance {
                    Text(verbatim: balance.formatted(.number.locale(locale)))
                        .font(JolFont.largeTitle)
                        .foregroundStyle(JolColor.brandText)
                        .accessibilityIdentifier("bonus-balance")
                } else if model.phase == .failed {
                    Text("Couldn't load your bonuses.").foregroundStyle(JolColor.textSecondary)
                    Button("Try again") { Task { await model.load() } }
                        .accessibilityIdentifier("bonus-retry")
                } else {
                    ProgressView().accessibilityIdentifier("bonus-loading")
                }
                Text("1 bonus ≈ 1 ₸")
                    .font(JolFont.callout)
                    .foregroundStyle(JolColor.textSecondary)
                    .accessibilityIdentifier("bonus-rate")
            }
            Label("Spending bonuses: coming soon", systemImage: "clock")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("bonus-spending-soon")
        }
    }

    @ViewBuilder private var history: some View {
        if model.balance != nil {
            Section {
                if model.items.isEmpty {
                    Text("No bonuses yet. They are paid after a moderator approves your reviews, photos and data.")
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.textSecondary)
                        .accessibilityIdentifier("bonus-empty")
                }
                ForEach(model.items) { entry in
                    row(entry)
                        .onAppear {
                            if entry.id == model.items.last?.id { Task { await model.loadMore() } }
                        }
                }
                if model.isLoadingMore {
                    ProgressView().frame(maxWidth: .infinity)
                } else if model.moreFailed {
                    Button("Try again") { Task { await model.loadMore() } }
                        .accessibilityIdentifier("bonus-more-retry")
                }
            } header: {
                Text("History")
            }
        }
    }

    private func row(_ entry: BonusEntry) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                Text(LocalizedStringKey(entry.reasonKey)).font(JolFont.body)
                if let date = entry.date {
                    Text(date, format: .dateTime.day().month(.abbreviated).year().locale(locale))
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.textSecondary)
                }
            }
            Spacer()
            Text(verbatim: "+\(entry.amount.formatted(.number.locale(locale)))")
                .font(JolFont.headline)
                .foregroundStyle(JolColor.brand)
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("bonus-row")
    }
}
