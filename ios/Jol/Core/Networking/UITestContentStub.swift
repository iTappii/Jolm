#if DEBUG
import Foundation

/// Stub of the content endpoints for UI tests (`-JolStubAPI`, Ш-44):
/// - `GET /v1/places/{id}/reviews`: two reviews for the fixture cafe, none for the museum (the empty state);
/// - `POST /v1/uploads`: a slot whose URL is on the stub's own host, `PUT` of the file answers 200;
/// - `POST /v1/submissions`: 401 without a session; 201 `published_pending_review`; a review whose text contains
///   "spam" gets `rejected_auto`; "again" gets 409 `already_submitted`; a missing `place_id` (not for transit) is 422.
enum UITestContent {
    static func answer(method: String, path: String, payload: [String: Any], signedIn: Bool)
        -> UITestPlaceActions.Answer? {
        if method == "GET", path.hasPrefix("/v1/places/"), path.hasSuffix("/reviews") {
            let id = path.dropFirst("/v1/places/".count).dropLast("/reviews".count)
            return UITestPlaceActions.Answer(body: reviewsJSON(placeID: String(id)))
        }
        if method == "PUT", path.hasPrefix("/v1/dev-uploads/") { return UITestPlaceActions.Answer(body: "") }
        guard method == "POST", path == "/v1/uploads" || path == "/v1/submissions" else { return nil }
        guard signedIn else { return failure(401, "unauthorized") }
        if path == "/v1/uploads" {
            return UITestPlaceActions.Answer(status: 201, body: """
            {"upload_id":"55555555-5555-4555-8555-555555555555","url":"http://localhost:8000/v1/dev-uploads/stub",\
            "method":"PUT","headers":{"Content-Type":"image/jpeg"},"expires_at":"2026-11-21T15:00:00+00:00",\
            "max_bytes":8388608}
            """)
        }
        return submission(payload)
    }

    private static func failure(_ status: Int, _ code: String) -> UITestPlaceActions.Answer {
        UITestPlaceActions.Answer(status: status, body: "{\"error\":{\"code\":\"\(code)\",\"message\":\"stub\"}}")
    }

    private static func submission(_ payload: [String: Any]) -> UITestPlaceActions.Answer {
        let type = payload["type"] as? String ?? ""
        let body = payload["payload"] as? [String: Any] ?? [:]
        if type != "transit", payload["place_id"] == nil { return failure(422, "validation_error") }
        let text = (body["text"] as? String) ?? ""
        if type == "review", text.contains("again") { return failure(409, "already_submitted") }
        let spam = type == "review" && text.contains("spam")
        let status = spam ? "rejected_auto" : "published_pending_review"
        return UITestPlaceActions.Answer(status: 201, body: """
        {"id":"66666666-6666-4666-8666-666666666666","type":"\(type)","place":null,"status":"\(status)",\
        "pending_review":\(!spam),"reason_codes":\(spam ? "[\"spam\"]" : "[]"),"payload":{},"photo_url":null,\
        "created_at":"2026-11-21T10:00:00+00:00","decided_at":null}
        """)
    }

    static func reviewsJSON(placeID: String) -> String {
        guard placeID == UITestSupport.secondPlaceID else {
            return "{\"items\":[],\"next_cursor\":null,\"summary\":{\"count\":0,\"average\":null}}"
        }
        return """
        {"items":[{"id":"77777777-7777-4777-8777-777777777771","rating":5,"text":"Great coffee and a calm room.",\
        "author_name":null,"created_at":"2026-11-20T12:00:00+00:00","pending_review":true},\
        {"id":"77777777-7777-4777-8777-777777777772","rating":4,"text":"Good, a bit crowded at noon.",\
        "author_name":"Aigerim","created_at":"2026-11-18T09:30:00.123456+00:00","pending_review":false}],\
        "next_cursor":null,"summary":{"count":2,"average":4.5}}
        """
    }
}
#endif
