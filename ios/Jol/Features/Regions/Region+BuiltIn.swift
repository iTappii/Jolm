import Foundation

extension Region {
    /// The region used before the server answers, offline and against a server without `/v1/regions`.
    /// Values are the ones the app had before regions (Ш-57): map centre and zoom of the first region, Almaty.
    /// This file and the UI-test stubs are the only places allowed to name the city (`.swiftlint.yml`).
    static let builtIn = Region(
        id: "almaty",
        name: Name(ru: "Алматы", en: "Almaty"),
        timezone: "Asia/Almaty",
        currency: "KZT",
        languages: ["ru", "en"],
        centre: Centre(lat: 43.2380, lon: 76.9450),
        camera: Camera(zoom: 11),
        bbox: [76.70, 42.95, 77.30, 43.45],
        isDefault: true
    )
}
