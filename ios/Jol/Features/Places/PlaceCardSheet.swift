import SwiftUI

/// Sheet with the place card: the small detent is the mini card (the map behind stays interactive),
/// swiping up expands it to the full card.
struct PlaceCardSheet: View {
    static let miniHeight: CGFloat = 270
    static let miniDetent = PresentationDetent.height(miniHeight)

    let model: PlacesModel
    @Binding var detent: PresentationDetent

    var body: some View {
        PlaceCardView(model: model, expanded: detent == .large)
            .presentationDetents([Self.miniDetent, .large], selection: $detent)
            .presentationBackgroundInteraction(.enabled(upThrough: Self.miniDetent))
            .presentationDragIndicator(.visible)
            .presentationCornerRadius(JolRadius.xl)
    }
}
