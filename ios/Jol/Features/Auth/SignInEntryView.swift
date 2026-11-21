import SwiftUI

/// Sign-in (guest → account, SSOT §3.3): Apple (when the build supports it), e-mail code, SMS code.
/// Two steps inside one view: where to send the code, then the code itself.
struct SignInEntryView: View {
    let onSignedIn: () -> Void
    /// Why the user is asked to sign in (the registration gate passes its own text).
    var reason: LocalizedStringKey = "Sign in to build a personal trip plan and keep your chats."

    @Environment(AppContainer.self) private var container
    @State private var model: SignInModel?

    var body: some View {
        Group {
            if let model {
                content(model)
            } else {
                ProgressView()
            }
        }
        .navigationTitle(Text("Sign in"))
        .navigationBarTitleDisplayMode(.inline)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("sign-in-entry")
        .task {
            if model == nil {
                model = SignInModel(service: AuthService(api: container.api, tokens: container.tokens),
                                    auth: container.auth)
            }
        }
        .onDisappear { model?.cancel() }
    }

    private func content(_ model: SignInModel) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: JolSpacing.lg) {
                switch model.step {
                case .destination:
                    DestinationStep(model: model, reason: reason, onSignedIn: onSignedIn)
                case .code:
                    CodeStep(model: model, onSignedIn: onSignedIn)
                }
            }
            .padding(JolSpacing.lg)
        }
        .scrollDismissesKeyboard(.interactively)
    }
}

// MARK: - Step 1: where to send the code

private struct DestinationStep: View {
    @Bindable var model: SignInModel
    let reason: LocalizedStringKey
    let onSignedIn: () -> Void
    @FocusState private var focused: Bool

    var body: some View {
        Text(reason)
            .font(JolFont.callout)
            .foregroundStyle(JolColor.textSecondary)
            .accessibilityIdentifier("sign-in-reason")
        appleSection
        Picker("Method", selection: $model.channel) {
            Text("Email").tag(OTPChannel.email)
            Text("Phone").tag(OTPChannel.phone)
        }
        .pickerStyle(.segmented)
        .accessibilityIdentifier("sign-in-channel")
        .onChange(of: model.channel) { _, _ in model.input = "" }

        TextField(model.channel == .email ? "Email address" : "Phone number", text: $model.input)
            .keyboardType(model.channel == .email ? .emailAddress : .phonePad)
            .textContentType(model.channel == .email ? .emailAddress : .telephoneNumber)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .focused($focused)
            .submitLabel(.continue)
            .onSubmit { submit() }
            .padding(JolSpacing.md)
            .frame(minHeight: 44)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
            .accessibilityIdentifier("sign-in-destination")
        if model.channel == .phone {
            Text("Kazakhstan numbers work without a country code; for other countries start with +.")
                .font(JolFont.caption)
                .foregroundStyle(JolColor.textSecondary)
        }
        ProblemText(problem: model.problem, secondsLeft: model.secondsUntilResend)
        Button { submit() } label: {
            HStack {
                if model.isWorking { ProgressView() }
                Text("Send code")
            }
            .font(JolFont.headline)
            .foregroundStyle(JolColor.onBrand)
            .frame(maxWidth: .infinity, minHeight: 48)
            .background(JolColor.brand.opacity(model.canSubmitDestination ? 1 : 0.4),
                        in: RoundedRectangle(cornerRadius: JolRadius.md))
        }
        .buttonStyle(.plain)
        .disabled(!model.canSubmitDestination)
        .accessibilityIdentifier("sign-in-send")
    }

    private func submit() {
        guard model.canSubmitDestination else { return }
        Task { await model.sendCode() }
    }

    @ViewBuilder
    private var appleSection: some View {
        if AppConfig.appleSignInEnabled {
            AppleSignInView(onSignedIn: onSignedIn)
        } else {
            VStack(alignment: .leading, spacing: JolSpacing.xs) {
                Label("Sign in with Apple", systemImage: "apple.logo")
                    .font(JolFont.headline)
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
                    .foregroundStyle(JolColor.textSecondary)
                Text("Sign in with Apple isn't available in this build yet. Use email or phone.")
                    .font(JolFont.caption)
                    .foregroundStyle(JolColor.textSecondary)
            }
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.isButton)
            .accessibilityHint(Text("Not available yet"))
            .accessibilityIdentifier("sign-in-apple-disabled")
        }
    }
}

// MARK: - Step 2: the code

private struct CodeStep: View {
    @Bindable var model: SignInModel
    let onSignedIn: () -> Void
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: JolSpacing.xs) {
            Text("Enter the code")
                .font(JolFont.title)
                .foregroundStyle(JolColor.textPrimary)
                .accessibilityAddTraits(.isHeader)
            Text("We sent a 6-digit code to \(model.destination).")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .accessibilityIdentifier("sign-in-code-sent")
        }
        // `.oneTimeCode` lets iOS offer the code from the SMS / Mail message above the keyboard.
        TextField("6-digit code", text: $model.code)
            .keyboardType(.numberPad)
            .textContentType(.oneTimeCode)
            .focused($focused)
            .font(.system(.title, design: .monospaced, weight: .semibold))
            .minimumScaleFactor(0.6)
            .multilineTextAlignment(.center)
            .padding(JolSpacing.md)
            .frame(minHeight: 44)
            .background(JolColor.surface, in: RoundedRectangle(cornerRadius: JolRadius.md))
            // One element: «6-digit code», the value is what has been typed, the hint says where the code went.
            .accessibilityLabel(Text("6-digit code"))
            .accessibilityHint(Text("We sent a 6-digit code to \(model.destination)."))
            .accessibilityIdentifier("sign-in-code")
            .onChange(of: model.code) { _, value in
                let digits = String(value.filter { $0.isASCII && $0.isNumber }.prefix(6))
                if digits != value { model.code = digits }
                if digits.count == 6 { verify() }
            }
            .onAppear { focused = true }
        ProblemText(problem: model.problem, secondsLeft: model.secondsUntilResend)
        if model.isWorking { ProgressView().frame(maxWidth: .infinity).accessibilityLabel(Text("Loading")) }
        AdaptiveStack {
            Button("Change") { model.changeDestination() }
                .minTapTarget()
                .accessibilityIdentifier("sign-in-change")
            Spacer()
            Button { Task { await model.resend() } } label: {
                if model.secondsUntilResend > 0 {
                    Text("Resend in \(model.secondsUntilResend) s")
                } else {
                    Text("Resend code")
                }
            }
            .disabled(!model.canResend)
            .minTapTarget()
            .accessibilityIdentifier("sign-in-resend")
        }
        .font(JolFont.callout)
    }

    private func verify() {
        Task {
            if await model.verify() { onSignedIn() }
        }
    }
}

// MARK: - Errors

private struct ProblemText: View {
    let problem: SignInModel.Problem?
    let secondsLeft: Int

    var body: some View {
        if let problem {
            text(problem)
                .font(JolFont.callout)
                .foregroundStyle(JolColor.danger)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityIdentifier("sign-in-error")
        }
    }

    private var rateLimitedText: Text {
        if secondsLeft > 0 { return Text("Too many attempts. Try again in \(secondsLeft) s.") }
        return Text("Too many attempts. Try again later.")
    }

    private func text(_ problem: SignInModel.Problem) -> Text {
        switch problem {
        case .invalidDestination: Text("That email or phone number doesn't look right.")
        case .rateLimited:
            rateLimitedText
        case .deliveryUnavailable: Text("Couldn't send the code right now. Try again in a minute.")
        case .wrongCode: Text("Wrong code. Check it and try again.")
        case .codeExpired: Text("Code expired. Request a new one.")
        case .network: Text("No connection. Check the internet and try again.")
        case .generic: Text("Something went wrong. Try again.")
        }
    }
}
