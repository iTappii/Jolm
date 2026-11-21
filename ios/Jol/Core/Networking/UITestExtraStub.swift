#if DEBUG
import Foundation

/// Stub of the endpoints added after the first UI tests (`-JolStubAPI`): the offline copy of a trip (Ш-42), the bonus
/// account (Ш-46), device registration (Ш-40) and analytics events (Ш-50). `-JolStubOffline` makes every call fail
/// like a missing connection (a second launch of the same test shows what the device saved).
enum UITestExtraStub {
    static var isOffline: Bool { ProcessInfo.processInfo.arguments.contains("-JolStubOffline") }

    /// `-JolResetOffline`: the first launch of a test starts without downloads left by an earlier test.
    static var resetsOffline: Bool { ProcessInfo.processInfo.arguments.contains("-JolResetOffline") }

    static let offlineETag = "\"v1-en\""

    static func answer(
        method: String, path: String, ifNoneMatch: String?, signedIn: Bool
    ) -> UITestPlaceActions.Answer? {
        let parts = path.split(separator: "/").map(String.init)
        if method == "GET", parts.count == 4, parts[1] == "trips", parts[3] == "offline" {
            guard signedIn else { return failure(401, "unauthorized") }
            guard [ChatStub.tripID, ChatStub.oldTripID].contains(parts[2]) else { return failure(404, "not_found") }
            if ifNoneMatch == offlineETag {
                return UITestPlaceActions.Answer(status: 304, headers: ["ETag": offlineETag], body: "")
            }
            return UITestPlaceActions.Answer(headers: ["ETag": offlineETag], body: offlineJSON(tripID: parts[2]))
        }
        if method == "GET", path == "/v1/me/bonuses" {
            return signedIn ? UITestPlaceActions.Answer(body: bonusesJSON) : failure(401, "unauthorized")
        }
        if method == "POST", path == "/v1/devices" {
            return UITestPlaceActions.Answer(
                body: "{\"install_id\":\"00000000-0000-4000-8000-000000000002\",\"user_linked\":\(signedIn),"
                    + "\"push_enabled\":false}"
            )
        }
        if method == "POST", path == "/v1/analytics/events" {
            return UITestPlaceActions.Answer(body: "{\"accepted\":1,\"duplicates\":0,\"rejected\":0}")
        }
        return nil
    }

    private static func failure(_ status: Int, _ code: String) -> UITestPlaceActions.Answer {
        UITestPlaceActions.Answer(
            status: status, body: "{\"error\":{\"code\":\"\(code)\",\"message\":\"stub\"}}"
        )
    }

    // MARK: - Bonuses

    static let bonusesJSON = """
    {"balance":240,"tenge_per_bonus":1,"next_cursor":null,"items":[\
    {"id":"c0000000-0000-4000-8000-000000000001","amount":188,"kind":"accrual",\
    "submission_id":"d0000000-0000-4000-8000-000000000001","submission_type":"menu",\
    "created_at":"2026-11-20T12:00:00+05:00"},\
    {"id":"c0000000-0000-4000-8000-000000000002","amount":52,"kind":"accrual",\
    "submission_id":"d0000000-0000-4000-8000-000000000002","submission_type":"review",\
    "created_at":"2026-11-18T09:30:00+05:00"}]}
    """

    // MARK: - Offline copy

    private static let museumPlace = "11111111-1111-4111-8111-111111111111"
    private static let cafePlace = "22222222-2222-4222-8222-222222222222"

    private static func item(_ id: String, _ order: Int, _ place: String, _ day: String,
                             _ times: (String, String), must: Bool = false) -> String {
        let (from, to) = times
        return "{\"id\":\"\(id)\",\"ord\":\(order),\"kind\":\"activity\",\"meal\":null,\"place_id\":\"\(place)\","
            + "\"starts_at\":\"\(day)T\(from):00+05:00\",\"ends_at\":\"\(day)T\(to):00+05:00\",\"visit_min\":90,"
            + "\"must_have\":\(must),\"est_cost_kzt\":3000}"
    }

    private static func leg(_ id: String, _ from: String, _ to: String, _ day: String, _ at: String) -> String {
        "{\"id\":\"\(id)\",\"from_item_id\":\"\(from)\",\"to_item_id\":\"\(to)\","
            + "\"depart_at\":\"\(day)T\(at):00+05:00\","
            + "\"travel_s\":780,\"estimated\":false,\"mode\":\"bus\",\"cost_kzt\":120,\"distance_m\":2400,"
            + "\"geometry\":\"oprmqAotvvqCwyEotLwyEozD\"}"
    }

    static func offlineJSON(tripID: String) -> String {
        let (museum, cafe) = (TripStub.museumItem, TripStub.cafeItem)
        let (dayOne, dayTwo) = ("2026-12-05", "2026-12-06")
        let lat = AlmatyCamera.center.latitude
        let lon = AlmatyCamera.center.longitude
        return """
        {"trip_id":"\(tripID)","version":1,"locale":"en","timezone":"Asia/Almaty","geometry_encoding":"polyline6",\
        "start_date":"\(dayOne)","end_date":"\(dayTwo)","budget_kzt":100000,"total_cost_kzt":90000,"days":[\
        {"date":"\(dayOne)","items":[\(item(museum, 1, museumPlace, dayOne, ("09:30", "11:00"), must: true)),\
        \(item(cafe, 2, cafePlace, dayOne, ("12:00", "13:30")))],\
        "legs":[\(leg(TripStub.legOne, museum, cafe, dayOne, "11:00"))]},\
        {"date":"\(dayTwo)","items":[\(item(TripStub.dayTwoCafeItem, 1, cafePlace, dayTwo, ("10:00", "11:30")))],\
        "legs":[]}],\
        "places":{"\(museumPlace)":{"name":"Fixture Museum","name_lang":"en","names":{"en":"Fixture Museum"},\
        "category":"museum","category_name":"Museum","lat":\(lat),"lon":\(lon),"address":"1 Test Street",\
        "hours":[{"weekday":5,"intervals":[{"opens":"10:00","closes":"18:00"}]}],"photo_url":null},\
        "\(cafePlace)":{"name":"Fixture Cafe","name_lang":"en","names":{"en":"Fixture Cafe"},\
        "category":"coffee","category_name":"Coffee","lat":\(lat + 0.01),"lon":\(lon + 0.012),\
        "address":"2 Test Street","hours":[],"photo_url":null}}}
        """
    }
}

extension FixtureURLProtocol {
    /// Sends one stub answer (status, headers, body) and finishes.
    func finish(with answer: UITestPlaceActions.Answer) {
        var headers = ["Content-Type": "application/json"]
        headers.merge(answer.headers) { _, new in new }
        let response = HTTPURLResponse(
            url: request.url ?? URL(fileURLWithPath: "/"), statusCode: answer.status, httpVersion: "HTTP/1.1",
            headerFields: headers
        )!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        if answer.status != 304 { client?.urlProtocol(self, didLoad: Data(answer.body.utf8)) }
        client?.urlProtocolDidFinishLoading(self)
    }
}
#endif
