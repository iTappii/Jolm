# Jol iOS

SwiftUI, iOS 17+. Map: MapLibre Native iOS (SPM `maplibre-gl-native-distribution`, pinned exactly to 6.31.0).

## Layout
- `Jol/App` entry point, `Jol/Core` config/infra, `Jol/Features/Map` map, `Jol/Resources` assets, String Catalog, bundled style.
- `JolTests`, `JolUITests`.
- `project.yml` — XcodeGen spec (reproducible source). `Jol.xcodeproj` is committed and equivalent;
  with XcodeGen installed, `cd ios && xcodegen generate` regenerates it.

## Build
```
xcodebuild -project ios/Jol.xcodeproj -scheme Jol \
  -destination 'platform=iOS Simulator,name=iPhone 16' -derivedDataPath ios/build build
```
Requires full Xcode (not only Command Line Tools).

## Map style URL
For local simulator builds, run `make tiles-serve` at the repository root
(run `make tiles` once if the archive is missing). The simulator loads the Jol
style at `http://localhost:8080/native/jol-light.json` and streams the Almaty
PMTiles archive from the same server.

`Jol/Info.plist` key `JOL_MAP_STYLE_URL` is filled from the build setting of the same name, set in
`Config.xcconfig` (used by Debug and Release). Empty value -> bundled
`Jol/Resources/placeholder-style.json` (MapLibre demotiles, temporary).

To switch to the Jol style, set in `Config.xcconfig` (`//` starts a comment in xcconfig, so split the slashes):
```
JOL_MAP_STYLE_URL = https:/$()/<host>/jol-light.json
```
or override per build: `xcodebuild ... JOL_MAP_STYLE_URL='https:/$()/host/jol-light.json'`.
Style file is `maps/style/jol-light.json`. To bundle it instead, copy it into `Jol/Resources/` and
change `AppConfig.bundledStyleName` (add the file to the target resources).

## Location
`NSLocationWhenInUseUsageDescription` is in `Jol/Info.plist` (en) and `Jol/Resources/InfoPlist.xcstrings` (en, ru).
Attribution: MapLibre's own attribution button plus a visible "© OpenStreetMap contributors" label.
