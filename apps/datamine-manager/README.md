# Datamine Manager

Der Datamine Manager erzeugt eine kompakte Wurstbrot-Datenbank aus einer entpackten War-Thunder-Datamine.

## Start

```bash
python wurstbrot_converter.py --gui
```

oder unter Windows:

```text
Wurstbrot_Converter_starten.bat
```

Eine bereits normalisierte Datenbank kann ohne Roh-Datamine geprüft werden:

```bash
python wurstbrot_converter.py \
  --validate-database ../../data/samples/WT_Database_2.57.1.67.json \
  --output ../../build/health
```

Dabei entstehen der strukturierte JSON-Report und eine kompakte Textzusammenfassung. `error` blockiert
die Verwendung; `WT_Validation_*` bleibt bei vollständigen Konvertierungen als Legacy-Export erhalten.
