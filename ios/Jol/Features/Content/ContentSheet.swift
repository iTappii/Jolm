import PhotosUI
import SwiftUI

/// «Add info» from the place card (Ш-44, SSOT §10): one entry point, a simple form per kind of submission.
/// Everything is published at once and checked by a moderator later (§10.2) — the result says so.
struct ContentSheet: View {
    let place: PlaceSummary
    var onSubmitted: () -> Void = {}
    @Environment(AppContainer.self) private var container
    @Environment(\.dismiss) private var dismiss
    @State private var draft = SubmissionDraft()
    @State private var pickerItem: PhotosPickerItem?
    @State private var model: ContentModel?

    var body: some View {
        NavigationStack {
            Group {
                if let model {
                    if case .done(let result) = model.stage {
                        resultView(result)
                    } else {
                        form(model)
                    }
                }
            }
            .navigationTitle(Text("Add info"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(model?.isDone == true ? "Done" : "Cancel") { dismiss() }
                        .accessibilityIdentifier("content-close")
                }
            }
        }
        .presentationDetents([.large])
        .presentationBackground(JolColor.surfaceElevated)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("content-sheet")
        .onAppear { if model == nil { model = ContentModel(api: container.api) } }
    }

    // MARK: - Form

    private func form(_ model: ContentModel) -> some View {
        Form {
            Section {
                Text(verbatim: place.name).font(JolFont.headline)
                Picker("What to add", selection: $draft.kind) {
                    ForEach(SubmissionKind.allCases) { Text(Self.title($0)).tag($0) }
                }
                .accessibilityIdentifier("content-kind")
            }
            switch draft.kind {
            case .review: reviewFields
            case .menu: menuFields
            case .photo: photoFields
            case .transit: transitFields
            case .price: priceFields
            }
            if draft.usesPhoto { photoSection(model) }
            Section {
                if let message = Self.problemText(draft, model: model) {
                    Text(message)
                        .font(JolFont.callout)
                        .foregroundStyle(JolColor.danger)
                        .accessibilityIdentifier("content-error")
                }
                Button { send(model) } label: {
                    HStack {
                        Spacer()
                        if model.isBusy {
                            ProgressView()
                            Text(Self.stageText(model.stage)).font(JolFont.headline)
                        } else {
                            Text("Send").font(JolFont.headline)
                        }
                        Spacer()
                    }
                }
                .disabled(model.isBusy || !draft.isValid)
                .accessibilityIdentifier("content-submit")
            } footer: {
                Text("It appears right away and a moderator checks it later. Spam earns nothing.")
            }
        }
        .scrollDismissesKeyboard(.immediately)
        .onChange(of: draft.kind) { _, _ in
            if case .failed = model.stage { model.clearPhoto() }
        }
        .onChange(of: pickerItem) { _, item in
            guard let item else { return }
            Task { await load(item, into: model) }
        }
    }

    private func send(_ model: ContentModel) {
        Task {
            if await model.submit(draft, placeID: place.id) { onSubmitted() }
        }
    }

    private func load(_ item: PhotosPickerItem, into model: ContentModel) async {
        defer { pickerItem = nil }
        guard let data = try? await item.loadTransferable(type: Data.self) else {
            model.setPhotoFailed()
            return
        }
        await model.setPhoto(data: data)
        draft.hasPhoto = model.photo != nil
    }

    private func photoSection(_ model: ContentModel) -> some View {
        Section {
            if let photo = model.photo, let image = UIImage(data: photo.jpeg) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(height: 140)
                    .frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: JolRadius.lg))
                    .accessibilityIdentifier("content-photo-preview")
                Button("Remove the photo", role: .destructive) {
                    model.clearPhoto()
                    draft.hasPhoto = false
                }
            }
            PhotosPicker(selection: $pickerItem, matching: .images) {
                Label(model.photo == nil ? "Choose a photo" : "Choose another photo", systemImage: "photo")
            }
            .disabled(model.isBusy)
            .accessibilityIdentifier("content-photo-pick")
        } footer: {
            Text("Location and camera data are removed from the photo before it is sent.")
        }
    }

    // MARK: - Result

    private func resultView(_ result: SubmissionResult) -> some View {
        VStack(spacing: JolSpacing.lg) {
            Image(systemName: result.isRejected ? "xmark.octagon.fill" : "checkmark.circle.fill")
                .font(.system(size: 56))
                .foregroundStyle(result.isRejected ? JolColor.danger : JolColor.brand)
            Text(result.isRejected ? "It didn't pass the automatic check" : "Thank you!")
                .font(JolFont.title)
                .multilineTextAlignment(.center)
                .accessibilityIdentifier("content-result-title")
            Text(result.isRejected
                 ? "Nothing was published and no bonus is paid. Check the text and try again."
                 : "It is published and will be checked later. A bonus comes after the check.")
                .font(JolFont.callout)
                .foregroundStyle(JolColor.textSecondary)
                .multilineTextAlignment(.center)
                .accessibilityIdentifier("content-result-note")
            Spacer()
        }
        .padding(JolSpacing.xl)
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("content-result")
    }
}

private extension ContentSheet {
    // MARK: - Kinds

    @ViewBuilder private var reviewFields: some View {
        Section {
            HStack(spacing: JolSpacing.sm) {
                ForEach(1...5, id: \.self) { star in
                    Button { draft.rating = star } label: {
                        Image(systemName: star <= draft.rating ? "star.fill" : "star")
                            .font(.title2)
                            .foregroundStyle(star <= draft.rating ? JolColor.brand : JolColor.textTertiary)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(Text("\(star) of 5"))
                    .accessibilityIdentifier("content-star-\(star)")
                }
            }
            TextField("Your review (optional)", text: $draft.text, axis: .vertical)
                .lineLimit(3...8)
                .accessibilityIdentifier("content-review-text")
        }
    }

    @ViewBuilder private var menuFields: some View {
        Section {
            ForEach($draft.menuItems) { $item in
                HStack {
                    TextField("Dish", text: $item.name)
                    TextField("₸", text: $item.price)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .frame(maxWidth: 90)
                }
            }
            .onDelete { draft.menuItems.remove(atOffsets: $0) }
            if draft.menuItems.count < 30 {
                Button { draft.menuItems.append(MenuItemDraft()) } label: { Label("Add a dish", systemImage: "plus") }
                    .accessibilityIdentifier("content-menu-add")
            }
        } header: {
            Text("Menu: dishes and prices, or a photo of the menu")
        }
    }

    @ViewBuilder private var photoFields: some View {
        Section {
            TextField("Caption (optional)", text: $draft.caption)
                .accessibilityIdentifier("content-caption")
        }
    }

    @ViewBuilder private var transitFields: some View {
        Section {
            TextField("Route number", text: $draft.routeRef).accessibilityIdentifier("content-route")
            TextField("Stop (optional)", text: $draft.stop)
            TextField("Direction (optional)", text: $draft.direction)
            TextField("Interval, minutes (optional)", text: $draft.interval).keyboardType(.numberPad)
            TextField("Fare, ₸ (optional)", text: $draft.transitPrice).keyboardType(.numberPad)
            TextField("Note (optional)", text: $draft.transitNote)
        }
    }

    @ViewBuilder private var priceFields: some View {
        Section {
            TextField("Entry price, ₸", text: $draft.price)
                .keyboardType(.numberPad)
                .accessibilityIdentifier("content-price")
            Picker("Ticket", selection: $draft.audience) {
                ForEach(TicketAudience.allCases) { Text(Self.title($0)).tag($0) }
            }
            TextField("Note (optional)", text: $draft.priceNote)
        }
    }
}

extension ContentSheet {
    // MARK: - Text

    static func title(_ kind: SubmissionKind) -> LocalizedStringKey {
        switch kind {
        case .review: "Review"
        case .menu: "Menu"
        case .photo: "Photo"
        case .transit: "Transport data"
        case .price: "Entry price"
        }
    }

    static func title(_ audience: TicketAudience) -> LocalizedStringKey {
        switch audience {
        case .adult: "Adult"
        case .child: "Child"
        case .student: "Student"
        case .senior: "Senior"
        case .foreigner: "Foreigner"
        case .resident: "Resident"
        }
    }

    static func stageText(_ stage: ContentModel.Stage) -> LocalizedStringKey {
        switch stage {
        case .preparingPhoto: "Preparing the photo…"
        case .uploading: "Uploading the photo…"
        default: "Sending…"
        }
    }

    /// A failure of the last send wins over a form problem.
    static func problemText(_ draft: SubmissionDraft, model: ContentModel) -> LocalizedStringKey? {
        if case .failed(let failure) = model.stage { return failureText(failure) }
        return draft.problems.first.map(formText)
    }

    private static func failureText(_ failure: ContentModel.Failure) -> LocalizedStringKey {
        switch failure {
        case .photoUnreadable: "This photo can't be read. Choose another one."
        case .photoTooLarge: "The photo is too large. Choose another one."
        case .imageRefused: "The server didn't accept the photo. Choose it again."
        case .alreadySubmitted: "You have already left a review here."
        case .tooMany: "Too many submissions today. Try again later."
        case .network: "No connection. Try again."
        case .server: "Couldn't send. Try again later."
        }
    }

    private static func formText(_ problem: SubmissionDraft.Problem) -> LocalizedStringKey {
        switch problem {
        case .rating: "Choose a rating from 1 to 5."
        case .textTooLong, .captionTooLong, .fieldTooLong: "The text is too long."
        case .menuEmpty: "Add a dish or a photo of the menu."
        case .menuName: "A dish needs a name."
        case .menuPrice, .price: "Enter the price as a number."
        case .photoMissing: "Choose a photo."
        case .routeRef: "Enter the route number."
        case .interval: "The interval is from 1 to 240 minutes."
        }
    }
}
