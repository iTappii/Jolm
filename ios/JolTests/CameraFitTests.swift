@testable import Jol
import CoreLocation
import XCTest

/// Ш-63: the camera maths for the live route and the trip map.
final class CameraFitTests: XCTestCase {
    private func point(_ lat: Double, _ lon: Double) -> CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: lat, longitude: lon)
    }

    func testNoCoordinatesNoPlan() {
        XCTAssertNil(CameraFit.plan(for: [], singleZoom: 15))
    }

    func testSingleStopIsCentredAtClampedZoom() {
        let plan = CameraFit.plan(for: [point(43.238, 76.945)], singleZoom: CameraFit.singleStopZoom)
        XCTAssertEqual(plan, .center(point(43.238, 76.945), zoom: 15))
    }

    func testStopsOnTopOfEachOtherCountAsSingle() {
        let plan = CameraFit.plan(for: [point(43.238, 76.945), point(43.2381, 76.9451)], singleZoom: 15)
        guard case .center(_, let zoom) = plan else { return XCTFail("expected center") }
        XCTAssertEqual(zoom, 15)
    }

    func testSeveralStopsAreFitted() {
        let plan = CameraFit.plan(for: [point(43.238, 76.945), point(43.26, 76.95)], singleZoom: 15)
        XCTAssertEqual(plan, .bounds)
    }

    func testPaddingKeepsRouteAboveTheCard() {
        // Card opened: the content inset has not caught up yet, so the padding covers the difference.
        let opening = CameraFit.liveRoutePadding(mapHeight: 850, targetInset: 400, currentInset: 0)
        XCTAssertEqual(opening.bottom, 484)
        XCTAssertEqual(opening.top, 72)
        // Settled: only the margin.
        XCTAssertEqual(CameraFit.liveRoutePadding(mapHeight: 850, targetInset: 400, currentInset: 400).bottom, 84)
    }

    func testCollapsedCardNeedsOnlyTheMargin() {
        let collapsing = CameraFit.liveRoutePadding(mapHeight: 850, targetInset: 0, currentInset: 400)
        XCTAssertEqual(collapsing.bottom, 84)
    }

    func testKeyboardStripGetsTightMargins() {
        let padding = CameraFit.liveRoutePadding(mapHeight: 850, targetInset: 600, currentInset: 600)
        XCTAssertEqual(padding.top, 56)
        XCTAssertEqual(padding.bottom, 52)
    }
}
