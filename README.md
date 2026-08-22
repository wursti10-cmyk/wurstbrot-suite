# 🥪 Wurstbrot Suite

Die **Wurstbrot Suite** ist ein Community-Projekt für War Thunder.

> Entwickler: Die vollständige technische Referenz beginnt bei
> [`docs/00_PROJECT_CONTEXT.md`](docs/00_PROJECT_CONTEXT.md). Verbindliche Fachverträge liegen in
> [`specs/`](specs/).

Hauptbestandteile:

- **Datamine Manager** – lädt oder verarbeitet relevante Datamine-Dateien
- **GE Calculator 2.0** – berechnet den Golden-Eagles-Bedarf von Fahrzeug A zu Fahrzeug B
- **Validator** – prüft Forschungsgraph, Kosten, Freischaltungen und Rangregeln
- **Patch Compare** – erkennt Unterschiede zwischen War-Thunder-Versionen
- **Browser-App** – nutzt den Rechner ohne Installation und verarbeitet Daten lokal

## Projektstatus

Aktueller Stand: **1.1.0-rc.1**. Der Python-Kern, die Desktop-Oberflächen und eine
installierbare Browser-Version sind nutzbar. GitHub Actions prüft Python 3.10, 3.12
und 3.13, die Browser-Logik und den vollständigen Regressionstest.

Version 1.0.0 bleibt der Stable-Stand. Version 1.1.0-rc.1 ist der Release Candidate mit dem
vollständigen visuellen Forschungsbaum. Legacy bleibt die standardmäßige und empfohlene
Rechenquelle; Graph Experimental bleibt explizit opt-in und nicht für die Default-Nutzung freigegeben.

Der Produktumfang von Version 1.0 bleibt bewusst eng: ein zuverlässiger Forschungsweg von
Fahrzeug A zu Fahrzeug B sowie die zugehörigen RP-, GE- und SL-Kosten. Legacy ist weiterhin die
standardmäßige und empfohlene Rechenquelle. Die Python-CLI kann die Graphpipeline ausdrücklich
experimentell aktivieren; Desktop und Browser bleiben unverändert auf Legacy.

Der 1.1-Release-Candidate ergänzt die Darstellung aller 44 Forschungsbäume, Suche, Navigation,
Zoom/Pan, Folder-/Hidden-/Partial-Anzeige und die bestehende A→B-Berechnung im Baum. Diese Oberfläche
projiziert ausschließlich vorhandene Daten und Solverergebnisse; sie führt keine neue Forschungs-,
Folder- oder Solversemantik ein.

### Fertig

- Parser für `shop.blkx`
- Parser für `wpcost.blkx`
- Parser für `rank.blkx`
- Parser für `warpoints.blkx`
- Parser für `unlocks.blkx`
- Lokalisierung über `units.csv`
- kompakter JSON-Export
- Validierung von Vorgängern, Zyklen, Rängen und Kosten
- Patchvergleich zwischen zwei Datenbanken

### Kernfunktionen

- A → B Berechnung und Rangfreischaltungen
- Fahrzeugordner, angeforschte RP und GE-Rundung je Fahrzeug
- vorhandene GE, Convertible RP und SL-Rabatte
- Explain Mode in CLI und Desktop-GUI
- Browser-App mit JSON-Import, responsivem Layout und Offline-Cache
- Datamine-Konvertierung, Validierung und Patchvergleich

## Entwicklerdokumentation

- [Projektkontext](docs/00_PROJECT_CONTEXT.md)
- [Architektur](docs/02_ARCHITECTURE.md)
- [Entwicklungsleitfaden](docs/04_DEVELOPMENT_GUIDE.md)
- [Datamine-Referenz](docs/07_DATAMINE_REFERENCE.md)
- [GE Engine](docs/08_GE_ENGINE.md)
- [Tests](docs/13_TESTING.md)
- [Release Hardening](docs/31_RELEASE_HARDENING.md)
- [Bekannte Fehler](docs/16_KNOWN_BUGS.md)
- [Spezifikationen](specs/GE_CALCULATION_SPEC.md)

## Schnellstart

### Windows

1. Python 3.10 oder neuer installieren.
2. Dieses Repository herunterladen oder klonen.
3. `apps/datamine-manager/Wurstbrot_Converter_starten.bat` ausführen.
4. Entpackte Datamine auswählen.
5. JSON-Datenbank erzeugen.

### Kommandozeile

```bash
python apps/datamine-manager/wurstbrot_converter.py   --source "D:\WarThunder-Datamine"   --output "D:\Wurstbrot-Output"
```

### Browser-Version

Im Repository einen lokalen Webserver starten:

```bash
python -m http.server 8000
```

Danach `http://localhost:8000/apps/web/` öffnen. Alternativ kann `apps/web/index.html`
direkt geöffnet und eine `WT_Database_*.json` ausgewählt werden.

## Benötigte Datamine-Dateien

Der Converter sucht rekursiv nach:

- `shop.blkx`
- `wpcost.blkx`
- `rank.blkx`
- `warpoints.blkx`
- `unlocks.blkx`
- `units.csv`
- optional `version.txt`

## Ordnerstruktur

```text
wurstbrot-suite/
├── apps/
│   ├── datamine-manager/
│   ├── ge-calculator/
│   └── web/
├── packages/
│   ├── core/
│   ├── parser/
│   └── validator/
├── data/
│   └── samples/
├── docs/
├── specs/
└── .github/
```

## Datenschutz

Die Verarbeitung findet lokal statt. Es werden keine Accountdaten benötigt und keine Spieldateien hochgeladen.

## Rechtlicher Hinweis

War Thunder und alle zugehörigen Marken gehören Gaijin Entertainment. Dieses Projekt ist ein unabhängiges Fanprojekt und steht in keiner Verbindung zu Gaijin Entertainment.

## Stable 1.0 testen

Tests starten:

```bash
python run_tests.py
python tests/regression_matrix.py
node --test tests/web_solver.test.mjs
node tests/browser_release_hardening.mjs
```

Das vollständige Accuracy-10-Gate aggregiert 61 unabhängige reale A→B-Abnahmen, 32 deterministische
Boundary-Fälle und die 14 bewusst partiellen Hidden-Folder-Fälle. Der genaue Artefaktaufruf steht in
der [Release-Hardening-Dokumentation](docs/31_RELEASE_HARDENING.md).

Beispielberechnung:

```bash
python apps/ge-calculator/ge_calculator_cli.py \
  --database data/samples/WT_Database_2.57.1.67.json \
  --start germ_leopard_2a5 \
  --target germ_leopard_2a7v
```

Rechenmodi der CLI:

```bash
# Standard: nur Legacy, kein Graph-Aufruf
python apps/ge-calculator/ge_calculator_cli.py \
  --database data/samples/WT_Database_2.57.1.67.json \
  --start germ_sdkfz_222 --target germ_sdkfz_6_2_flak36

# Legacy-Benutzerergebnis plus Graphvergleich
python apps/ge-calculator/ge_calculator_cli.py \
  --database data/samples/WT_Database_2.57.1.67.json \
  --start germ_sdkfz_222 --target germ_sdkfz_6_2_flak36 \
  --engine shadow

# Pro Aufruf ausdrücklich aktivierter, nicht empfohlener Experimentalmodus
python apps/ge-calculator/ge_calculator_cli.py \
  --database data/samples/WT_Database_2.57.1.67.json \
  --start germ_sdkfz_222 --target germ_sdkfz_6_2_flak36 \
  --engine graph-experimental
```

`graph-experimental` verwendet Graph nur bei `complete` und `exact_match`. Bei `partial`,
`unavailable`, internem Fehler, nicht exaktem Vergleich oder Adapterverletzung bleibt das
Legacy-Ergebnis sichtbar; Quelle und Fallback-Grund werden ausgegeben. Als `invalid_input`
klassifizierte Aufrufe werden dagegen ohne Legacy-Fallback abgelehnt, damit ungültige Eingaben nicht
wie erfolgreiche Berechnungen erscheinen. Die Auswahl wird nicht gespeichert und nie anhand eines
Confidence-Werts automatisch aktiviert.

Angeforschte RP:

```bash
python apps/ge-calculator/ge_calculator_cli.py \
  --database data/samples/WT_Database_2.57.1.67.json \
  --start germ_leopard_2a5 \
  --target germ_leopard_2a7v \
  --progress germ_leopard_2a7v:100000
```

Der v1-Eingabevertrag akzeptiert SL-Rabatte nur mit `--sl-discount 0`, `30` oder `50`. Negative oder
über den Gesamt-RP liegende Fortschritte sowie widersprüchliche Forschungs-/Kaufstatus werden
abgelehnt und nicht still geklemmt.

Datamine-Health-Report für eine bestehende Datenbank:

```bash
python apps/datamine-manager/wurstbrot_converter.py \
  --validate-database data/samples/WT_Database_2.57.1.67.json \
  --output build/health
```

Der Befehl erzeugt `WT_Health_<gameVersion>.json` und `.txt`. Ein `error`-Finding liefert Exitcode 1;
der bisherige `WT_Validation_*`-Export bleibt bei regulären Konvertierungen erhalten.

Health Report V2 enthält automatisch ermittelte Rule-Coverage, Befundgruppen und Fahrzeug-, Graph-
und Ordnerstatistiken. Der Health Score ist bewusst noch nicht implementiert; der Report weist dies
maschinenlesbar als `healthScore: null` aus.


## Desktop-RC starten

Windows-GUI:

```text
apps\ge-calculator\Wurstbrot_GE_Calculator_starten.bat
```

Komplette Prüfung:

```text
Milestone1_pruefen.bat
```
