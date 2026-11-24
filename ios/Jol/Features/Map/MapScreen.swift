import SwiftUI

/// Full-screen map layer. `HomeScreen` puts the chat, profile button and attribution label on top.
struct MapScreen: View {
    let places: PlacesModel
    var chat: ChatModel?
    var directions: DirectionsModel?
    var tripMap: TripMapModel?
    var events: EventsModel?
    var projection: MapProjection?
    /// The sights `LandmarksOverlay` draws (empty while it is not shown): ordinary pins keep out from under them.
    var landmarks: [Landmark] = []
    var bottomInset: CGFloat = 0
    @Environment(\.colorScheme) private var colorScheme

    private var tripOpen: Bool { tripMap?.isOpen == true }
    /// The live route (Ш-54) wins over the plain chat pins for drawing; the full route map hides it.
    private var liveRoute: LiveRoute? { tripOpen ? nil : chat?.state.liveRoute }

    var body: some View {
        MapView(
            styleURL: AppConfig.mapStyleURL(dark: colorScheme == .dark),
            // Ordinary place pins and their orange clusters hide under a drawn route: next to the live route's
            // numbered stops a cluster «2» read as a stop.
            pins: places.activeRoute == nil && !tripOpen && liveRoute == nil ? places.pins : [],
            pinsVersion: tripOpen ? -3 : liveRoute != nil ? -5 : places.activeRoute == nil ? places.pinsVersion : -2,
            routeStops: places.routeStops,
            routeID: places.activeRoute?.id,
            selectedID: places.selected?.id,
            landmarks: landmarks,
            markedPoint: places.selected?.tappedPoint == nil ? nil : places.selected.map { GeoPoint($0.coordinate) },
            directionLines: directions?.lines ?? [],
            directionOrigin: directions?.origin,
            directionVersion: directions?.lineVersion ?? 0,
            directionFitVersion: directions?.fitVersion ?? 0,
            chatPlaces: tripOpen || liveRoute != nil ? [] : chat?.state.mapPlaces ?? [],
            chatPlacesVersion: tripOpen ? -3 : liveRoute != nil ? -4 : chat?.state.mapVersion ?? 0,
            liveRoute: liveRoute,
            projection: projection,
            tripStops: tripOpen ? tripMap?.stops ?? [] : [],
            tripLines: tripOpen ? tripMap?.lines ?? [] : [],
            tripFitExtras: tripOpen ? tripMap?.fitExtras ?? [] : [],
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
            onTapEmpty: { coordinate in
                events?.clearSelection()
                // Ш-23c: a tap on any point opens its card. While a route is drawn, a tap on the empty map keeps
                // its old meaning (closing the card), so the route is not replaced by accident.
                if directions?.isActive == true {
                    places.clearSelection()
                } else {
                    places.tapPoint(GeoPoint(coordinate))
                }
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
                Color.clear
                    .frame(width: 1, height: 1)
                    .accessibilityElement()
                    .accessibilityLabel(Text(verbatim: "map-drawn-pins"))
                    .accessibilityValue(Text(verbatim: projection?.debugPins ?? ""))
                    .accessibilityIdentifier("map-drawn-pins")
                Color.clear
                    .frame(width: 1, height: 1)
                    .accessibilityElement()
                    .accessibilityLabel(Text(verbatim: "live-route-stops"))
                    .accessibilityValue(Text(verbatim: String(liveRoute?.stops.count ?? 0)))
                    .accessibilityIdentifier("live-route-stops")
            }
        }
        #endif
    }
}
