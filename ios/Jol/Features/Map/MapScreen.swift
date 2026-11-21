import SwiftUI

/// Full-screen map layer. `HomeScreen` puts the chat, profile button and attribution label on top.
struct MapScreen: View {
    let places: PlacesModel
    var chat: ChatModel?
    var directions: DirectionsModel?
    var tripMap: TripMapModel?
    var events: EventsModel?
    var bottomInset: CGFloat = 0
    @Environment(\.colorScheme) private var colorScheme

    private var tripOpen: Bool { tripMap?.isOpen == true }

    var body: some View {
        MapView(
            styleURL: AppConfig.mapStyleURL(dark: colorScheme == .dark),
            pins: places.activeRoute == nil && !tripOpen ? places.pins : [],
            pinsVersion: tripOpen ? -3 : places.activeRoute == nil ? places.pinsVersion : -2,
            routeStops: places.routeStops,
            routeID: places.activeRoute?.id,
            selectedID: places.selected?.id,
            directionLines: directions?.lines ?? [],
            directionOrigin: directions?.origin,
            directionVersion: directions?.lineVersion ?? 0,
            directionFitVersion: directions?.fitVersion ?? 0,
            chatPlaces: tripOpen ? [] : chat?.state.mapPlaces ?? [],
            chatPlacesVersion: tripOpen ? -3 : chat?.state.mapVersion ?? 0,
            tripStops: tripOpen ? tripMap?.stops ?? [] : [],
            tripLines: tripOpen ? tripMap?.lines ?? [] : [],
            tripColor: tripMap?.dayColor ?? JolColor.brandUIColor,
            tripVersion: tripOpen ? (tripMap?.drawVersion ?? 0) + 1 : 0,
            tripFitVersion: tripOpen ? (tripMap?.fitVersion ?? 0) + 1 : 0,
            events: tripOpen ? tripMap?.events ?? [] : events?.items ?? [],
            eventsVersion: tripOpen ? (tripMap?.drawVersion ?? 0) + 1_000_000 : events?.version ?? 0,
            bottomInset: bottomInset,
            onRegionChange: {
                places.regionChanged($0)
                if !tripOpen { events?.regionChanged($0) }
            },
            onSelect: { id in
                if let stop = tripMap?.stop(placeID: id), tripOpen {
                    places.select(stop.summary)
                } else if let pin = chat?.state.mapPlaces.first(where: { $0.id == id }) {
                    places.select(pin.summary)
                } else {
                    places.select(id)
                }
            },
            onTapEmpty: {
                places.clearSelection()
                events?.clearSelection()
            },
            onSelectLeg: { tripMap?.selectLeg($0) },
            onSelectEvent: { id in
                let event = tripOpen ? tripMap?.events.first { $0.id == id } : events?.items.first { $0.id == id }
                if let event {
                    places.clearSelection()
                    events?.select(event)
                }
            }
        )
        .ignoresSafeArea()
        #if DEBUG
        .overlay(alignment: .topTrailing) {
            if UITestSupport.isStubbed {
                Color.clear
                    .frame(width: 1, height: 1)
                    .accessibilityElement()
                    .accessibilityLabel(Text(verbatim: "chat-map-places"))
                    .accessibilityValue(Text(verbatim: String(chat?.state.mapPlaces.count ?? 0)))
                    .accessibilityIdentifier("chat-map-places")
            }
        }
        #endif
    }
}
