import Foundation
import Observation

/// Light client-side checks. The server is the authority (it normalizes e-mail and E.164 phone numbers, KZ default).
enum ContactValidator {
    static func isPlausibleEmail(_ raw: String) -> Bool {
        let value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        let parts = value.split(separator: "@", omittingEmptySubsequences: false)
        guard parts.count == 2, !parts[0].isEmpty, !value.contains(" ") else { return false }
        let domain = parts[1]
        return domain.contains(".") && !domain.hasPrefix(".") && !domain.hasSuffix(".")
    }

    /// Removes spaces, dashes and brackets; keeps a leading `+`. `nil` if what is left is not 10-15 digits.
    static func cleanedPhone(_ raw: String) -> String? {
        var result = ""
        for character in raw.trimmingCharacters(in: .whitespacesAndNewlines) {
            if character.isASCII, character.isNumber {
                result.append(character)
            } else if character == "+", result.isEmpty {
                result.append(character)
            } else if " -()\u{00A0}".contains(character) {
                continue
            } else {
                return nil
            }
        }
        let digits = result.filter(\.isNumber).count
        return (10...15).contains(digits) ? result : nil
    }
}

/// State of the sign-in flow: destination → code (Ш-25 e-mail, Ш-27 SMS endpoints, SSOT §3.3).
@MainActor
@Observable
final class SignInModel {
    enum Step: Equatable {
        case destination
        case code
    }

    enum Problem: Equatable {
        case invalidDestination
        /// `retryAfter` seconds when the server said so.
        case rateLimited(retryAfter: Int?)
        case deliveryUnavailable
        case wrongCode
        case network
        case generic
    }

    /// Resend countdown when the server gives no `Retry-After`.
    static let defaultCooldown = 30
    static let rateLimitedCooldown = 60

    var channel = OTPChannel.email
    var input = ""
    var code = "" {
        didSet {
            if !code.isEmpty, code != oldValue, problem == .wrongCode { problem = nil }
        }
    }

    private(set) var step = Step.destination
    private(set) var problem: Problem?
    private(set) var isWorking = false
    private(set) var secondsUntilResend = 0
    /// What was actually sent (trimmed / cleaned), shown on the code screen.
    private(set) var destination = ""

    @ObservationIgnored private let service: AuthService
    @ObservationIgnored private let auth: AuthState
    @ObservationIgnored private let tick: Duration
    @ObservationIgnored private var countdown: Task<Void, Never>?

    init(service: AuthService, auth: AuthState, tick: Duration = .seconds(1)) {
        self.service = service
        self.auth = auth
        self.tick = tick
    }

    var canSubmitDestination: Bool {
        !input.trimmingCharacters(in: .whitespaces).isEmpty && !isWorking && secondsUntilResend == 0
    }
    var canResend: Bool { secondsUntilResend == 0 && !isWorking }

    // MARK: - Actions

    func sendCode() async {
        guard let cleaned = cleanedDestination() else {
            problem = .invalidDestination
            return
        }
        if await requestCode(to: cleaned) {
            code = ""
            step = .code
        }
    }

    func resend() async {
        guard canResend else { return }
        code = ""
        _ = await requestCode(to: destination)
    }

    /// Returns `true` when the session was created.
    @discardableResult
    func verify() async -> Bool {
        guard code.count == 6, !isWorking else { return false }
        isWorking = true
        problem = nil
        defer { isWorking = false }
        do {
            try await service.verifyCode(channel: channel, destination: destination, code: code)
            auth.refresh()
            countdown?.cancel()
            return true
        } catch {
            problem = Self.problem(for: error, wrongCodeStatuses: [401, 422])
            if problem == .wrongCode { code = "" }
            return false
        }
    }

    func changeDestination() {
        countdown?.cancel()
        secondsUntilResend = 0
        code = ""
        problem = nil
        step = .destination
    }

    func cancel() {
        countdown?.cancel()
    }

    // MARK: - Internals

    private func cleanedDestination() -> String? {
        switch channel {
        case .email:
            let value = input.trimmingCharacters(in: .whitespacesAndNewlines)
            return ContactValidator.isPlausibleEmail(value) ? value : nil
        case .phone:
            return ContactValidator.cleanedPhone(input)
        }
    }

    private func requestCode(to target: String) async -> Bool {
        isWorking = true
        problem = nil
        defer { isWorking = false }
        do {
            try await service.requestCode(channel: channel, destination: target)
            destination = target
            startCountdown(Self.defaultCooldown)
            return true
        } catch {
            let found = Self.problem(for: error, wrongCodeStatuses: [])
            problem = found
            if case .rateLimited(let retry) = found {
                // The code that was already sent may still work: stay on the code screen when we are there.
                destination = step == .code ? destination : target
                startCountdown(retry ?? Self.rateLimitedCooldown)
            }
            return false
        }
    }

    private func startCountdown(_ seconds: Int) {
        countdown?.cancel()
        secondsUntilResend = seconds
        countdown = Task { [weak self, tick] in
            while !Task.isCancelled {
                try? await Task.sleep(for: tick)
                guard !Task.isCancelled, let self else { return }
                if self.secondsUntilResend > 0 { self.secondsUntilResend -= 1 }
                if self.secondsUntilResend == 0 { return }
            }
        }
    }

    static func problem(for error: Error, wrongCodeStatuses: Set<Int>) -> Problem {
        switch error as? APIError {
        case .rateLimited(let retry, _):
            return .rateLimited(retryAfter: retry.map { Int($0.rounded(.up)) })
        case .server(let status, let code, _):
            if code == "otp_invalid" || wrongCodeStatuses.contains(status) { return .wrongCode }
            if code == "otp_invalid_destination" || status == 422 { return .invalidDestination }
            if status == 503 { return .deliveryUnavailable }
            return .generic
        case .network:
            return .network
        default:
            return .generic
        }
    }
}
