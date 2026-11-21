import SwiftUI

/// The circular carousel of transport pages (SSOT §6.1): chips, swipe, variant rows.
extension DirectionsPanel {
    var carousel: some View {
        VStack(alignment: .leading, spacing: JolSpacing.md) {
            chips
            if let page = model.currentPage {
                pageView(page)
                    .id(page.kind)
                    .transition(.asymmetric(insertion: .move(edge: slideFrom), removal: .opacity))
                    .accessibilityElement(children: .contain)
                    .accessibilityIdentifier("directions-page-\(page.kind.slug)")
            }
        }
        .contentShape(Rectangle())
        // Horizontal swipe turns the page; the carousel is circular.
        .simultaneousGesture(
            DragGesture(minimumDistance: 24).onEnded { value in
                guard abs(value.translation.width) > 50, abs(value.translation.width) > abs(value.translation.height)
                else { return }
                turn(forward: value.translation.width < 0)
            }
        )
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("directions-carousel")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: turn(forward: true)
            case .decrement: turn(forward: false)
            @unknown default: break
            }
        }
    }

    func turn(forward: Bool) {
        slideFrom = forward ? .trailing : .leading
        withAnimation(.snappy(duration: 0.25)) {
            if forward { model.showNext() } else { model.showPrevious() }
        }
    }

    /// Mode icons with the best time; the current page is filled, tapping one jumps to it.
    var chips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: JolSpacing.sm) {
                ForEach(Array(model.pages.enumerated()), id: \.element.kind) { index, page in
                    chip(page, index: index)
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("directions-chips")
    }

    private func chip(_ page: TransportPage, index: Int) -> some View {
        let current = index == model.pageIndex
        let first = page.fastest
        return Button {
            slideFrom = index > model.pageIndex ? .trailing : .leading
            withAnimation(.snappy(duration: 0.25)) { model.showPage(index) }
        } label: {
            HStack(spacing: JolSpacing.xs) {
                Image(systemName: DirectionsFormatting.symbol(first?.mode ?? .walk))
                    .accessibilityHidden(true)
                if let first {
                    Text(DirectionsFormatting.clock(DirectionsFormatting.minutes(first.durationS), language: language))
                        .font(JolFont.caption.weight(.semibold))
                }
            }
            .padding(.horizontal, JolSpacing.md)
            .padding(.vertical, JolSpacing.sm)
            .frame(minHeight: JolTarget.minimum)
            .foregroundStyle(current ? JolColor.onBrand : JolColor.textPrimary)
            .background(current ? JolColor.brand : JolColor.surface, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(chipLabel(page, first: first))
        .accessibilityAddTraits(current ? [.isButton, .isSelected] : .isButton)
        .accessibilityIdentifier("directions-chip-\(page.kind.slug)")
    }

    private func pageView(_ page: TransportPage) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.sm) {
            HStack {
                Text(DirectionsFormatting.pageTitle(page.kind))
                    .font(JolFont.headline)
                    .foregroundStyle(JolColor.textPrimary)
                Spacer()
                Text("\(model.pageIndex + 1) / \(model.pages.count)")
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.textTertiary)
                    .accessibilityLabel(Text("Page \(model.pageIndex + 1) of \(model.pages.count)"))
                    .accessibilityIdentifier("directions-page-counter")
            }
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.isHeader)
            ForEach(Array(page.variants.enumerated()), id: \.offset) { index, option in
                variantRow(option, index: index, page: page)
            }
        }
    }

    private func variantRow(_ option: DirectionOption, index: Int, page: TransportPage) -> some View {
        let selected = model.selectedVariant(of: page) == index
        return Button { model.selectVariant(index) } label: {
            AdaptiveStack(spacing: JolSpacing.md) {
                Image(systemName: DirectionsFormatting.symbol(option.mode))
                    .font(.title3)
                    .frame(width: 40, height: 40)
                    .accessibilityHidden(true)
                    .background(selected ? JolColor.brand : JolColor.surface, in: Circle())
                    .foregroundStyle(selected ? JolColor.onBrand : JolColor.textPrimary)
                VStack(alignment: .leading, spacing: JolSpacing.xxs) {
                    HStack(spacing: JolSpacing.xs) {
                        Text(DirectionsFormatting.title(option.mode))
                        if let ref = option.transitRef { Text(ref).foregroundStyle(JolColor.textSecondary) }
                    }
                    .font(JolFont.headline)
                    detailLine(option, index: index, count: page.variants.count)
                }
                Spacer(minLength: JolSpacing.sm)
                VStack(alignment: typeSize.isAccessibilitySize ? .leading : .trailing, spacing: JolSpacing.xxs) {
                    Text(DirectionsFormatting.duration(option, language: language)).font(JolFont.headline)
                    Text("Arrive \(DirectionsFormatting.arrival(option, departedAt: model.answeredAt))")
                        .font(JolFont.caption.weight(.semibold))
                        .foregroundStyle(JolColor.textPrimary)
                    Text(DirectionsFormatting.price(option, language: language))
                        .font(JolFont.caption)
                        .foregroundStyle(JolColor.textSecondary)
                }
            }
            .foregroundStyle(JolColor.textPrimary)
            .padding(JolSpacing.md)
            .background(JolColor.surface.opacity(selected ? 1 : 0.6), in: RoundedRectangle(cornerRadius: JolRadius.lg))
            .overlay(
                RoundedRectangle(cornerRadius: JolRadius.lg)
                    .stroke(selected ? JolColor.brand : .clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(variantLabel(option, index: index, count: page.variants.count))
        .accessibilityHint(selected ? Text("") : Text("Shows this way on the map"))
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
        .accessibilityIdentifier("direction-variant-\(page.kind.slug)-\(index + 1)")
    }

    /// Second line: «Recommended» / «Optimal» tag or distance, plus the congestion slot (only when the server
    /// sends `congestion`; there is no data source yet, SSOT §16.14).
    private func detailLine(_ option: DirectionOption, index: Int, count: Int) -> some View {
        HStack(spacing: JolSpacing.xs) {
            if option.recommended {
                Text("Recommended").foregroundStyle(JolColor.brand).fontWeight(.semibold)
            } else if index == 0 && count > 1 {
                Text("Optimal").foregroundStyle(JolColor.brand).fontWeight(.semibold)
            } else {
                Text(DirectionsFormatting.distance(option.distanceM, language: language))
                    .foregroundStyle(JolColor.textSecondary)
            }
            if let congestion = DirectionsFormatting.congestion(option) {
                Text("·").foregroundStyle(JolColor.textTertiary)
                Text(congestion).foregroundStyle(JolColor.textSecondary)
                    .accessibilityIdentifier("direction-congestion")
            }
        }
        .font(JolFont.caption)
    }

    /// Spoken form of a chip: «Walk, 12 min».
    func chipLabel(_ page: TransportPage, first: DirectionOption?) -> Text {
        var parts = [Text(DirectionsFormatting.pageTitle(page.kind))]
        if let first {
            parts.append(Text(verbatim: DirectionsFormatting.clock(
                DirectionsFormatting.minutes(first.durationS), language: language)))
        }
        return Text.spoken(parts)
    }

    /// Spoken form of a variant row: mode, time, arrival, price, tag/distance, congestion (its icon is decorative).
    func variantLabel(_ option: DirectionOption, index: Int, count: Int) -> Text {
        let mode = Text(DirectionsFormatting.title(option.mode))
        let title = option.transitRef.map { mode + Text(verbatim: " " + $0) } ?? mode
        let arrival = DirectionsFormatting.arrival(option, departedAt: model.answeredAt)
        var parts = [
            title,
            Text(verbatim: DirectionsFormatting.duration(option, language: language)),
            Text("Arrive \(arrival)"),
            Text(verbatim: DirectionsFormatting.price(option, language: language))
        ]
        if option.recommended {
            parts.append(Text("Recommended"))
        } else if index == 0 && count > 1 {
            parts.append(Text("Optimal"))
        } else {
            parts.append(Text(verbatim: DirectionsFormatting.distance(option.distanceM, language: language)))
        }
        if let congestion = DirectionsFormatting.congestion(option) { parts.append(Text(congestion)) }
        return Text.spoken(parts)
    }
}
