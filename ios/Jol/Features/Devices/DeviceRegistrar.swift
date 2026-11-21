import Foundation
import UIKit
import UserNotifications

/// Where the notification permission and the APNs registration come from (the system; a fake in tests).
@MainActor
protocol PushAuthorizing {
    /// `true` once the person allowed notifications; `false` when denied; `nil` while they were never asked.
    func isAuthorized() async -> Bool?
    /// Shows the system question; `true` when allowed.
    func requestAuthorization() async -> Bool
    /// Asks iOS for an APNs token; it arrives in `JolAppDelegate`.
    func registerForRemoteNotifications()
}

struct SystemPushAuthorizing: PushAuthorizing {
    func isAuthorized() async -> Bool? {
        switch await UNUserNotificationCenter.current().notificationSettings().authorizationStatus {
        case .notDetermined: nil
        case .denied: false
        default: true
        }
    }

    func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        return (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
    }

    func registerForRemoteNotifications() {
        UIApplication.shared.registerForRemoteNotifications()
    }
}

/// `POST /v1/devices` body (Ш-40). `apns_token` is always present: `null` until iOS hands out a token.
struct DeviceRegistration: Encodable, Equatable, Sendable {
    let installID: String
    let apnsToken: String?
    let language: String

    enum CodingKeys: String, CodingKey {
        case installID = "install_id"
        case apnsToken = "apns_token"
        case language
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(installID, forKey: .installID)
        try container.encode(apnsToken, forKey: .apnsToken)
        try container.encode(language, forKey: .language)
    }
}

/// Tells the server which device this is and where to push (SSOT §7.2, Ш-40). Called at launch, after sign-in and
/// sign-out (the server links the device to the user only when a session is sent, so a signed-out device stops getting
/// the previous user's pushes), when the language changes and when APNs hands out a new token. The system question
/// about notifications is asked once, after the first trip shows up — never at launch.
///
/// APNs does not deliver anything without the paid Apple Developer account (push capability, `aps-environment`
/// entitlement); until then `apns_token` stays `null` and the server keeps a guest-style device row.
@MainActor
final class DeviceRegistrar {
    static let tokenKey = "jol.apns_token"
    static let askedKey = "jol.push_asked"

    private let api: APIClient
    private let installID: String
    private let language: () -> String
    private let defaults: UserDefaults
    private let push: any PushAuthorizing
    private var chain: Task<Void, Never>?

    /// The last call failed (no network, server error): the next time the app is active it is repeated.
    private(set) var needsRetry = false

    init(
        api: APIClient, installID: String, language: @escaping () -> String,
        defaults: UserDefaults = .standard, push: any PushAuthorizing = SystemPushAuthorizing()
    ) {
        self.api = api
        self.installID = installID
        self.language = language
        self.defaults = defaults
        self.push = push
    }

    /// The APNs token iOS last gave us (hex), `nil` before the first one or after the permission was withdrawn.
    var apnsToken: String? { defaults.string(forKey: Self.tokenKey) }

    /// Registers the device with what is known right now. Calls are serialised, so two quick changes (sign-in, then
    /// sign-out) reach the server in order, each with the state of its own moment.
    func register() async {
        let previous = chain
        let task = Task { [weak self] in
            await previous?.value
            await self?.send()
        }
        chain = task
        await task.value
    }

    func retryIfNeeded() async {
        if needsRetry { await register() }
    }

    private func send() async {
        let body = DeviceRegistration(installID: installID, apnsToken: apnsToken, language: language())
        do {
            try await api.send(Endpoint.post("v1/devices", json: body))
            needsRetry = false
        } catch {
            needsRetry = true
        }
    }

    // MARK: - Token

    /// `didRegisterForRemoteNotificationsWithDeviceToken`: a new or changed token is sent to the server at once.
    func tokenReceived(_ token: Data) {
        let hex = token.map { String(format: "%02x", $0) }.joined()
        guard !hex.isEmpty, hex != apnsToken else { return }
        defaults.set(hex, forKey: Self.tokenKey)
        Task { await register() }
    }

    /// At launch: with the permission given the token is requested again (iOS may have changed it); with the permission
    /// withdrawn the stored token is dropped and the server is told `null`. Asks nothing.
    func refreshTokenAtLaunch() async {
        switch await push.isAuthorized() {
        case true?:
            push.registerForRemoteNotifications()
        case false?:
            if apnsToken != nil {
                defaults.removeObject(forKey: Self.tokenKey)
                await register()
            }
        case nil:
            break
        }
    }

    /// The first trip is on screen: the one moment the question "tell you when the weather changes the plan?" makes
    /// sense. Asked once in the life of the install; an answer, whatever it is, is final.
    func requestPermissionAfterFirstTrip() async {
        guard !defaults.bool(forKey: Self.askedKey) else { return }
        defaults.set(true, forKey: Self.askedKey)
        guard await push.isAuthorized() == nil else {
            await refreshTokenAtLaunch()
            return
        }
        if await push.requestAuthorization() { push.registerForRemoteNotifications() }
    }
}

/// Receives the APNs token and hands it to the registrar of the running app.
final class JolAppDelegate: NSObject, UIApplicationDelegate {
    @MainActor static weak var registrar: DeviceRegistrar?

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken token: Data) {
        Task { @MainActor in Self.registrar?.tokenReceived(token) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        // Expected without the paid Apple account / push entitlement: the device stays registered with `null`.
    }
}
