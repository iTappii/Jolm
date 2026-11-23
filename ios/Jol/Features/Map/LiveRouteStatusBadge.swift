import SwiftUI

/// Ш-64: the small capsule on the map while the live route is built in the background («Строю маршрут…»), and the
/// short sentence when the build failed. Never blocks anything: no buttons, no alert, the person keeps typing.
struct LiveRouteStatusBadge: View {
    let isBuilding: Bool
    let failed: Bool
    var onDismissFailure: () -> Void = {}

    var body: some View {
        Group {
            if isBuilding {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Building route…").font(.footnote.weight(.semibold))
                }
                .badge()
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("live-route-building")
            } else if failed {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(JolColor.danger)
                    Text("Couldn't build the route. I'll try again with your next message.")
                        .font(.footnote.weight(.semibold))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .badge()
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("live-route-build-failed")
                .task {
                    try? await Task.sleep(for: .seconds(6))
                    if !Task.isCancelled { onDismissFailure() }
                }
            }
        }
        .animation(.snappy(duration: 0.25), value: isBuilding)
        // Over the map above the chat: past xxxLarge it would reach the chat card.
        .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
    }
}

private extension View {
    func badge() -> some View {
        padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(.regularMaterial, in: Capsule())
            .shadow(color: .black.opacity(0.2), radius: 4, y: 1)
            .transition(.move(edge: .top).combined(with: .opacity))
    }
}

/// The badge on the map: top strip between the sidebar and profile buttons.
struct StandaloneBuildBadge: View {
    let chat: ChatModel

    var body: some View {
        LiveRouteStatusBadge(
            isBuilding: chat.isBuildingRoute, failed: chat.routeBuildFailed,
            onDismissFailure: { chat.dismissRouteBuildFailure() }
        )
        // In the strip between the two corner buttons, above the chat card (which would cover it lower down).
        .padding(.top, 8)
        .padding(.horizontal, 64)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }
}
