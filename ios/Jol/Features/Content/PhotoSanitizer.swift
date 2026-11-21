import CoreGraphics
import Foundation
import ImageIO
import UIKit
import UniformTypeIdentifiers

/// Prepares a picked photo for upload (SSOT §10, Ш-44): the server does not strip EXIF or GPS, so the app does.
/// The picture is decoded, turned upright, shrunk to `maxSide` and drawn into a fresh opaque bitmap, which is then
/// encoded as JPEG with no metadata at all (no EXIF, GPS, TIFF, IPTC, maker notes, thumbnail).
enum PhotoSanitizer {
    enum Failure: Error, Equatable {
        case unreadable
        case tooLarge
    }

    static let maxSide = 2048
    /// The server takes up to 8 MB; leave room.
    static let maxBytes = 7_000_000
    private static let qualities: [CGFloat] = [0.8, 0.65, 0.5, 0.35]

    /// JPEG bytes without metadata, at most `maxSide` on the longer side and `maxBytes` long.
    static func clean(_ data: Data) throws -> Data {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil), CGImageSourceGetCount(source) > 0 else {
            throw Failure.unreadable
        }
        let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]
        let width = (properties?[kCGImagePropertyPixelWidth] as? Int) ?? 0
        let height = (properties?[kCGImagePropertyPixelHeight] as? Int) ?? 0
        guard width > 0, height > 0 else { throw Failure.unreadable }
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true, // upright: the orientation tag goes away with the rest
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceThumbnailMaxPixelSize: min(maxSide, max(width, height)),
        ]
        guard let decoded = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else {
            throw Failure.unreadable
        }
        let flat = try opaque(decoded)
        for quality in qualities {
            let jpeg = try encode(flat, quality: quality)
            if jpeg.count <= maxBytes { return jpeg }
        }
        throw Failure.tooLarge
    }

    /// A new bitmap with a white background: no alpha for JPEG, and no leftovers of the source's colour space metadata.
    private static func opaque(_ image: CGImage) throws -> CGImage {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let size = CGSize(width: image.width, height: image.height)
        let rendered = UIGraphicsImageRenderer(size: size, format: format).image { context in
            UIColor.white.setFill()
            context.fill(CGRect(origin: .zero, size: size))
            UIImage(cgImage: image).draw(in: CGRect(origin: .zero, size: size))
        }
        guard let result = rendered.cgImage else { throw Failure.unreadable }
        return result
    }

    private static func encode(_ image: CGImage, quality: CGFloat) throws -> Data {
        let output = NSMutableData()
        let type = UTType.jpeg.identifier as CFString
        guard let destination = CGImageDestinationCreateWithData(output, type, 1, nil) else {
            throw Failure.unreadable
        }
        // Only the quality: no properties dictionary with metadata is ever passed.
        CGImageDestinationAddImage(
            destination, image, [kCGImageDestinationLossyCompressionQuality: quality] as CFDictionary
        )
        guard CGImageDestinationFinalize(destination) else { throw Failure.unreadable }
        return dropMetadataSegments(output as Data)
    }

    /// ImageIO writes a small EXIF block (pixel size, colour space) even when it is given no metadata. It holds nothing
    /// personal, but "no EXIF" is easier to promise and to check when the bytes have none: every application segment
    /// except JFIF (`APP0`) and the colour profile (`APP2`) is cut out of the JPEG header.
    static func dropMetadataSegments(_ jpeg: Data) -> Data {
        let bytes = [UInt8](jpeg)
        guard bytes.count > 4, bytes[0] == 0xFF, bytes[1] == 0xD8 else { return jpeg }
        var result: [UInt8] = [0xFF, 0xD8]
        var index = 2
        while index + 4 <= bytes.count, bytes[index] == 0xFF {
            let marker = bytes[index + 1]
            if marker == 0xDA { break } // start of the image data: the rest is copied as is
            let length = Int(bytes[index + 2]) << 8 | Int(bytes[index + 3])
            guard length >= 2, index + 2 + length <= bytes.count else { return jpeg }
            let isApplication = (0xE0...0xEF).contains(marker)
            let keep = !isApplication || marker == 0xE0 || marker == 0xE2
            if keep { result += bytes[index..<(index + 2 + length)] }
            index += 2 + length
        }
        result += bytes[index...]
        return Data(result)
    }
}
