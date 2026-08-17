# Changelog

## [1.0.0-rc.2] - 2026-08-17

### Changed

- Nationen und Fahrzeugarten in Browser und Desktop mit lesbaren deutschen Bezeichnungen angezeigt
- Küsten- und Hochseeschiffe als getrennte Forschungsbäume beschriftet
- Auswahl „Baumstart“ in „Forschungsbaum“ umbenannt
- RC.2-Service-Worker-Cache für die aktualisierte Browser-Anzeige gesetzt

### Known limitations

- Legacy bleibt Default; Graph Experimental bleibt ausdrücklich opt-in
- 14 Hidden-Folder-Fälle bleiben bewusst `partial` mit sichtbarem Legacy-Fallback
- Browser und Desktop besitzen keine Graph-Runtime

## [1.0.0-rc.1] - 2026-08-10

### Changed

- Produkt-, Paket-, CLI-, Desktop- und Browser-Version auf `1.0.0-rc.1` vereinheitlicht
- installierbaren CLI-Einstiegspunkt und prüfbare RC-Build-Artefakte ergänzt
- Release-Build-Acceptance, Clean-Install und maschinenlesbares RC.1-Readiness-Gate ergänzt

### Known limitations

- Legacy bleibt Default; Graph Experimental bleibt explizit opt-in
- 14 Hidden-Folder-Fälle bleiben bewusst `partial` mit sichtbarem Legacy-Fallback
- Browser und Desktop besitzen keine Graph-Runtime

## [0.9.0-beta] - 2026-08-05

### Added

- responsive Browser-Version des GE Calculators
- lokaler Datenbankimport und Offline-Cache als Progressive Web App
- GitHub-Actions-CI für Python 3.10, 3.12 und 3.13
- JavaScript-Tests für Datenbankprüfung, Forschungswege und GE-Rundung
- gemeinsame Python-/Browser-Contract-Fixture und Browser-Regression
- automatischer Paket-Build und GitHub-Pages-Workflow
- Entwicklungsabhängigkeiten, `.gitignore` und Metadatenprüfungen

### Changed

- Projektstatus, Dokumentation und Versionsangaben auf `0.9.0-beta` vereinheitlicht
- README um Browser- und Beta-Schnellstart ergänzt
- Komponenten- und UI-Versionen auf `0.9.0-beta` vereinheitlicht

### Fixed

- ungültige erste Zeile in zwei Windows-Startskripten entfernt
- Browser-Solver an Rangfreischaltungen und Optimierungsregeln des Python-Cores angeglichen
- ungefilterte Fahrzeugnamen aus der HTML-Ausgabe entfernt

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
