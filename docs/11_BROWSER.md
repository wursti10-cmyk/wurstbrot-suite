# Browser

## Status

Die Browser-Anwendung liegt unter `apps/web/`. Sie ist statisch, benötigt kein Backend und kann eine
mitgelieferte oder lokal ausgewählte `WT_Database_*.json` verarbeiten.

## Zielarchitektur

- statische Dateien ohne Backend
- lokaler Import einer `WT_Database_*.json`
- kein Upload von Datamine oder Fortschritt
- responsive und per Tastatur bedienbar
- optionaler Offline-Cache, dessen Version an den Release gekoppelt ist

## Fachlicher Vertrag

Bei identischer Datenbank, A, B, Fortschritt und Optionen müssen Browser und Python-Core dieselben
Fahrzeug-IDs, Gründe, RP, GE, SL und Warnungen liefern. `tests/fixtures/solver_contract.json` wird von
beiden Laufzeiten geprüft; zusätzlich läuft die normale Graph-Regression auch im Browser-Solver.

## Sicherheit

JSON ist untrusted input. Die Ausgabe erzeugt DOM-Knoten und setzt Nutzdaten ausschließlich über
`textContent`; Fahrzeugnamen werden nicht als HTML interpretiert.
Service Worker dürfen nur veröffentlichte statische Assets cachen. Keine Tokens, Accounts oder externen
Tracker.

## Deployment

Bevorzugt GitHub Pages aus einem geprüften Build-Artefakt. Basis-Pfade müssen sowohl unter lokalem
HTTP-Server als auch unter dem Repository-Unterpfad funktionieren. Direkte `file://`-Nutzung erfordert
wegen Browserregeln in der Regel manuellen Dateiimport.
