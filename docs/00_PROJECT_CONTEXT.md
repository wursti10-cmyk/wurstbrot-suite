# Project Context

## Zweck dieses Dokuments

Diese Developer Bible ist die technische Referenz für Menschen und KI-Agenten. Sie beschreibt den
Stand von `main` zum Commit `1d47b92` (`0.3.0-milestone1`). Aussagen über zukünftige Funktionen sind
ausdrücklich als Ziel markiert. Der offene Draft-PR #1 enthält einen Vorschlag für `0.9.0-beta`, gehört
aber noch nicht zum veröffentlichten Hauptzweig.

## Produkt

Die Wurstbrot Suite ist ein unabhängiges Community-Projekt für War Thunder. Sie verarbeitet eine
entpackte Datamine lokal, normalisiert Forschungs- und Wirtschaftsdaten und berechnet den Aufwand von
einem Startfahrzeug A zu einem Zielfahrzeug B. Es werden keine Spielkonten, Zugangsdaten oder
proprietären Spielassets benötigt oder hochgeladen.

## Aktueller Stand

- Python 3.10 oder neuer, ausschließlich Standardbibliothek zur Laufzeit
- Datamine Converter mit CLI und Tkinter-GUI
- kompakte JSON-Datenbank, Schema-Version 1
- GE Calculator Core, CLI und Tkinter-GUI
- 2.232 reguläre Fahrzeuge in der Beispieldatenbank `2.57.1.67`
- 395 Fahrzeuggruppen, zehn Nationen und fünf Fahrzeugarten
- Unit Tests und Regression über normale Vorgänger-Ziel-Paare
- kein Browser-Frontend und keine CI auf `main`

## Nicht-Ziele

- Umgehung von Gaijin-Schutzmaßnahmen oder automatisierter Accountzugriff
- Veränderung von Spieldateien
- Garantie absoluter Preise für zukünftige Spielversionen
- Veröffentlichung urheberrechtlich geschützter Spielassets

## Verbindlichkeit

Bei Widersprüchen gilt: ausführbarer Code und Tests vor Dokumentation; Spezifikationen vor Roadmap;
`main` vor offenen Pull Requests. Ein Widerspruch ist als Fehler zu behandeln und in derselben Änderung
zu korrigieren.

## Inhaltsverzeichnis

| Bereich | Dokumente |
|---|---|
| Richtung | [Vision](01_VISION.md) · [Roadmap](03_ROADMAP.md) · [Ideen](17_IDEAS.md) |
| System | [Architektur](02_ARCHITECTURE.md) · [Datamine](07_DATAMINE_REFERENCE.md) · [Graph](09_RESEARCH_GRAPH.md) · [Optimierer](10_OPTIMIZER.md) |
| Entwicklung | [Guide](04_DEVELOPMENT_GUIDE.md) · [Standards](05_CODING_STANDARDS.md) · [Tests](13_TESTING.md) · [Release](14_RELEASE_PROCESS.md) |
| Oberflächen | [UI-Regeln](06_UI_GUIDELINES.md) · [Browser](11_BROWSER.md) · [Desktop](12_DESKTOP.md) |
| Betrieb | [AI Context](15_AI_CONTEXT.md) · [Bekannte Fehler](16_KNOWN_BUGS.md) · [FAQ](18_FAQ.md) |
| Spezifikationen | [GE](../specs/GE_CALCULATION_SPEC.md) · [Forschungsgraph](../specs/RESEARCH_GRAPH_SPEC.md) · [Schema](../specs/DATAMINE_SCHEMA.md) · [UI](../specs/UI_SPEC.md) |
