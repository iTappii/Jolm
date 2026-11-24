import Foundation
import Observation

/// Dependency container: one instance per app launch, created in `JolApp` and injected through the
/// SwiftUI environment (`@Environment(AppContainer.self)`). Features take what they need from it.
@MainActor
@Observable
final class AppContainer {
    let language: LanguageSettings
    let auth: AuthState
    let installID: String
    @ObservationIgnored let api: APIClient
    @ObservationIgnored let tokens: any TokenStore
    @ObservationIgnored let places: PlacesModel
    @ObservationIgnored let directions: DirectionsModel
    @ObservationIgnored let gate: AccountGate
    @ObservationIgnored let favorites: FavoritesModel
    @ObservationIgnored let chat: ChatModel
    @ObservationIgnored let tripMap: TripMapModel
    @ObservationIgnored let events: EventsModel
    @ObservationIgnored let landmarks: LandmarksModel
    @ObservationIgnored let crowd: CrowdModel
    @ObservationIgnored let bookings: BookingModel
    @ObservationIgnored let offline: OfflineTripsModel
    @ObservationIgnored let devices: DeviceRegistrar
    @ObservationIgnored let analytics: AnalyticsClient
    @ObservationIgnored let reviews: ReviewsModel
    @ObservationIgnored let regions: RegionModel
    /// The last known position, only if access was already granted (Ш-70: «1,2 км от вас» on the card).
    @ObservationIgnored let locator: any LocationProviding

    init(
        tokens: any TokenStore = SessionStore.shared,
        defaults: UserDefaults = .standard,
        baseURL: Result<URL, APIError> = AppConfig.apiBaseURL,
        session: URLSession = .shared,
        locator: (any LocationProviding)? = nil,
        offlineStore: OfflineTripStore = OfflineTripStore(),
        push: any PushAuthorizing = SystemPushAuthorizing(),
        analyticsStore: AnalyticsQueueStore = AnalyticsQueueStore()
    ) {
        let auth = AuthState(tokens: tokens)
        let installID = InstallID.current(defaults: defaults)
        // UserDefaults is thread-safe; it just isn't annotated Sendable.
        nonisolated(unsafe) let languageDefaults = defaults
        let languageSettings = LanguageSettings(defaults: defaults)
        self.language = languageSettings
        self.auth = auth
        self.installID = installID
        self.tokens = tokens
        self.api = APIClient(
            baseURL: baseURL,
            tokens: tokens,
            installID: installID,
            session: session,
            language: { LanguageSettings.acceptLanguage(defaults: languageDefaults) },
            onSessionCleared: { Task { @MainActor in auth.refresh() } }
        )
        self.regions = RegionModel(api: self.api, defaults: defaults)
        self.places = PlacesModel(api: self.api)
        self.gate = AccountGate(auth: auth)
        self.favorites = FavoritesModel(api: self.api)
        let locator = locator ?? CoreLocationProvider()
        self.locator = locator
        self.chat = ChatModel(
            api: self.api, language: { languageSettings.code }, location: { locator.knownLocation() }
        )
        self.directions = DirectionsModel(api: self.api, locator: locator)
        self.offline = OfflineTripsModel(api: self.api, store: offlineStore)
        self.devices = DeviceRegistrar(
            api: self.api, installID: installID, language: { languageSettings.code }, defaults: defaults, push: push
        )
        JolAppDelegate.registrar = self.devices
        self.analytics = AnalyticsClient(
            api: self.api, store: analyticsStore, defaults: defaults, language: { languageSettings.code }
        )
        self.tripMap = TripMapModel(api: self.api, offline: self.offline)
        self.events = EventsModel(api: self.api)
        self.landmarks = LandmarksModel(api: self.api)
        self.crowd = CrowdModel(api: self.api, locator: locator)
        self.bookings = BookingModel(api: self.api)
        self.reviews = ReviewsModel(api: self.api)
    }

    func makeBonusModel() -> BonusModel {
        BonusModel(api: api, auth: auth)
    }

    func makeBookingsModel() -> MyBookingsModel {
        MyBookingsModel(api: api, auth: auth)
    }

    func makeProfileModel() -> ProfileModel {
        ProfileModel(service: AuthService(api: api, tokens: tokens), auth: auth)
    }
}
