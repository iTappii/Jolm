import Foundation
import Observation

/// A photo ready to go: cleaned JPEG bytes (`PhotoSanitizer`).
struct PreparedPhoto: Equatable, Identifiable {
    let id = UUID()
    let jpeg: Data
}

/// One submission from the place card (Ш-44): clean the photo, ask for an upload slot, PUT the file, send the
/// submission. Stages are shown to the person; a retry after a failure does not upload the same photo twice.
@MainActor
@Observable
final class ContentModel {
    enum Stage: Equatable {
        case idle
        case preparingPhoto
        case uploading
        case sending
        case done(SubmissionResult)
        case failed(Failure)
    }

    enum Failure: Equatable {
        case photoUnreadable
        case photoTooLarge
        /// The server refused the file (`invalid_image`, `upload_not_found`): choose it again.
        case imageRefused
        case alreadySubmitted
        case tooMany
        case network
        case server(String)
    }

    private(set) var stage = Stage.idle
    private(set) var photo: PreparedPhoto?

    @ObservationIgnored private let service: ContentService
    /// The slot already filled for `photo` (a retry reuses it: a slot is a daily quota).
    @ObservationIgnored private var filledSlot: (photoID: UUID, uploadID: UUID)?

    init(api: APIClient) {
        self.service = ContentService(api: api)
    }

    var isBusy: Bool {
        switch stage {
        case .preparingPhoto, .uploading, .sending: true
        default: false
        }
    }

    var isDone: Bool {
        if case .done = stage { return true }
        return false
    }

    func reset() {
        stage = .idle
        photo = nil
        filledSlot = nil
    }

    func clearPhoto() {
        photo = nil
        filledSlot = nil
        if case .failed = stage { stage = .idle }
    }

    /// The bytes the picker gave: EXIF and GPS are stripped here, off the main thread.
    func setPhoto(data: Data) async {
        stage = .preparingPhoto
        do {
            let jpeg = try await Task.detached { try PhotoSanitizer.clean(data) }.value
            photo = PreparedPhoto(jpeg: jpeg)
            filledSlot = nil
            stage = .idle
        } catch PhotoSanitizer.Failure.tooLarge {
            stage = .failed(.photoTooLarge)
        } catch {
            stage = .failed(.photoUnreadable)
        }
    }

    func setPhotoFailed() {
        stage = .failed(.photoUnreadable)
    }

    /// Sends the form. `true` when the server took it (also when its filter refused it: see `SubmissionResult`).
    @discardableResult
    func submit(_ draft: SubmissionDraft, placeID: UUID) async -> Bool {
        guard !isBusy, draft.isValid else { return false }
        do {
            var uploadID: UUID?
            if draft.usesPhoto, let photo {
                if let filled = filledSlot, filled.photoID == photo.id {
                    uploadID = filled.uploadID
                } else {
                    stage = .uploading
                    let slot = try await service.createUpload(sizeBytes: photo.jpeg.count)
                    try await service.put(photo.jpeg, to: slot)
                    filledSlot = (photo.id, slot.uploadID)
                    uploadID = slot.uploadID
                }
            }
            stage = .sending
            let result = try await service.submit(SubmissionRequest(
                type: draft.kind, placeID: placeID, payload: draft.payload(uploadID: uploadID)
            ))
            stage = .done(result)
            return true
        } catch {
            stage = .failed(Self.failure(for: error))
            if case .failed(.imageRefused) = stage { filledSlot = nil }
            return false
        }
    }

    nonisolated static func failure(for error: Error) -> Failure {
        switch error as? APIError {
        case .rateLimited?: .tooMany
        case .network?: .network
        case .server(_, let code, _)?:
            switch code {
            case "invalid_image", "upload_not_found", "upload_used": .imageRefused
            case "already_submitted": .alreadySubmitted
            default: .server(code)
            }
        default: .server("error")
        }
    }
}
