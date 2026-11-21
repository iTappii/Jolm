@testable import Jol
import XCTest

/// Ш-32b: the chain in the chat state — nodes come from `brief_updated` in the order of the answers.
final class ChatChainReductionTests: XCTestCase {
    private func recorded(_ name: String) async throws -> [ChatEvent] {
        let bytes = Array(ChatStub.fixture(name).utf8)
        XCTAssertFalse(bytes.isEmpty, "fixture \(name) is missing")
        let stream = AsyncStream<UInt8> { continuation in
            for byte in bytes { continuation.yield(byte) }
            continuation.finish()
        }
        var events: [ChatEvent] = []
        for try await raw in SSEParser.events(from: stream) { events.append(ChatEvent(raw)) }
        return events
    }

    private func brief(_ json: String) throws -> ChatBrief {
        try JSONDecoder().decode(ChatBrief.self, from: Data(json.utf8))
    }

    func testRecordedDialogFillsTheRingAnswerByAnswerAndAChangedAnswerAddsNoNode() async throws {
        var state = ChatState()
        var seen: [[String]] = []
        for name in ["chat-dlg-0", "chat-dlg-1", "chat-dlg-2", "chat-dlg-3", "chat-dlg-4", "chat-dlg-5"] {
            for event in try await recorded(name) { state.apply(event) }
            seen.append(state.chainNodes.map(\.key))
        }
        XCTAssertEqual(seen[0], [], "a question alone makes no node")
        XCTAssertEqual(seen[1], ["dates"])
        XCTAssertEqual(seen[2], ["dates", "budget_kzt"])
        XCTAssertEqual(seen[3], ["dates", "budget_kzt", "has_accommodation"])
        XCTAssertEqual(seen[4], ["dates", "budget_kzt", "has_accommodation", "must_haves:Eastern cuisine"])
        XCTAssertEqual(seen[5], seen[4], "the budget changed: same nodes, new value")
        XCTAssertEqual(state.brief?.budgetKzt, 300_000)
        XCTAssertFalse(state.isConverged)
        for event in try await recorded("chat-dlg-6") { state.apply(event) }
        XCTAssertTrue(state.isConverged)
        XCTAssertEqual(state.chainNodes.count, 4)
    }

    func testOrderFollowsTheAnswersNotTheCanonicalOrder() throws {
        var state = ChatState()
        let wish = try brief("{\"must_haves\":[\"plov\"]}")
        state.apply(.briefUpdated(wish, changed: ["must_haves"]))
        let both = try brief("{\"must_haves\":[\"plov\"],\"budget_kzt\":100000}")
        state.apply(.briefUpdated(both, changed: ["budget_kzt"]))
        let more = try brief("{\"must_haves\":[\"plov\",\"sushi\"],\"budget_kzt\":100000}")
        state.apply(.briefUpdated(more, changed: ["must_haves"]))
        XCTAssertEqual(state.chainNodes.map(\.key), ["must_haves:plov", "budget_kzt", "must_haves:sushi"])
    }

    func testReopenedChatRestoresTheRingFromFilledOrder() throws {
        let json = """
        {"id":"\(ChatStub.chatID)","title":null,"messages":[],"graph_nodes":[],"brief":{\
        "start_date":"2026-12-05","end_date":"2026-12-07","budget_kzt":500000,"has_accommodation":false,\
        "must_haves":["plov"],"interests":[],"missing":[],"complete":true,\
        "filled_order":["must_haves:plov","budget_kzt","start_date","end_date","has_accommodation"]}}
        """
        let detail = try JSONDecoder().decode(ChatDetail.self, from: Data(json.utf8))
        let state = ChatState(detail: detail, route: nil, proposals: [:])
        XCTAssertEqual(state.chainNodes.map(\.key), ["must_haves:plov", "budget_kzt", "dates", "has_accommodation"])
        XCTAssertFalse(state.isEmpty)
    }
}
