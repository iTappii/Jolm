import SwiftUI

/// Sheet with the place card (SSOT §6.1): opens at about a third of the screen (the map behind stays interactive)
/// and can be dragged up. While directions are open it starts taller so a few variants fit.
struct PlaceCardSheet: View {
    static let cardFraction: CGFloat = 1.0 / 3.0
    static let directionsFraction: CGFloat = 0.5
    static let cardDetent = PresentationDetent.fraction(cardFraction)
    static let directionsDetent = PresentationDetent.fraction(directionsFraction)

    let model: PlacesModel
    let directions: DirectionsModel
    @Binding var detent: PresentationDetent

    var body: some View {
        let base = directions.isActive ? Self.directionsDetent : Self.cardDetent
        PlaceCardView(model: model, directions: directions)
            .presentationDetents([base, .large], selection: $detent)
            .presentationBackgroundInteraction(.enabled(upThrough: base))
            .presentationDragIndicator(.visible)
            // Solid: with the default translucent sheet material the orange map clusters shine through the card.
            .presentationBackground(JolColor.surfaceElevated)
            .presentationCornerRadius(JolRadius.xl)
    }
}
