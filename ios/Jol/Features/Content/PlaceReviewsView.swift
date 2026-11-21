import SwiftUI

/// Five stars for a rating.
struct RatingStars: View {
    let rating: Int

    var body: some View {
        HStack(spacing: 2) {
            ForEach(1...5, id: \.self) { star in
                Image(systemName: star <= rating ? "star.fill" : "star")
                    .font(.caption)
                    .foregroundStyle(star <= rating ? JolColor.brand : JolColor.textTertiary)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text("\(rating) of 5"))
    }
}

/// «Отзывы» tab (Ш-44): the average and count, then the reviews page by page. No reviews → the old empty state.
struct PlaceReviewsView: View {
    let place: PlaceSummary
    var onAdd: () -> Void = {}
    @Environment(AppContainer.self) private var container
    @Environment(\.locale) private var locale

    private var model: ReviewsModel { container.reviews }

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            content
            Button(action: onAdd) {
                Label("Write a review", systemImage: "square.and.pencil")
                    .font(JolFont.callout.weight(.semibold))
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, JolSpacing.sm)
                    .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("place-write-review")
        }
        .task(id: place.id) { await model.load(placeID: place.id) }
    }

    @ViewBuilder private var content: some View {
        switch model.phase {
        case .idle, .loading:
            ProgressView().frame(maxWidth: .infinity).padding(.vertical, JolSpacing.lg)
                .accessibilityIdentifier("place-reviews-loading")
        case .failed:
            HStack {
                Text("Couldn't load the reviews").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
                Button("Retry") { Task { await model.reload() } }
                    .accessibilityIdentifier("place-reviews-retry")
            }
        case .loaded:
            if model.items.isEmpty { empty } else { list }
        }
    }

    private var empty: some View {
        VStack(spacing: JolSpacing.sm) {
            Image(systemName: "text.bubble").font(.largeTitle).foregroundStyle(JolColor.textTertiary)
            Text("No reviews yet").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, JolSpacing.xl)
        .accessibilityIdentifier("place-reviews-empty")
    }

    @ViewBuilder private var list: some View {
        if let summary = model.summary, let average = summary.average {
            HStack(spacing: JolSpacing.xs) {
                Image(systemName: "star.fill").foregroundStyle(JolColor.brand)
                Text(verbatim: average.formatted(.number.precision(.fractionLength(1)).locale(locale)))
                    .font(JolFont.headline)
                Text("\(summary.count) reviews").font(JolFont.callout).foregroundStyle(JolColor.textSecondary)
            }
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("place-reviews-summary")
        }
        ForEach(model.items) { review in
            row(review)
                .onAppear {
                    if review.id == model.items.last?.id { Task { await model.loadMore() } }
                }
        }
        if model.isLoadingMore {
            ProgressView().frame(maxWidth: .infinity)
        } else if model.moreFailed {
            Button("Retry") { Task { await model.loadMore() } }
                .accessibilityIdentifier("place-reviews-more-retry")
        }
    }

    private func row(_ review: PlaceReview) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.xxs) {
            HStack {
                RatingStars(rating: review.rating)
                Spacer()
                if let date = review.date {
                    Text(date, format: .dateTime.day().month(.abbreviated).year().locale(locale))
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.textSecondary)
                }
            }
            if let text = review.text, !text.isEmpty {
                Text(verbatim: text).font(JolFont.body).foregroundStyle(JolColor.textPrimary)
            }
            HStack(spacing: JolSpacing.xs) {
                if let name = review.authorName, !name.isEmpty {
                    Text(verbatim: name)
                } else {
                    Text("Anonymous")
                }
                if review.pendingReview {
                    Text("· will be checked later")
                }
            }
            .font(JolFont.caption)
            .foregroundStyle(JolColor.textSecondary)
        }
        .padding(.vertical, JolSpacing.xs)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("review-row")
    }
}
