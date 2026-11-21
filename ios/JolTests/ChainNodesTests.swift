@testable import Jol
import XCTest

/// Ш-32b: brief → chain nodes (which nodes, in which order) and the label of each node, in Russian and English.
final class ChainNodesTests: XCTestCase {
    private let english = Locale(identifier: "en_US")
    private let russian = Locale(identifier: "ru_RU")

    private func brief(_ json: String) throws -> ChatBrief {
        try JSONDecoder().decode(ChatBrief.self, from: Data(json.utf8))
    }

    private func kinds(_ brief: ChatBrief, order: [String] = []) -> [ChainNode.Kind] {
        ChainNodes.nodes(brief: brief, order: order).map(\.kind)
    }

    // MARK: - Nodes

    func testOneNodePerAnsweredFieldAndDatesAreOneNode() throws {
        let full = try brief("""
        {"start_date":"2026-12-05","end_date":"2026-12-09","budget_kzt":200000,"has_accommodation":true,\
        "must_haves":["plov","sushi"],"interests":["museums","hiking"],"pace":"calm","crowd_tolerance":1}
        """)
        XCTAssertEqual(
            kinds(full),
            [.dates, .budget, .lodging, .mustHave("plov"), .mustHave("sushi"), .interests, .pace, .crowd]
        )
        XCTAssertEqual(kinds(ChatBrief()), [])
        XCTAssertEqual(ChainNodes.nodes(brief: nil, order: ["budget_kzt"]).count, 0)
        let oneDate = try brief("{\"start_date\":\"2026-12-05\"}")
        XCTAssertEqual(kinds(oneDate), [.dates], "one known date is a node too")
        let needsLodging = try brief("{\"has_accommodation\":false}")
        XCTAssertEqual(kinds(needsLodging), [.lodging], "«need lodging» is an answer")
    }

    func testOrderIsTheOrderOfTheAnswersThenCanonicalForTheRest() throws {
        let full = try brief("""
        {"start_date":"2026-12-05","end_date":"2026-12-09","budget_kzt":200000,"has_accommodation":true,\
        "must_haves":["plov"],"pace":"calm"}
        """)
        let order = ["budget_kzt", "must_haves:plov", "dates"]
        let nodes = ChainNodes.nodes(brief: full, order: order)
        XCTAssertEqual(nodes.map(\.key), ["budget_kzt", "must_haves:plov", "dates", "has_accommodation", "pace"])
        XCTAssertEqual(
            ChainNodes.nodes(brief: full, order: ["pace", "pace", "unknown_field", "interests"]).map(\.key),
            ["pace", "dates", "budget_kzt", "has_accommodation", "must_haves:plov"],
            "unknown and empty entries are skipped, repeated ones count once"
        )
    }

    func testKeysOfAnUpdate() throws {
        let before = try brief("{\"must_haves\":[\"plov\"],\"budget_kzt\":1}")
        let after = try brief("{\"must_haves\":[\"Plov\",\"sushi\"],\"budget_kzt\":2,\"start_date\":\"2026-12-05\"}")
        let changed = ["start_date", "end_date", "budget_kzt", "must_haves"]
        XCTAssertEqual(
            ChainNodes.keys(changed: changed, previous: before, current: after),
            ["dates", "dates", "budget_kzt", "must_haves:sushi"],
            "only the new wish makes a key; a different case is the same wish"
        )
        let merged = ChainNodes.merged(["budget_kzt"], with: ["dates", "dates", "budget_kzt"])
        XCTAssertEqual(merged, ["budget_kzt", "dates"])
        XCTAssertEqual(
            ChainNodes.normalized(["start_date", "budget_kzt", "end_date", "must_haves:x"]),
            ["dates", "budget_kzt", "must_haves:x"]
        )
    }

    func testARemovedWishLeavesTheChain() throws {
        let wish = try brief("{\"must_haves\":[\"plov\",\"sushi\"]}")
        let order = ["must_haves:plov", "must_haves:sushi"]
        XCTAssertEqual(ChainNodes.nodes(brief: wish, order: order).count, 2)
        let removed = try brief("{\"must_haves\":[\"sushi\"]}")
        XCTAssertEqual(ChainNodes.nodes(brief: removed, order: order).map(\.key), ["must_haves:sushi"])
    }

    // MARK: - Labels

    private func label(_ json: String, _ kind: ChainNode.Kind, _ locale: Locale, full: Bool = false) throws -> String {
        let brief = try brief(json)
        let node = ChainNode(key: "k", kind: kind)
        return full ? ChainLabels.full(node, brief: brief, locale: locale)
            : ChainLabels.short(node, brief: brief, locale: locale)
    }

    func testDaysLabelEnglishAndRussian() throws {
        let json = "{\"start_date\":\"2026-12-05\",\"end_date\":\"2026-12-09\"}"
        XCTAssertEqual(try label(json, .dates, english), "5 days")
        XCTAssertEqual(try label(json, .dates, russian), "5 дней")
        let one = "{\"start_date\":\"2026-12-05\",\"end_date\":\"2026-12-05\"}"
        XCTAssertEqual(try label(one, .dates, english), "1 day")
        XCTAssertEqual(try label(one, .dates, russian), "1 день")
        let two = "{\"start_date\":\"2026-12-05\",\"end_date\":\"2026-12-07\"}"
        XCTAssertEqual(try label(two, .dates, russian), "3 дня")
        XCTAssertTrue(try label(json, .dates, english, full: true).hasPrefix("5 days · "))
        XCTAssertTrue(try label(json, .dates, english, full: true).contains("Dec"))
    }

    func testSingleDateAndLongRangeAcrossMonths() throws {
        XCTAssertTrue(try label("{\"start_date\":\"2026-12-05\"}", .dates, english).contains("Dec"))
        let acrossYear = "{\"start_date\":\"2026-12-30\",\"end_date\":\"2027-01-02\"}"
        XCTAssertEqual(try label(acrossYear, .dates, english), "4 days")
    }

    func testBudgetIsGroupedPerLocale() throws {
        let json = "{\"budget_kzt\":200000}"
        XCTAssertEqual(try label(json, .budget, english), "200,000 ₸")
        let russianText = try label(json, .budget, russian)
            .replacingOccurrences(of: "\u{00A0}", with: " ").replacingOccurrences(of: "\u{202F}", with: " ")
        XCTAssertEqual(russianText, "200 000 ₸")
    }

    func testLodgingPaceCrowdLabels() throws {
        XCTAssertEqual(try label("{\"has_accommodation\":true}", .lodging, english), "Have accommodation")
        XCTAssertEqual(try label("{\"has_accommodation\":true}", .lodging, russian), "жильё есть")
        XCTAssertEqual(try label("{\"has_accommodation\":false}", .lodging, english), "Need accommodation")
        XCTAssertEqual(try label("{\"has_accommodation\":false}", .lodging, russian), "нужно жильё")
        XCTAssertEqual(try label("{\"pace\":\"calm\"}", .pace, russian), "спокойный темп")
        XCTAssertEqual(try label("{\"pace\":\"dense\"}", .pace, english), "Packed days")
        XCTAssertEqual(try label("{\"pace\":\"normal\"}", .pace, english), "Steady pace")
        XCTAssertEqual(try label("{\"crowd_tolerance\":0}", .crowd, english), "Quiet places only")
        XCTAssertEqual(try label("{\"crowd_tolerance\":4}", .crowd, russian), "люблю оживлённые")
    }

    func testWishAndInterestsAreTheUsersWordsTruncatedOnlyNextToTheNode() throws {
        XCTAssertEqual(try label("{}", .mustHave("восточная кухня"), russian), "восточная кухня")
        let long = "Chinese food in a very good place"
        let short = try label("{}", .mustHave(long), english)
        XCTAssertLessThanOrEqual(short.count, ChainLabels.shortLimit)
        XCTAssertTrue(short.hasSuffix("…"))
        XCTAssertEqual(try label("{}", .mustHave(long), english, full: true), long, "the full text is kept for a tap")
        let interests = "{\"interests\":[\"museums\",\"hiking\",\"jazz\"]}"
        XCTAssertEqual(try label(interests, .interests, english, full: true), "museums, hiking, jazz")
        XCTAssertEqual(try label(interests, .interests, english), "museums, hiking,…")
    }

    func testTruncationKeepsShortTextAndNeverExceedsTheLimit() {
        XCTAssertEqual(ChainLabels.truncated("5 days", limit: 18), "5 days")
        XCTAssertEqual(ChainLabels.truncated(String(repeating: "я", count: 40), limit: 10).count, 10)
    }
}
