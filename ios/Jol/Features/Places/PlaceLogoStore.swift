import UIKit

/// Venue logos for the map pins (Ш-70): downloaded once, cut to a small round pin with a white ring, kept in memory.
/// A logo that fails to load is not retried within the session; the pin stays the category icon.
@MainActor
final class PlaceLogoStore {
    static let shared = PlaceLogoStore()
    static let diameter: CGFloat = 34

    private let cache = NSCache<NSString, UIImage>()
    private var inFlight: [String: Task<UIImage?, Never>] = [:]
    private var failed: Set<String> = []
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    func pinImage(for urlString: String) async -> UIImage? {
        if let cached = cache.object(forKey: urlString as NSString) { return cached }
        if failed.contains(urlString) { return nil }
        if let task = inFlight[urlString] { return await task.value }
        let session = session
        let task = Task { () -> UIImage? in
            guard let source = await Self.fetch(urlString, session: session) else { return nil }
            return Self.round(source, diameter: Self.diameter)
        }
        inFlight[urlString] = task
        let image = await task.value
        inFlight[urlString] = nil
        if let image { cache.setObject(image, forKey: urlString as NSString) } else { failed.insert(urlString) }
        return image
    }

    nonisolated private static func fetch(_ urlString: String, session: URLSession) async -> UIImage? {
        #if DEBUG
        // UI tests: `asset:<name>` is an image bundled in the app (the stub has no media server).
        if urlString.hasPrefix("asset:") {
            return await MainActor.run { UIImage(named: String(urlString.dropFirst(6))) }
        }
        #endif
        guard let url = URL(string: urlString), url.scheme == "https" || url.scheme == "http" else { return nil }
        guard let (data, response) = try? await session.data(from: url),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }
        return UIImage(data: data)
    }

    /// A centred square crop of `source` in a circle with a white ring and a hairline shadow edge.
    nonisolated static func round(_ source: UIImage, diameter: CGFloat) -> UIImage {
        let size = CGSize(width: diameter, height: diameter)
        return UIGraphicsImageRenderer(size: size).image { context in
            let rect = CGRect(origin: .zero, size: size).insetBy(dx: 1.5, dy: 1.5)
            UIColor.white.setFill()
            UIBezierPath(ovalIn: CGRect(origin: .zero, size: size)).fill()
            context.cgContext.saveGState()
            UIBezierPath(ovalIn: rect.insetBy(dx: 1, dy: 1)).addClip()
            let side = min(source.size.width, source.size.height)
            let scale = (diameter - 5) / max(side, 1)
            let drawn = CGSize(width: source.size.width * scale, height: source.size.height * scale)
            source.draw(in: CGRect(
                x: (size.width - drawn.width) / 2, y: (size.height - drawn.height) / 2,
                width: drawn.width, height: drawn.height
            ))
            context.cgContext.restoreGState()
            UIColor.black.withAlphaComponent(0.18).setStroke()
            let edge = UIBezierPath(ovalIn: CGRect(origin: .zero, size: size).insetBy(dx: 0.5, dy: 0.5))
            edge.lineWidth = 1
            edge.stroke()
        }
    }
}
