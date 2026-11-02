# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- The showcase demo is now an animated, procedurally rendered dusk flyover that
  moves and climbs with the telemetry, instead of a static gradient.
- The website hero and the social preview card draw the showcase flight's ground
  track and altitude profile in place of a generic grid background.

## [0.2.0] – 2026-11-02

### Fixed
- The route on the OpenStreetMap background was misplaced whenever the flight's
  bounding box had a different aspect ratio from the map panel; the offline route
  was distorted the same way. The route now uses the same uniform scale and
  centring as the map tiles.

### Changed
- The whole application is now in English: UI, HUD labels, compass directions,
  messages, logs, docs and code comments.
- Numbers in the UI and HUD use a decimal point.

### Added
- English README with screenshots, demo animation and a project landing page.
- `scripts/generate_showcase.py` and `scripts/generate_brand_assets.py` to rebuild
  the demo media, logo and social preview card.
- `scripts/capture_gui_screenshot.py` options for custom inputs.
- Continuous integration on macOS (unit, integration and offscreen GUI tests).
- Release workflow that builds the macOS `.app` when a `v*` tag is pushed.
- Contributing guide, security policy, issue and pull request templates.

## [0.1.0] – 2026-07-31

### Added
- First working release: DJI SRT parser, telemetry calculations, offline route map,
  HUD preview, cancellable FFmpeg export and a PySide6 desktop UI.

[Unreleased]: https://github.com/horakdani/Drone_Telemetry_Studio/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/horakdani/Drone_Telemetry_Studio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/horakdani/Drone_Telemetry_Studio/releases/tag/v0.1.0
