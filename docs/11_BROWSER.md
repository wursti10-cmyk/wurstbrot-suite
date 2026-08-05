# Browser

## Status

Auf `main` existiert noch keine Browser-Anwendung. Draft-PR #1 schlägt eine Browser-Beta vor. Dieses
Dokument definiert den Zielvertrag und darf nicht als Nachweis einer bereits veröffentlichten Funktion
gelesen werden.

## Zielarchitektur

- statische Dateien ohne Backend
- lokaler Import einer `WT_Database_*.json`
- kein Upload von Datamine oder Fortschritt
- responsive und per Tastatur bedienbar
- optionaler Offline-Cache, dessen Version an den Release gekoppelt ist

## Fachlicher Vertrag

Bei identischer Datenbank, A, B, Fortschritt und Optionen müssen Browser und Python-Core dieselben
Fahrzeug-IDs, Gründe, RP, GE, SL und Warnungen liefern. Bis gemeinsame Core-Ausführung möglich ist,
sind Contract Fixtures in beiden Laufzeiten Pflicht.

## Sicherheit

JSON ist untrusted input. HTML-Ausgabe darf Fahrzeugnamen nicht ungefiltert per `innerHTML` einsetzen.
Service Worker dürfen nur veröffentlichte statische Assets cachen. Keine Tokens, Accounts oder externen
Tracker.

## Deployment

Bevorzugt GitHub Pages aus einem geprüften Build-Artefakt. Basis-Pfade müssen sowohl unter lokalem
HTTP-Server als auch unter dem Repository-Unterpfad funktionieren. Direkte `file://`-Nutzung erfordert
wegen Browserregeln in der Regel manuellen Dateiimport.
