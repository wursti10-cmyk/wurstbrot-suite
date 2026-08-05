# Development Guide

## Voraussetzungen

- Python 3.10 oder neuer
- Git
- Tk-Unterstützung nur für Desktop-GUIs
- Node.js 22 für Browser-Tests
- keine externen Python-Laufzeitpakete

## Einrichtung

```bash
git clone https://github.com/wursti10-cmyk/wurstbrot-suite.git
cd wurstbrot-suite
python run_tests.py
python tests/regression_matrix.py
node --test tests/web_solver.test.mjs
node tests/browser_regression.mjs
```

Ein virtuelles Environment ist empfohlen, aber derzeit nicht zwingend. Die Apps fügen
`packages/core` selbst zum Importpfad hinzu.

## Typische Aufgaben

```bash
# Calculator CLI
python apps/ge-calculator/ge_calculator_cli.py \
  --database data/samples/WT_Database_2.57.1.67.json \
  --start germ_leopard_2a5 --target germ_leopard_2a7v

# Converter CLI
python apps/datamine-manager/wurstbrot_converter.py \
  --source /pfad/zur/datamine --output /pfad/zur/ausgabe
```

## Änderungsablauf

1. Branch vom aktuellen `main` erstellen.
2. Betroffene Spezifikation und Code gemeinsam ändern.
3. Kleine Unit Tests ergänzen.
4. `python run_tests.py` ausführen.
5. Bei Graph- oder Solveränderungen zusätzlich `python tests/regression_matrix.py` ausführen.
6. Keine generierten `__pycache__`, lokalen Daten oder proprietären Assets committen.
7. Pull Request mit Motivation, Verhalten und Prüfungen beschreiben.

## Debugging

Der Converter unterstützt `--debug`. Solverfehler sind `SolveError`, Datenbankfehler
`DatabaseError`. Für reproduzierbare Fehler immer Spielversion, IDs, Fortschritt und Optionen notieren.
