import Foundation

/// One node of the chat chain (SSOT §11.2): an answer of the tourist that filled a field of the trip brief.
struct ChainNode: Equatable, Identifiable, Sendable {
    enum Kind: Equatable, Sendable {
        case dates
        case budget
        case lodging
        /// One must-have wish (its text, as the brief keeps it).
        case mustHave(String)
        case interests
        case pace
        case crowd
    }

    /// Stable key (the entry of the order list): the node keeps it while its value changes.
    let key: String
    let kind: Kind

    var id: String { key }
}

/// Brief → chain nodes. Pure: the order is the order of the answers (`order`, entries as the server writes them to
/// `trip_briefs.filled_order`: a brief field name, or `must_haves:<item>`), a node exists while its field is filled.
enum ChainNodes {
    static let datesKey = "dates"
    static let mustHavePrefix = "must_haves:"

    /// Entry of the order list → key of a node (`start_date` / `end_date` are one node).
    static func key(forField field: String) -> String {
        switch field {
        case "start_date", "end_date": datesKey
        default: field
        }
    }

    /// Keys added by one `brief_updated`: its changed fields; for `must_haves` one key per newly added item.
    static func keys(changed: [String], previous: ChatBrief?, current: ChatBrief) -> [String] {
        let known = Set((previous?.mustHaves ?? []).map { $0.lowercased() })
        var keys: [String] = []
        for field in changed {
            if field == "must_haves" {
                keys += current.mustHaves.filter { !known.contains($0.lowercased()) }.map { mustHavePrefix + $0 }
            } else {
                keys.append(key(forField: field))
            }
        }
        return keys
    }

    /// `order` plus the keys not there yet; a repeated answer keeps its place.
    static func merged(_ order: [String], with keys: [String]) -> [String] {
        var result = order
        for key in keys where !result.contains(key) { result.append(key) }
        return result
    }

    /// Order of the keys of a stored order list (`start_date` + `end_date` collapse into one).
    static func normalized(_ order: [String]) -> [String] {
        merged([], with: order.map { $0.hasPrefix(mustHavePrefix) ? $0 : key(forField: $0) })
    }

    private static func kind(forKey key: String, brief: ChatBrief) -> ChainNode.Kind? {
        if key.hasPrefix(mustHavePrefix) {
            let wanted = String(key.dropFirst(mustHavePrefix.count)).lowercased()
            return brief.mustHaves.first { $0.lowercased() == wanted }.map { .mustHave($0) }
        }
        switch key {
        case datesKey: return brief.startDate != nil || brief.endDate != nil ? .dates : nil
        case "budget_kzt": return brief.budgetKzt != nil ? .budget : nil
        case "has_accommodation": return brief.hasAccommodation != nil ? .lodging : nil
        case "interests": return brief.interests.isEmpty ? nil : .interests
        case "pace": return brief.pace != nil ? .pace : nil
        case "crowd_tolerance": return brief.crowdTolerance != nil ? .crowd : nil
        default: return nil
        }
    }

    /// Fields in the order a conversation normally goes (SSOT §4); used for filled fields that `order` lacks
    /// (a server that does not send `filled_order`).
    private static let canonical = [
        datesKey, "budget_kzt", "has_accommodation", "must_haves", "interests", "pace", "crowd_tolerance",
    ]

    /// The nodes for a brief: filled fields in `order`, then — if the order does not know them — in the canonical one.
    static func nodes(brief: ChatBrief?, order: [String]) -> [ChainNode] {
        guard let brief else { return [] }
        var nodes: [ChainNode] = []
        var seen: Set<String> = []
        func add(_ key: String) {
            guard !seen.contains(key), let kind = kind(forKey: key, brief: brief) else { return }
            seen.insert(key)
            nodes.append(ChainNode(key: key, kind: kind))
        }
        for key in order { add(key) }
        for key in canonical {
            if key == "must_haves" {
                brief.mustHaves.forEach { add(mustHavePrefix + $0) }
            } else {
                add(key)
            }
        }
        return nodes
    }
}
