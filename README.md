# 🥪 Wurstbrot Suite

Die **Wurstbrot Suite** ist ein Community-Projekt für War Thunder.

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

### Nächster Meilenstein

**GE Calculator 2.0 Core**

- A → B Berechnung
- Rangfreischaltungen
- Fahrzeugordner
- angeforschte RP
- GE-Rundung pro Fahrzeug
- Explain Mode

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
