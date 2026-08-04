# Changelog

## [0.3.0-milestone1] - 2026-08-04

### Added

- benutzbare Desktop-GUI
- indirekte A→B-Starts innerhalb desselben Forschungsbaums
- vollständiger Explain Mode in der GUI
- Regressionstest über alle normalen Vorgänger→Ziel-Paare
- Milestone-Prüfskript für Windows

### Fixed

- Startfahrzeuge in einer anderen Linie wurden zuvor abgelehnt
- Zielvorgänger werden nun gegen die durch A bereits belegte Kette dedupliziert
- Israelische Rangfreischaltungen berücksichtigen externe Tree-Unlocks, sobald A bereits im Baum liegt


## [0.2.0-alpha] - 2026-08-04

### Added

- GE Calculator 2.0 Core
- Vehicle database loader
- A → B research solver
- Rank unlock solver with uniform-cost search
- Per-vehicle GE rounding
- Partial RP and owned vehicle progress
- Convertible RP and owned GE handling
- SL discounts
- Explain Mode
- Command-line calculator
- Automated unit tests
- Startfahrzeug überspringt bereits überwundene Rangfreischaltungen

## [0.1.0] - 2026-08-04

### Added

- Initial repository structure
- Datamine converter
- JSON database export
- Validation report
- Patch comparison
