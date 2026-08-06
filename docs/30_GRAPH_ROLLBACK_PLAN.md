# Graph Shadow Rollback Plan

## Status

Dieser Plan ist `design_only`. Es existiert kein produktiver Graphschalter. Die produktive
Ergebnisquelle ist weiterhin ausschließlich der Legacy-`ResearchSolver`.

Maschinenlesbarer Vertrag:
[`accuracy/rollback/experimental_switch_plan.json`](../accuracy/rollback/experimental_switch_plan.json).

## Spätere experimentelle Umschaltung

Eine spätere, separat geprüfte Umsetzung braucht:

- ein standardmäßig deaktiviertes Feature Flag;
- Legacy als jederzeit verfügbare Fallback- und Benutzer-Ergebnisquelle;
- parallelen Shadow-Vergleich mit unveränderten Kategorien;
- lokale, deterministische Graph-Shadow- und Confidence-Berichte;
- strukturierte Behandlung von `mismatch`, `internal_error`, Contract-Differenzen,
  `unresolved_expected` und `unsupported`;
- einen vollständig deaktivierbaren Graphpfad ohne Datenmigration.

Ein Graphfehler darf den Legacy-Benutzerwert nicht überschreiben. Nicht exakte Kategorien dürfen
nicht als erfolgreicher Match umetikettiert werden.

## Daten und Datenschutz

Es ist keine Migration gespeicherter Fortschrittsdaten notwendig. Reports bleiben lokal oder werden
als CI-Artefakte erzeugt. Benutzertelemetrie ist ausgeschlossen, bis eine spätere ausdrückliche
Produkt- und Datenschutzentscheidung sie erlaubt.

## Nicht implementiert

Accuracy 7 fügt weder Feature Flag noch GUI-/Browser-Schalter, Telemetrie, produktive Fallback-Logik
oder Solver-Umschaltung hinzu. Der Plan beschreibt nur überprüfbare Voraussetzungen für einen
späteren, eigenständigen Migrationssprint.
