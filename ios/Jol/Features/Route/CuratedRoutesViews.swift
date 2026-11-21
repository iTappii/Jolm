import SwiftUI

/// Ready-made routes (SSOT §3.1, Ш-19): list sheet opened from the side panel.
struct CuratedRoutesSheet: View {
    let model: PlacesModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            content
                .navigationTitle(Text("Ready-made routes"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { dismiss() }.accessibilityIdentifier("routes-done")
                    }
                }
        }
        .task { await model.loadRoutes() }
        .accessibilityIdentifier("routes-sheet")
    }

    @ViewBuilder
    private var content: some View {
        switch model.routes {
        case .idle, .loading:
            ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
        case .failed:
            VStack(spacing: JolSpacing.md) {
                Text("Couldn't load routes").foregroundStyle(JolColor.textSecondary)
                Button("Retry") { Task { await model.loadRoutes() } }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .accessibilityIdentifier("routes-failed")
        case .loaded(let routes) where routes.isEmpty:
            Text("No ready-made routes yet")
                .foregroundStyle(JolColor.textSecondary)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityIdentifier("routes-empty")
        case .loaded(let routes):
            List(routes) { route in
                Button { model.openRoute(id: route.id) } label: { row(route) }
                    .accessibilityIdentifier("route-row")
            }
            .overlay { if model.routeLoading { ProgressView() } }
            .alert("Couldn't open the route", isPresented: Binding(
                get: { model.routeFailed }, set: { _ in }
            )) {
                Button("OK", role: .cancel) {}
            }
        }
    }

    private func row(_ route: CuratedRouteSummary) -> some View {
        VStack(alignment: .leading, spacing: JolSpacing.xs) {
            Text(route.title).font(JolFont.headline).foregroundStyle(JolColor.textPrimary)
            if let description = route.description, !description.isEmpty {
                Text(description).font(JolFont.callout).foregroundStyle(JolColor.textSecondary).lineLimit(2)
            }
            Text("\(route.placesCount) places").font(JolFont.caption).foregroundStyle(JolColor.textTertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }
}

/// Bar shown while a curated route is on the map: title, close, stops in order (tap → place card).
struct RouteBar: View {
    let model: PlacesModel

    var body: some View {
        if let route = model.activeRoute {
            VStack(alignment: .leading, spacing: JolSpacing.sm) {
                HStack {
                    Text(route.title)
                        .font(JolFont.headline)
                        .foregroundStyle(JolColor.textPrimary)
                        .lineLimit(1)
                        .accessibilityIdentifier("route-title")
                    Spacer()
                    Button { model.closeRoute() } label: {
                        Image(systemName: "xmark")
                            .font(.footnote.weight(.semibold))
                            .frame(width: 32, height: 32)
                            .background(JolColor.surface, in: Circle())
                            .foregroundStyle(JolColor.textPrimary)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(Text("Close route"))
                    .accessibilityIdentifier("route-close")
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: JolSpacing.sm) {
                        ForEach(Array(model.routeStops.enumerated()), id: \.element.id) { index, stop in
                            Button { model.select(stop) } label: { chip(index + 1, stop) }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("route-stop-\(index + 1)")
                        }
                    }
                }
            }
            .padding(JolSpacing.md)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: JolRadius.lg))
            .padding(.horizontal, JolSpacing.sm)
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("route-bar")
        }
    }

    private func chip(_ number: Int, _ stop: PlaceSummary) -> some View {
        HStack(spacing: JolSpacing.xs) {
            Text("\(number)")
                .font(JolFont.caption.weight(.bold))
                .foregroundStyle(JolColor.onBrand)
                .frame(width: 22, height: 22)
                .background(JolColor.brand, in: Circle())
            Text(stop.name).font(JolFont.callout).foregroundStyle(JolColor.textPrimary).lineLimit(1)
        }
        .padding(.horizontal, JolSpacing.sm)
        .padding(.vertical, JolSpacing.xs)
        .background(JolColor.surface, in: Capsule())
    }
}
