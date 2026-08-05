# 🥪 Wurstbrot Suite

Die **Wurstbrot Suite** ist ein Community-Projekt für War Thunder.

> Entwickler: Die vollständige technische Referenz beginnt bei
> [`docs/00_PROJECT_CONTEXT.md`](docs/00_PROJECT_CONTEXT.md). Verbindliche Fachverträge liegen in
> [`specs/`](specs/).

Geplante Hauptbestandteile:

- **Datamine Manager** – lädt oder verarbeitet relevante Datamine-Dateien
- **GE Calculator 2.0** – berechnet den Golden-Eagles-Bedarf von Fahrzeug A zu Fahrzeug B
- **Validator** – prüft Forschungsgraph, Kosten, Freischaltungen und Rangregeln
- **Patch Compare** – erkennt Unterschiede zwischen War-Thunder-Versionen

## Projektstatus

Aktuell befindet sich das Projekt in einer frühen Entwicklungsphase.

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

### Aktueller Meilenstein

**GE Calculator 2.0 Core**

- A → B Berechnung
- Rangfreischaltungen
- Fahrzeugordner
- angeforschte RP
- GE-Rundung pro Fahrzeug
- Explain Mode

Diese Punkte sind im Stand `0.3.0-milestone1` implementiert. Browser-Version und CI befinden sich
derzeit nur in einem offenen Draft-Pull-Request und sind noch nicht Bestandteil von `main`.

## Entwicklerdokumentation

- [Projektkontext](docs/00_PROJECT_CONTEXT.md)
- [Architektur](docs/02_ARCHITECTURE.md)
- [Entwicklungsleitfaden](docs/04_DEVELOPMENT_GUIDE.md)
- [Datamine-Referenz](docs/07_DATAMINE_REFERENCE.md)
- [GE Engine](docs/08_GE_ENGINE.md)
- [Tests](docs/13_TESTING.md)
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
│   └── ge-calculator/
├── packages/
│   ├── core/
│   ├── parser/
│   └── validator/
├── data/
│   └── samples/
├── docs/
└── .github/
```

## Datenschutz

Die Verarbeitung findet lokal statt. Es werden keine Accountdaten benötigt und keine Spieldateien hochgeladen.

## Rechtlicher Hinweis

War Thunder und alle zugehörigen Marken gehören Gaijin Entertainment. Dieses Projekt ist ein unabhängiges Fanprojekt und steht in keiner Verbindung zu Gaijin Entertainment.

## GE Calculator 2.0 Alpha testen

Tests starten:

```bash
python run_tests.py
```

Beispielberechnung:

```bash
python apps/ge-calculator/ge_calculator_cli.py   --database data/samples/WT_Database_2.57.1.67.json   --start germ_leopard_2a5   --target germ_leopard_2a7v
```

Angeforschte RP:

```bash
python apps/ge-calculator/ge_calculator_cli.py   --database data/samples/WT_Database_2.57.1.67.json   --start germ_leopard_2a5   --target germ_leopard_2a7v   --progress germ_leopard_2a7v:100000
```


## Milestone 1 starten

Windows-GUI:

```text
apps\ge-calculator\Wurstbrot_GE_Calculator_starten.bat
```

Komplette Prüfung:

```text
Milestone1_pruefen.bat
```
