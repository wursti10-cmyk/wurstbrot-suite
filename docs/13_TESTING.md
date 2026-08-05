# Testing

## Testebenen

| Ebene | Befehl | Zweck |
|---|---|---|
| Unit/Integration | `python run_tests.py` | Datenbank, Wirtschaft und Solver |
| Graph-Regression | `python tests/regression_matrix.py` | normale Vorgänger-Ziel-Paare der Beispieldatenbank |
| Windows-Sammeltest | `Milestone1_pruefen.bat` | beide Python-Prüfungen unter Windows |

Der gespeicherte Milestone-Bericht nennt 18 Unit Tests. Die Regression für Spielversion `2.57.1.67`
meldet 1.977 bestandene Fälle, 206 Wurzelziele und 49 übersprungene Sonderfälle ohne Fehler.

## Was die Regression prüft

- Ziel ist in `required_vehicle_ids`
- GE-Gesamtsumme entspricht den Fahrzeugzeilen
- jede ausgewiesene Rangschranke ist erfüllt

Sie überspringt ausgeblendete Ziele und Ziele mit `reqUnlock`; diese 49 Fälle sind keine bestätigten
Erfolge und brauchen gezielte Fixtures.

## Neue Tests

- kleine synthetische Datenbanken für Randfälle bevorzugen
- reale Beispiel-IDs für End-to-End-Realismus verwenden
- Rundung bei 0, 1, `rpPerGE` und `rpPerGE + 1` abdecken
- Zyklen, unbekannte Vorgänger, falsche Bäume und Sicherheitslimit testen
- bei UI-Arbeit fachliche Logik separat testbar halten

## Release-Gate

Unit Tests und Regression müssen grün sein. Gespeicherte Berichte dürfen nur aktualisiert werden, wenn
die Änderung beabsichtigt und im PR erklärt ist.
