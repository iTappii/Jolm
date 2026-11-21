import SwiftUI

/// "Download route" on the full route map (SSOT §7.4): arrow → progress → check mark; a tap on the check mark offers to
/// remove the copy from the device. Only for a signed-in user (the plan belongs to the account).
struct TripDownloadButton: View {
    let model: TripMapModel
    @Environment(AppContainer.self) private var container
    @State private var confirmRemove = false

    var body: some View {
        if let id = model.tripID, container.auth.isSignedIn {
            let state = container.offline.state(for: id)
            Button {
                switch state {
                case .none: Task { await container.offline.download(tripID: id) }
                case .saved: confirmRemove = true
                case .downloading: break
                }
            } label: {
                Group {
                    switch state {
                    case .none: Image(systemName: "arrow.down.circle")
                    case .downloading: ProgressView()
                    case .saved: Image(systemName: "checkmark.circle.fill").foregroundStyle(JolColor.brand)
                    }
                }
                .font(.title3)
                .frame(width: 44, height: 44)
                .background(.thinMaterial, in: Circle())
                .foregroundStyle(JolColor.textPrimary)
            }
            .buttonStyle(.plain)
            .disabled(state == .downloading || (state == .none && model.isSavedCopy))
            .accessibilityLabel(label(state))
            .accessibilityIdentifier("trip-download")
            .confirmationDialog("Remove the downloaded route?", isPresented: $confirmRemove,
                                titleVisibility: .visible) {
                Button("Remove from device", role: .destructive) { container.offline.remove(tripID: id) }
                    .accessibilityIdentifier("trip-download-remove")
                Button("Cancel", role: .cancel) {}
            }
        }
    }

    private func label(_ state: OfflineTripsModel.State) -> Text {
        switch state {
        case .none: Text("Download route")
        case .downloading: Text("Downloading the route…")
        case .saved: Text("Route downloaded")
        }
    }
}
