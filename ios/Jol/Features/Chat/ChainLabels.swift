import Foundation

/// Texts of the chain nodes (SSOT §11.2): the value the tourist gave, never a number of the node. `short` sits next to
/// the node (cut to `shortLimit` characters), `full` is shown when the node is tapped. Words come from the String
/// Catalog in the language of `locale`.
enum ChainLabels {
    static let shortLimit = 18

    static func short(_ node: ChainNode, brief: ChatBrief, locale: Locale) -> String {
        truncated(summary(node, brief: brief, locale: locale), limit: shortLimit)
    }

    /// The whole value; for dates the range as well («5 days · 5 – 9 Dec»).
    static func full(_ node: ChainNode, brief: ChatBrief, locale: Locale) -> String {
        let text = summary(node, brief: brief, locale: locale)
        if node.kind == .dates, brief.startDate != nil, brief.endDate != nil,
           let range = BriefFormatting.dates(start: brief.startDate, end: brief.endDate, locale: locale),
           range != text {
            return "\(text) · \(range)"
        }
        return text
    }

    static func truncated(_ text: String, limit: Int) -> String {
        guard text.count > limit else { return text }
        return String(text.prefix(limit - 1)).trimmingCharacters(in: .whitespaces) + "…"
    }

    private static func summary(_ node: ChainNode, brief: ChatBrief, locale: Locale) -> String {
        switch node.kind {
        case .dates: return dates(brief, locale: locale)
        case .budget: return BriefFormatting.budget(brief.budgetKzt ?? 0, locale: locale)
        case .lodging:
            return brief.hasAccommodation == true
                ? localized("Have accommodation", locale: locale) : localized("Need accommodation", locale: locale)
        case .mustHave(let text): return text
        case .interests: return brief.interests.joined(separator: ", ")
        case .pace:
            switch brief.pace {
            case "calm": return localized("Calm pace", locale: locale)
            case "dense": return localized("Packed days", locale: locale)
            default: return localized("Steady pace", locale: locale)
            }
        case .crowd: return crowd(brief.crowdTolerance ?? 2, locale: locale)
        }
    }

    /// «N days» when both dates are known, else the single date.
    private static func dates(_ brief: ChatBrief, locale: Locale) -> String {
        if let start = BriefFormatting.day(brief.startDate), let end = BriefFormatting.day(brief.endDate) {
            let gap = Calendar(identifier: .gregorian).dateComponents([.day], from: start, to: end).day ?? 0
            let days = max(1, gap + 1)
            return String(localized: LocalizedStringResource("\(days) days", locale: locale))
        }
        return BriefFormatting.dates(start: brief.startDate, end: brief.endDate, locale: locale) ?? ""
    }

    private static func crowd(_ level: Int, locale: Locale) -> String {
        switch level {
        case ...0: localized("Quiet places only", locale: locale)
        case 1: localized("Prefer quiet", locale: locale)
        case 2: localized("Crowds: either way", locale: locale)
        case 3: localized("Fine in a crowd", locale: locale)
        default: localized("Love lively places", locale: locale)
        }
    }

    private static func localized(_ key: String.LocalizationValue, locale: Locale) -> String {
        String(localized: LocalizedStringResource(key, locale: locale))
    }
}
