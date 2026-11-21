import ImageIO
@testable import Jol
import UIKit
import XCTest

/// Ш-44: the upload → PUT → submission flow, request shapes, reviews of a place.
private func reviewsPage(_ ids: [String], next: String?, count: Int = 3) -> String {
    let items = ids.map {
        "{\"id\":\"\($0)\",\"rating\":4,\"text\":\"t\($0)\",\"author_name\":null,"
            + "\"created_at\":\"2026-11-20T12:00:00.123456+00:00\",\"pending_review\":true}"
    }
    let cursor = next.map { "\"\($0)\"" } ?? "null"
    return "{\"items\":[\(items.joined(separator: ","))],\"next_cursor\":\(cursor),"
        + "\"summary\":{\"count\":\(count),\"average\":4.0}}"
}

@MainActor
final class ContentFlowTests: XCTestCase {
    private let base = URL(string: "https://api.example.test")!

    private func makeAPI() -> APIClient {
        APIClient(
            baseURL: .success(base), tokens: MemoryTokenStore(), installID: "install-1",
            session: StubURLProtocol.session(), language: { "en" }, onSessionCleared: {}
        )
    }

    private func requests(_ path: String) -> [URLRequest] {
        StubURLProtocol.requests.filter { $0.url?.path == path }
    }

    private func jsonBody(_ request: URLRequest) throws -> [String: Any] {
        let data = try XCTUnwrap(request.httpBody)
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }

    // MARK: - Request shapes

    func testSubmissionRequestBody() throws {
        let request = SubmissionRequest(type: .price, placeID: contentPlaceID, payload: ["price_kzt": .int(1500)])
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as? [String: Any])
        XCTAssertEqual(object["type"] as? String, "price")
        XCTAssertEqual(object["place_id"] as? String, UITestSupport.secondPlaceID)
        XCTAssertEqual((object["payload"] as? [String: Any])?["price_kzt"] as? Int, 1500)
        XCTAssertEqual(Set(object.keys), ["type", "place_id", "payload"], "the server forbids extra fields")
    }

    func testReviewIsSentWithoutAnUpload() async throws {
        StubURLProtocol.install { contentReply(contentAcceptedJSON, status: 201, $0) }
        let model = ContentModel(api: makeAPI())
        var draft = SubmissionDraft()
        draft.rating = 5
        draft.text = "Great"
        let sent = await model.submit(draft, placeID: contentPlaceID)
        XCTAssertTrue(sent)
        XCTAssertTrue(requests("/v1/uploads").isEmpty, "no photo, no upload slot")
        let body = try jsonBody(try XCTUnwrap(requests("/v1/submissions").first))
        XCTAssertEqual(body["type"] as? String, "review")
        XCTAssertEqual((body["payload"] as? [String: Any])?["rating"] as? Int, 5)
        guard case .done(let result) = model.stage else { return XCTFail("done") }
        XCTAssertTrue(result.pendingReview)
        XCTAssertFalse(result.isRejected)
    }

    func testInvalidFormIsNotSent() async {
        StubURLProtocol.install { contentReply(contentAcceptedJSON, status: 201, $0) }
        let model = ContentModel(api: makeAPI())
        let sent = await model.submit(SubmissionDraft(), placeID: contentPlaceID)
        XCTAssertFalse(sent)
        XCTAssertTrue(StubURLProtocol.requests.isEmpty)
    }

    func testPhotoFlowAskForSlotThenPutThenSubmit() async throws {
        StubURLProtocol.install { request in
            switch (request.httpMethod, request.url?.host) {
            case ("POST", "api.example.test") where request.url?.path == "/v1/uploads":
                return contentReply(contentSlotJSON, status: 201, request)
            case ("PUT", "storage.example.test"): return contentReply("", request)
            default: return contentReply(contentAcceptedJSON, status: 201, request)
            }
        }
        let model = ContentModel(api: makeAPI())
        await model.setPhoto(data: try ContentTests.photoWithMetadata(width: 800, height: 600, orientation: 1))
        let photo = try XCTUnwrap(model.photo)
        var draft = SubmissionDraft()
        draft.kind = .photo
        draft.hasPhoto = true
        draft.caption = "Hall"
        let sent = await model.submit(draft, placeID: contentPlaceID)
        XCTAssertTrue(sent)

        let slotBody = try jsonBody(try XCTUnwrap(requests("/v1/uploads").first))
        XCTAssertEqual(slotBody["content_type"] as? String, "image/jpeg")
        XCTAssertEqual(slotBody["size_bytes"] as? Int, photo.jpeg.count, "the announced size is the real one")

        let put = try XCTUnwrap(StubURLProtocol.requests.first { $0.httpMethod == "PUT" })
        XCTAssertEqual(put.url?.absoluteString, "https://storage.example.test/bucket/ugc/a.jpg?sig=abc")
        XCTAssertEqual(put.value(forHTTPHeaderField: "Content-Type"), "image/jpeg")
        XCTAssertEqual(put.httpBody, photo.jpeg, "exactly the cleaned bytes")
        XCTAssertNil(put.value(forHTTPHeaderField: "Authorization"), "the token never goes to the storage")
        XCTAssertNil(put.value(forHTTPHeaderField: "X-Install-ID"))

        let submission = try jsonBody(try XCTUnwrap(requests("/v1/submissions").first))
        let payload = try XCTUnwrap(submission["payload"] as? [String: Any])
        XCTAssertEqual(payload["upload_id"] as? String, "55555555-5555-4555-8555-555555555555")
        XCTAssertEqual(payload["caption"] as? String, "Hall")
    }

    func testRetryAfterAFailedSubmissionDoesNotUploadAgain() async throws {
        let failOnce = Flag()
        StubURLProtocol.install { request in
            if request.httpMethod == "PUT" { return contentReply("", request) }
            if request.url?.path == "/v1/uploads" { return contentReply(contentSlotJSON, status: 201, request) }
            if failOnce.take() { throw URLError(.notConnectedToInternet) }
            return contentReply(contentAcceptedJSON, status: 201, request)
        }
        let model = ContentModel(api: makeAPI())
        await model.setPhoto(data: try ContentTests.photoWithMetadata(width: 400, height: 300, orientation: 1))
        var draft = SubmissionDraft()
        draft.kind = .photo
        draft.hasPhoto = true
        let first = await model.submit(draft, placeID: contentPlaceID)
        XCTAssertFalse(first)
        XCTAssertEqual(model.stage, .failed(.network))
        let second = await model.submit(draft, placeID: contentPlaceID)
        XCTAssertTrue(second)
        XCTAssertEqual(requests("/v1/uploads").count, 1, "a slot is a daily quota: the retry reuses it")
        XCTAssertEqual(StubURLProtocol.requests.filter { $0.httpMethod == "PUT" }.count, 1)
    }

    func testRejectedByTheFilterIsADoneResultNotAnError() async throws {
        let rejected = contentAcceptedJSON.replacingOccurrences(of: "published_pending_review", with: "rejected_auto")
            .replacingOccurrences(
                of: "\"pending_review\":true,\"reason_codes\":[]",
                with: "\"pending_review\":false,\"reason_codes\":[\"spam\"]"
            )
        StubURLProtocol.install { contentReply(rejected, status: 201, $0) }
        let model = ContentModel(api: makeAPI())
        var draft = SubmissionDraft()
        draft.rating = 1
        draft.text = "buy now"
        let sent = await model.submit(draft, placeID: contentPlaceID)
        XCTAssertTrue(sent)
        guard case .done(let result) = model.stage else { return XCTFail("done") }
        XCTAssertTrue(result.isRejected)
        XCTAssertEqual(result.reasonCodes, ["spam"])
    }

    func testFailuresAreTold() {
        func failure(_ error: Error) -> ContentModel.Failure { ContentModel.failure(for: error) }
        XCTAssertEqual(failure(APIError.server(status: 409, code: "already_submitted", message: "")), .alreadySubmitted)
        XCTAssertEqual(failure(APIError.server(status: 422, code: "invalid_image", message: "")), .imageRefused)
        XCTAssertEqual(failure(APIError.server(status: 422, code: "upload_not_found", message: "")), .imageRefused)
        XCTAssertEqual(failure(APIError.rateLimited(retryAfter: 3600, message: "")), .tooMany)
        XCTAssertEqual(failure(APIError.network(URLError(.timedOut))), .network)
        XCTAssertEqual(failure(APIError.server(status: 503, code: "storage_unavailable", message: "")),
                       .server("storage_unavailable"))
    }

    func testAnUnreadablePhotoIsAFailureAndAddsNothing() async {
        let model = ContentModel(api: makeAPI())
        await model.setPhoto(data: Data("nope".utf8))
        XCTAssertEqual(model.stage, .failed(.photoUnreadable))
        XCTAssertNil(model.photo)
    }

    func testStorageURLMustBeHTTPSOrLoopback() async {
        StubURLProtocol.install { contentReply("", $0) }
        let api = makeAPI()
        do {
            try await api.upload(to: URL(string: "http://storage.example.test/x")!, headers: [:], body: Data([1]))
            XCTFail("plain http to a remote host")
        } catch {
            XCTAssertEqual(error as? APIError, .invalidResponse)
        }
        do {
            let local = URL(string: "http://localhost:8000/v1/dev-uploads/x")!
            try await api.upload(to: local, headers: [:], body: Data([1]))
        } catch {
            XCTFail("loopback http is the dev server: \(error)")
        }
    }

    // MARK: - Reviews

    func testReviewsPageWithCursorAndNoDuplicates() async throws {
        StubURLProtocol.install { request in
            let cursor = URLComponents(url: request.url!, resolvingAgainstBaseURL: false)?
                .queryItems?.first { $0.name == "cursor" }?.value
            let body = cursor == nil ? reviewsPage(["a", "b"], next: "c1") : reviewsPage(["b", "c"], next: nil)
            return contentReply(body, request)
        }
        let model = ReviewsModel(api: makeAPI())
        await model.load(placeID: contentPlaceID)
        XCTAssertEqual(model.items.map(\.id), ["a", "b"])
        XCTAssertEqual(model.summary, ReviewsSummary(count: 3, average: 4.0))
        XCTAssertNotNil(model.items.first?.date, "fractional seconds and an offset are read")
        let first = try XCTUnwrap(requests("/v1/places/\(UITestSupport.secondPlaceID)/reviews").first)
        XCTAssertTrue(first.url?.query?.contains("limit=20") ?? false)
        XCTAssertFalse(first.url?.query?.contains("cursor=") ?? true, "the first page has no cursor")

        await model.loadMore()
        XCTAssertEqual(model.items.map(\.id), ["a", "b", "c"], "the repeated review is dropped")
        XCTAssertNil(model.nextCursor)
        await model.loadMore()
        XCTAssertEqual(requests("/v1/places/\(UITestSupport.secondPlaceID)/reviews").count, 2, "no cursor, no request")
    }

    func testEmptyReviewsAndFailureAndAnotherPlace() async {
        let none = "{\"items\":[],\"next_cursor\":null,\"summary\":{\"count\":0,\"average\":null}}"
        StubURLProtocol.install { contentReply(none, $0) }
        let model = ReviewsModel(api: makeAPI())
        await model.load(placeID: contentPlaceID)
        XCTAssertEqual(model.phase, .loaded)
        XCTAssertTrue(model.items.isEmpty)
        XCTAssertNil(model.summary?.average)

        StubURLProtocol.install { _ in throw URLError(.notConnectedToInternet) }
        await model.load(placeID: UUID())
        XCTAssertEqual(model.phase, .failed, "another place starts from scratch and shows the failure")
        XCTAssertTrue(model.items.isEmpty)
    }

    func testReviewDecodesWithoutAnAuthorName() throws {
        let json = """
        {"id":"x","rating":5,"text":null,"author_name":null,"created_at":"2026-11-20T12:00:00+00:00",\
        "pending_review":false}
        """
        let data = Data(json.utf8)
        let review = try JSONDecoder().decode(PlaceReview.self, from: data)
        XCTAssertNil(review.authorName)
        XCTAssertNil(review.text)
        XCTAssertFalse(review.pendingReview)
    }
}

private final class Flag: @unchecked Sendable {
    private let lock = NSLock()
    private var armed = true

    /// `true` the first time only.
    func take() -> Bool {
        lock.lock(); defer { lock.unlock() }
        defer { armed = false }
        return armed
    }
}
