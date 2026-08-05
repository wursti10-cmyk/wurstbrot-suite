# Coding Standards

## Python

- Python 3.10+ und `from __future__ import annotations`
- Typannotationen für öffentliche Funktionen und Datenstrukturen
- `pathlib.Path` statt manueller Pfadverkettung
- `dataclass` für fachliche Werte, unveränderlich (`frozen=True`) wenn sinnvoll
- klare Domänenfehler statt unstrukturierter Rückgabewerte
- maximale Zeilenlänge laut `pyproject.toml`: 100 Zeichen
- deterministische Sortierung mit stabilen Tie-Breakern

## Fachlogik

- Ganzzahlarithmetik für RP, GE und SL
- keine Rundung von Gesamtsummen, wenn die Spielregel pro Fahrzeug rundet
- keine stillen Annahmen bei Sonderfreischaltungen
- bestehende IDs und Schemafelder rückwärtskompatibel behandeln
- UI-Code delegiert Berechnungen an den Core

## Tests

- jeder Fehlerfix erhält einen Regressionstest
- Tests verwenden feste IDs aus der Beispieldatenbank nur, wenn deren Bedeutung erklärt ist
- neue Optimierungsregeln brauchen kleine synthetische Tests plus breite Regression
- Reihenfolge und Textformat nur testen, wenn sie Teil des Vertrags sind

## Dokumentation und Commits

- Dokumentation auf Deutsch; Code-Bezeichner und stabile Schemafelder auf Englisch
- Commit-Nachrichten kurz und im Imperativ
- keine Behauptung „fertig“, wenn eine Funktion nur in einem offenen PR liegt
- TODOs nennen Grund, Besitzer oder geplanten Meilenstein
