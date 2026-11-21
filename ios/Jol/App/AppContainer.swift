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

    init(
        tokens: any TokenStore = SessionStore.shared,
        defaults: UserDefaults = .standard,
        baseURL: Result<URL, APIError> = AppConfig.apiBaseURL,
        session: URLSession = .shared,
        locator: (any LocationProviding)? = nil
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
        self.places = PlacesModel(api: self.api)
        self.gate = AccountGate(auth: auth)
        self.favorites = FavoritesModel(api: self.api)
        self.chat = ChatModel(api: self.api, language: { languageSettings.code })
        self.directions = DirectionsModel(api: self.api, locator: locator ?? CoreLocationProvider())
    }

    func makeProfileModel() -> ProfileModel {
        ProfileModel(service: AuthService(api: api, tokens: tokens), auth: auth)
    }
}
