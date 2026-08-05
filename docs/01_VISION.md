# Vision

## Leitbild

Spieler sollen vor einer Ausgabe nachvollziehen können, welche Fahrzeuge, RP, GE und SL zwischen ihrem
aktuellen Stand und einem Ziel liegen. Jede Zahl soll erklärbar, reproduzierbar und an eine konkrete
Datamine-Version gebunden sein.

## Produktprinzipien

1. **Lokal zuerst:** Daten und Fortschritt bleiben auf dem Gerät.
2. **Erklärbarkeit:** Ergebnisse bestehen nicht nur aus Summen, sondern aus Fahrzeugzeilen und Gründen.
3. **Versionierbarkeit:** Jede Datenbank nennt Schema, Spielversion, Erzeugungszeit und Quelldatei-Hashes.
4. **Konservative Genauigkeit:** Unbekannte Sonderfreischaltungen werden sichtbar gewarnt, nicht erraten.
5. **Ein Kern:** Desktop, CLI und künftiger Browser sollen dieselben fachlichen Regeln abbilden.
6. **Reproduzierbarkeit:** Berechnungen müssen durch Tests und feste Beispieldaten überprüfbar sein.

## Zielgruppen

- Spieler, die einen Forschungsweg oder GE-Bedarf planen
- Dataminer, die Patchänderungen prüfen
- Entwickler, die Parser, Solver, Oberflächen oder Tests erweitern

## Erfolgskriterien für 1.0

- dokumentiertes und stabilisiertes Datenbankschema
- definierte GE- und Graph-Spezifikation mit Golden Tests
- Desktop- und Browser-Ergebnisse für dieselben Eingaben identisch
- automatisierte Prüfungen auf unterstützten Python-Versionen
- reproduzierbare Windows- und Web-Releases
- bekannte Sonderfälle sichtbar klassifiziert
