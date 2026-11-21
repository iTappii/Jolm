import Foundation

/// One server-sent event (`text/event-stream`).
struct SSEEvent: Equatable, Sendable {
    /// `event:` field; `"message"` when absent (per the SSE spec).
    var event: String
    /// `data:` lines joined with `\n`.
    var data: String
    var id: String?
}

/// Incremental parser for the SSE wire format. Feed it lines (without terminators);
/// a blank line dispatches the pending event.
struct SSEParser: Sendable {
    private var event: String?
    private var dataLines: [String] = []
    private var lastID: String?

    /// Returns an event when `line` completes one.
    mutating func feed(line: String) -> SSEEvent? {
        if line.isEmpty {
            defer { event = nil; dataLines = [] }
            guard !dataLines.isEmpty else { return nil }
            return SSEEvent(event: event ?? "message", data: dataLines.joined(separator: "\n"), id: lastID)
        }
        if line.hasPrefix(":") { return nil } // comment / keep-alive
        let field: Substring
        var value: Substring
        if let colon = line.firstIndex(of: ":") {
            field = line[..<colon]
            value = line[line.index(after: colon)...]
            if value.first == " " { value = value.dropFirst() }
        } else {
            field = line[...]
            value = ""
        }
        switch field {
        case "event": event = String(value)
        case "data": dataLines.append(String(value))
        case "id": if !value.contains("\0") { lastID = String(value) }
        default: break // retry and unknown fields are ignored
        }
        return nil
    }

    /// Splits a byte stream into events. Handles `\n`, `\r\n` and lone `\r` terminators.
    /// `URLSession.AsyncBytes.lines` drops empty lines, so the bytes are split manually.
    static func events<Bytes: AsyncSequence & Sendable>(
        from bytes: Bytes
    ) -> AsyncThrowingStream<SSEEvent, Error> where Bytes.Element == UInt8 {
        AsyncThrowingStream { continuation in
            let task = Task {
                var parser = SSEParser()
                var buffer: [UInt8] = []
                var previousWasCR = false
                do {
                    for try await byte in bytes {
                        if byte == 0x0A, previousWasCR { // second half of CRLF
                            previousWasCR = false
                            continue
                        }
                        previousWasCR = byte == 0x0D
                        if byte == 0x0A || byte == 0x0D {
                            let line = String(bytes: buffer, encoding: .utf8) ?? ""
                            buffer.removeAll(keepingCapacity: true)
                            if let event = parser.feed(line: line) { continuation.yield(event) }
                        } else {
                            buffer.append(byte)
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
