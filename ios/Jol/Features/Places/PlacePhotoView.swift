import SwiftUI

/// Photo or a placeholder (the server has no photo URLs until `MEDIA_BASE_URL`, Ш-44).
struct PlacePhotoView: View {
    let photo: PlaceDetail.Photo?
    let category: String?
    let height: CGFloat

    var body: some View {
        let style = PlaceCategoryStyle.style(for: category)
        ZStack {
            if let urlString = photo?.url, let url = URL(string: urlString) {
                AsyncImage(url: url) { image in
                    image.resizable().scaledToFill()
                } placeholder: {
                    placeholder(style)
                }
            } else {
                placeholder(style)
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: height)
        .clipShape(RoundedRectangle(cornerRadius: JolRadius.md))
        .accessibilityHidden(true)
        .accessibilityIdentifier("place-photo")
    }

    private func placeholder(_ style: PlaceCategoryStyle) -> some View {
        ZStack {
            style.color.opacity(0.18)
            Image(systemName: style.symbol)
                .font(.system(size: height * 0.35, weight: .regular))
                .foregroundStyle(style.color)
        }
    }
}
