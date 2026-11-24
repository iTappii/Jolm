@testable import Jol
import XCTest

/// Ш-66: the daily AI limit (429 `llm_budget_exceeded`) is told apart from a plain rate limit.
final class BudgetLimitTests: XCTestCase {
    private func response(_ status: Int, retryAfter: String?) -> HTTPURLResponse {
        let headers = retryAfter.map { ["Retry-After": $0] }
        return HTTPURLResponse(url: URL(string: "https://x.test")!, statusCode: status, httpVersion: nil,
                               headerFields: headers)!
    }

    private func body(_ code: String, _ message: String) -> Data {
        Data("{\"error\":{\"code\":\"\(code)\",\"message\":\"\(message)\"}}".utf8)
    }

    func testBudgetBodyKeepsItsCode() {
        let error = APIErrorBody.decode(response: response(429, retryAfter: "40000"),
                                        data: body("llm_budget_exceeded", "Лимит"))
        XCTAssertEqual(error, .server(status: 429, code: "llm_budget_exceeded", message: "Лимит"))
    }

    func testPlainRateLimitStaysRateLimited() {
        let error = APIErrorBody.decode(response: response(429, retryAfter: "30"), data: body("rate_limited", "Slow"))
        XCTAssertEqual(error, .rateLimited(retryAfter: 30, message: "Slow"))
    }

    func testFailureMapping() {
        let budget = APIError.server(status: 429, code: "llm_budget_exceeded", message: "Today is over")
        XCTAssertEqual(ChatModel.failure(for: budget), .budgetExceeded(message: "Today is over"))
        XCTAssertEqual(ChatModel.failure(for: APIError.server(status: 429, code: "llm_budget_exceeded", message: "")),
                       .budgetExceeded(message: ""))
        XCTAssertEqual(ChatModel.failure(for: APIError.rateLimited(retryAfter: 5, message: "")),
                       .rateLimited(retryAfter: 5))
        XCTAssertFalse(ChatFailure.budgetExceeded(message: "").canRetry)
        XCTAssertFalse(ChatFailure.budgetExceeded(message: "").offersNewChat)
        XCTAssertTrue(ChatFailure.full.offersNewChat)
        XCTAssertTrue(ChatFailure.rateLimited(retryAfter: 5).canRetry)
    }

    func testLongRetryAfterIsReadable() {
        let en = Locale(identifier: "en_US")
        XCTAssertEqual(RetryDelay.text(45, locale: en), "45s")
        XCTAssertEqual(RetryDelay.text(90, locale: en), "2m")
        let long = RetryDelay.text(40_000, locale: en)
        XCTAssertFalse(long.contains("40000"), long)
        XCTAssertEqual(long, "11h 7m")
    }
}
