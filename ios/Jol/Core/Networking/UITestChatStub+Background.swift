#if DEBUG
import Foundation

extension ChatStub {
    // MARK: - Background live route (Ш-64)

    /// The recorded turn as the server now sends it: the `live_route` chunk is not in the message stream any more;
    /// `live_route_status building` follows the brief, and the text comes right after.
    static func backgroundLive(_ answer: Answer) -> Answer {
        var out = answer
        out.chunks = []
        var inserted = false
        for chunk in answer.chunks where !chunk.hasPrefix("event: live_route") {
            if !inserted, chunk.hasPrefix("event: text_delta") || chunk.hasPrefix("event: done") {
                out.chunks.append(statusChunk("building"))
                inserted = true
            }
            out.chunks.append(chunk)
            if !inserted, chunk.hasPrefix("event: brief_updated") {
                out.chunks.append(statusChunk("building"))
                inserted = true
            }
        }
        return out
    }

    static func statusChunk(_ state: String) -> String {
        "event: live_route_status\ndata: {\"state\": \"\(state)\"}\n\n"
    }
}
#endif
