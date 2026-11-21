@testable import Jol
import XCTest

final class SSEParserTests: XCTestCase {
    private func parse(_ text: String, chunk: Int = 3) async throws -> [SSEEvent] {
        // Feed in small chunks to prove the parser does not depend on chunk boundaries.
        let bytes = Array(text.utf8)
        let stream = AsyncStream<UInt8> { continuation in
            for byte in bytes { continuation.yield(byte) }
            continuation.finish()
        }
        var result: [SSEEvent] = []
        for try await event in SSEParser.events(from: stream) { result.append(event) }
        return result
    }

    func testCannedStream() async throws {
        let text = """
        : keep-alive

        event: token
        data: {"text":"Привет"}
        id: 1

        data: line one
        data: line two

        event: done
        data:

        """
        let events = try await parse(text + "\n")
        XCTAssertEqual(events, [
            SSEEvent(event: "token", data: "{\"text\":\"Привет\"}", id: "1"),
            SSEEvent(event: "message", data: "line one\nline two", id: "1"),
            SSEEvent(event: "done", data: "", id: "1")
        ])
    }

    func testCRLFAndLoneCR() async throws {
        let events = try await parse("event: a\r\ndata: 1\r\n\r\ndata: 2\r\r")
        XCTAssertEqual(events.map(\.data), ["1", "2"])
        XCTAssertEqual(events.map(\.event), ["a", "message"])
    }

    func testIncompleteTrailingEventIsDropped() async throws {
        let events = try await parse("data: done\n\ndata: cut off")
        XCTAssertEqual(events.map(\.data), ["done"])
    }

    func testFieldWithoutSpaceAndUnknownFields() {
        var parser = SSEParser()
        XCTAssertNil(parser.feed(line: "data:x"))
        XCTAssertNil(parser.feed(line: "retry: 1000"))
        XCTAssertNil(parser.feed(line: "bogus"))
        XCTAssertEqual(parser.feed(line: "")?.data, "x")
        XCTAssertNil(parser.feed(line: ""), "blank line without data dispatches nothing")
    }
}
