import ImageIO
@testable import Jol
import UIKit
import UniformTypeIdentifiers
import XCTest

func contentReply(_ text: String, status: Int = 200, _ request: URLRequest) -> (HTTPURLResponse, Data) {
    (StubURLProtocol.response(request.url!, status: status), Data(text.utf8))
}

let contentSlotJSON = """
{"upload_id":"55555555-5555-4555-8555-555555555555","url":"https://storage.example.test/bucket/ugc/a.jpg?sig=abc",\
"method":"PUT","headers":{"Content-Type":"image/jpeg"},"expires_at":"2026-11-21T15:00:00+00:00","max_bytes":8388608}
"""

let contentAcceptedJSON = """
{"id":"66666666-6666-4666-8666-666666666666","type":"photo","place":null,"status":"published_pending_review",\
"pending_review":true,"reason_codes":[],"payload":{},"photo_url":null,"created_at":"2026-11-21T10:00:00+00:00",\
"decided_at":null}
"""

let contentPlaceID = UUID(uuidString: UITestSupport.secondPlaceID)!

/// Ш-44: forms and EXIF stripping.
@MainActor
final class ContentTests: XCTestCase {
    // MARK: - A photo with GPS and EXIF

    /// A JPEG that carries GPS, EXIF, TIFF and an orientation tag, like a camera roll photo.
    static func photoWithMetadata(width: Int = 3000, height: Int = 2000, orientation: Int = 6) throws -> Data {
        let context = try XCTUnwrap(CGContext(
            data: nil, width: width, height: height, bitsPerComponent: 8, bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue
        ))
        context.setFillColor(UIColor.orange.cgColor)
        context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        context.setFillColor(UIColor.blue.cgColor)
        context.fill(CGRect(x: 0, y: 0, width: width / 2, height: height / 2))
        let image = try XCTUnwrap(context.makeImage())
        let metadata: [CFString: Any] = [
            kCGImagePropertyOrientation: orientation,
            kCGImagePropertyGPSDictionary: [
                kCGImagePropertyGPSLatitude: 43.2379, kCGImagePropertyGPSLatitudeRef: "N",
                kCGImagePropertyGPSLongitude: 76.9451, kCGImagePropertyGPSLongitudeRef: "E",
            ],
            kCGImagePropertyExifDictionary: [
                kCGImagePropertyExifDateTimeOriginal: "2026:11:21 10:00:00",
                kCGImagePropertyExifUserComment: "secret comment",
            ],
            kCGImagePropertyTIFFDictionary: [kCGImagePropertyTIFFMake: "Apple", kCGImagePropertyTIFFModel: "iPhone"],
        ]
        let output = NSMutableData()
        let type = UTType.jpeg.identifier as CFString
        let destination = try XCTUnwrap(CGImageDestinationCreateWithData(output, type, 1, nil))
        CGImageDestinationAddImage(destination, image, metadata as CFDictionary)
        XCTAssertTrue(CGImageDestinationFinalize(destination))
        return output as Data
    }

    private func properties(_ data: Data) throws -> [CFString: Any] {
        let source = try XCTUnwrap(CGImageSourceCreateWithData(data as CFData, nil))
        return try XCTUnwrap(CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any])
    }

    func testTheTestPhotoReallyCarriesGPSAndExif() throws {
        let original = try Self.photoWithMetadata()
        let props = try properties(original)
        XCTAssertNotNil(props[kCGImagePropertyGPSDictionary], "the fixture must have GPS")
        XCTAssertNotNil(props[kCGImagePropertyExifDictionary])
        XCTAssertNotNil(props[kCGImagePropertyTIFFDictionary])
        XCTAssertNotNil(original.range(of: Data("Exif".utf8)))
    }

    func testSanitizerRemovesGPSExifTIFFAndOrientation() throws {
        let clean = try PhotoSanitizer.clean(try Self.photoWithMetadata())
        let props = try properties(clean)
        XCTAssertNil(props[kCGImagePropertyGPSDictionary], "no GPS")
        XCTAssertNil(props[kCGImagePropertyTIFFDictionary], "no TIFF (make, model)")
        XCTAssertNil(props[kCGImagePropertyIPTCDictionary])
        XCTAssertNil(props[kCGImagePropertyOrientation], "no orientation tag: the picture is turned upright")
        let exif = props[kCGImagePropertyExifDictionary] as? [CFString: Any]
        XCTAssertNil(exif?[kCGImagePropertyExifDateTimeOriginal])
        XCTAssertNil(exif?[kCGImagePropertyExifUserComment])
        XCTAssertNil(clean.range(of: Data("Exif".utf8)), "no EXIF segment in the bytes")
        XCTAssertNil(clean.range(of: Data("Apple".utf8)))
        XCTAssertNil(clean.range(of: Data("secret".utf8)))
        XCTAssertEqual(Array(clean.prefix(3)), [0xFF, 0xD8, 0xFF], "a JPEG")
    }

    func testSanitizerAppliesOrientationAndShrinks() throws {
        // 3000 x 2000 with orientation 6 (rotate 90°): upright it is 2000 x 3000, shrunk to 2048 on the long side.
        let clean = try PhotoSanitizer.clean(try Self.photoWithMetadata())
        let props = try properties(clean)
        let width = try XCTUnwrap(props[kCGImagePropertyPixelWidth] as? Int)
        let height = try XCTUnwrap(props[kCGImagePropertyPixelHeight] as? Int)
        XCTAssertEqual(max(width, height), PhotoSanitizer.maxSide)
        XCTAssertGreaterThan(height, width, "portrait after the rotation")
        XCTAssertLessThanOrEqual(clean.count, PhotoSanitizer.maxBytes)
    }

    func testSmallPhotoIsNotEnlargedAndBrokenDataIsRefused() throws {
        let small = try PhotoSanitizer.clean(try Self.photoWithMetadata(width: 400, height: 300, orientation: 1))
        let props = try properties(small)
        XCTAssertEqual(props[kCGImagePropertyPixelWidth] as? Int, 400)
        XCTAssertEqual(props[kCGImagePropertyPixelHeight] as? Int, 300)
        XCTAssertThrowsError(try PhotoSanitizer.clean(Data("<html>not an image</html>".utf8))) {
            XCTAssertEqual($0 as? PhotoSanitizer.Failure, .unreadable)
        }
    }

    // MARK: - Forms

    func testReviewForm() throws {
        var draft = SubmissionDraft()
        XCTAssertEqual(draft.problems, [.rating], "a rating is required")
        draft.rating = 4
        draft.text = "  Nice place.\n"
        XCTAssertTrue(draft.isValid)
        XCTAssertEqual(draft.payload(uploadID: nil), ["rating": .int(4), "text": .string("Nice place.")])
        draft.text = "  "
        XCTAssertEqual(draft.payload(uploadID: nil), ["rating": .int(4)], "blank text is left out")
        draft.text = String(repeating: "a", count: 2001)
        XCTAssertEqual(draft.problems, [.textTooLong])
        draft.rating = 6
        XCTAssertTrue(draft.problems.contains(.rating))
    }

    func testMenuForm() {
        var draft = SubmissionDraft()
        draft.kind = .menu
        XCTAssertEqual(draft.problems, [.menuEmpty])
        draft.menuItems[0].name = " Plov  with  lamb "
        draft.menuItems[0].price = "2500"
        draft.menuItems.append(MenuItemDraft(name: "Tea", price: ""))
        draft.menuItems.append(MenuItemDraft())
        XCTAssertTrue(draft.isValid)
        XCTAssertEqual(draft.payload(uploadID: nil), ["items": .array([
            .object(["name": .string("Plov with lamb"), "price_kzt": .int(2500)]),
            .object(["name": .string("Tea")]),
        ])])
        draft.menuItems[1].price = "12a"
        XCTAssertEqual(draft.problems, [.menuPrice])
        draft.menuItems[1].price = "1000001"
        XCTAssertEqual(draft.problems, [.menuPrice], "above the server's limit")
        draft.menuItems[1].price = ""
        draft.menuItems.append(MenuItemDraft(name: "", price: "300"))
        XCTAssertEqual(draft.problems, [.menuName], "a price without a dish")
    }

    func testMenuWithOnlyAPhotoAndTheUploadID() throws {
        var draft = SubmissionDraft()
        draft.kind = .menu
        draft.menuItems = [MenuItemDraft()]
        draft.hasPhoto = true
        XCTAssertTrue(draft.isValid)
        let id = try XCTUnwrap(UUID(uuidString: "55555555-5555-4555-8555-555555555555"))
        XCTAssertEqual(draft.payload(uploadID: id), ["upload_id": .string("55555555-5555-4555-8555-555555555555")])
    }

    func testPhotoTransitAndPriceForms() {
        var photo = SubmissionDraft()
        photo.kind = .photo
        XCTAssertEqual(photo.problems, [.photoMissing])
        photo.hasPhoto = true
        photo.caption = " The  hall "
        XCTAssertEqual(photo.payload(uploadID: UUID(uuidString: "55555555-5555-4555-8555-555555555555")), [
            "upload_id": .string("55555555-5555-4555-8555-555555555555"), "caption": .string("The hall"),
        ])

        var transit = SubmissionDraft()
        transit.kind = .transit
        XCTAssertEqual(transit.problems, [.routeRef])
        transit.routeRef = " 92 "
        transit.interval = "0"
        XCTAssertEqual(transit.problems, [.interval])
        transit.interval = "241"
        XCTAssertEqual(transit.problems, [.interval])
        transit.interval = "12"
        transit.transitPrice = "-5"
        XCTAssertEqual(transit.problems, [.price], "a sign is not a number")
        transit.transitPrice = "120"
        transit.stop = "Abay / Dostyk"
        XCTAssertEqual(transit.payload(uploadID: nil), [
            "route_ref": .string("92"), "stop": .string("Abay / Dostyk"), "interval_min": .int(12),
            "price_kzt": .int(120),
        ])

        var price = SubmissionDraft()
        price.kind = .price
        XCTAssertEqual(price.problems, [.price], "the price is required")
        price.price = "1 500"
        XCTAssertEqual(price.problems, [.price], "digits only")
        price.price = "1500"
        price.audience = .student
        XCTAssertEqual(price.payload(uploadID: nil), ["price_kzt": .int(1500), "audience": .string("student")])
        price.price = "0"
        XCTAssertTrue(price.isValid, "free entry is a price too")
    }
}
