import Foundation

/// A number typed into a form field.
enum TypedNumber: Equatable {
    case empty
    case invalid
    case value(Int)

    init(_ text: String, range: ClosedRange<Int>) {
        let value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if value.isEmpty {
            self = .empty
        } else if value.allSatisfy({ $0.isASCII && $0.isNumber }), let number = Int(value), range.contains(number) {
            self = .value(number)
        } else {
            self = .invalid
        }
    }

    var int: Int? {
        if case .value(let number) = self { return number }
        return nil
    }
}

extension SubmissionDraft {
    private static func trimmed(_ text: String) -> String { text.trimmingCharacters(in: .whitespacesAndNewlines) }

    private static func amount(_ text: String) -> TypedNumber { TypedNumber(text, range: 0...maxMoney) }

    private static func line(_ text: String) -> String? {
        let value = trimmed(text).split(whereSeparator: \.isWhitespace).joined(separator: " ")
        return value.isEmpty ? nil : value
    }

    /// What is wrong with the form (empty = it can be sent).
    var problems: [Problem] {
        var found: [Problem] = []
        switch kind {
        case .review:
            if !(1...5).contains(rating) { found.append(.rating) }
            if Self.trimmed(text).count > 2000 { found.append(.textTooLong) }
        case .menu:
            let named = menuItems.filter { !Self.trimmed($0.name).isEmpty }
            if named.isEmpty && !hasPhoto { found.append(.menuEmpty) }
            if menuItems.contains(where: { Self.trimmed($0.name).isEmpty && !Self.trimmed($0.price).isEmpty }) {
                found.append(.menuName)
            }
            if named.contains(where: { Self.trimmed($0.name).count > 120 }) { found.append(.fieldTooLong) }
            if menuItems.contains(where: { Self.amount($0.price) == .invalid }) { found.append(.menuPrice) }
        case .photo:
            if !hasPhoto { found.append(.photoMissing) }
            if Self.trimmed(caption).count > 200 { found.append(.captionTooLong) }
        case .transit:
            let route = Self.trimmed(routeRef)
            if route.isEmpty || route.count > 40 { found.append(.routeRef) }
            if [stop, direction].contains(where: { Self.trimmed($0).count > 120 })
                || Self.trimmed(transitNote).count > 300 { found.append(.fieldTooLong) }
            if TypedNumber(interval, range: 1...240) == .invalid { found.append(.interval) }
            if Self.amount(transitPrice) == .invalid { found.append(.price) }
        case .price:
            if Self.amount(price).int == nil { found.append(.price) }
            if Self.trimmed(priceNote).count > 200 { found.append(.fieldTooLong) }
        }
        return found
    }

    var isValid: Bool { problems.isEmpty }

    /// The `payload` of `POST /v1/submissions`. Blank optionals are left out (the server forbids unknown fields and
    /// treats a missing one as absent).
    func payload(uploadID: UUID?) -> [String: JSONValue] {
        var body: [String: JSONValue] = [:]
        func put(_ key: String, _ value: String?) { if let value { body[key] = .string(value) } }
        func put(_ key: String, _ value: Int?) { if let value { body[key] = .int(value) } }
        switch kind {
        case .review:
            body["rating"] = .int(rating)
            put("text", Self.trimmed(text).isEmpty ? nil : Self.trimmed(text))
        case .menu:
            let items: [JSONValue] = menuItems.compactMap { item in
                guard let name = Self.line(item.name) else { return nil }
                var entry: [String: JSONValue] = ["name": .string(name)]
                if let price = Self.amount(item.price).int { entry["price_kzt"] = .int(price) }
                return .object(entry)
            }
            if !items.isEmpty { body["items"] = .array(items) }
            put("upload_id", uploadID?.uuidString.lowercased())
        case .photo:
            put("upload_id", uploadID?.uuidString.lowercased())
            put("caption", Self.line(caption))
        case .transit:
            put("route_ref", Self.line(routeRef))
            put("stop", Self.line(stop))
            put("direction", Self.line(direction))
            put("interval_min", TypedNumber(interval, range: 1...240).int)
            put("price_kzt", Self.amount(transitPrice).int)
            put("note", Self.line(transitNote))
        case .price:
            put("price_kzt", Self.amount(price).int)
            body["audience"] = .string(audience.rawValue)
            put("note", Self.line(priceNote))
        }
        return body
    }
}
