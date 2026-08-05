# Testing

## Testebenen

| Ebene | Befehl | Zweck |
|---|---|---|
| Unit/Integration | `python run_tests.py` | Datenbank, Wirtschaft und Solver |
| Graph-Regression | `python tests/regression_matrix.py` | normale Vorgänger-Ziel-Paare der Beispieldatenbank |
| Solver-Contract | `python run_tests.py` und `node --test tests/web_solver.test.mjs` | gleiche Fixture in Python und JavaScript |
| Browser-Regression | `node tests/browser_regression.mjs` | gleiche 1.977 normalen Paare im Browser-Solver |
| Graph Unit/Mirror | `python run_tests.py` | Builder, Adapter, Export, Diagnostik und alle Closures |
| Graph-Semantikmatrix | `python tests/graph_semantics_matrix.py` | alle Ziele, Statusverteilung, Sonderfälle und verfeinerte Diagnostik |
| Graph-Resolution-Matrix | `python tests/graph_resolution_matrix.py` | 1.977 bestehende Fälle plus 13 Progress-Szenarien, Shadow-Diagnostik und 49 Sonderfälle |
| Datamine-Health | `python apps/datamine-manager/wurstbrot_converter.py --validate-database data/samples/WT_Database_2.57.1.67.json --output build/health` | strukturierte Regeln und freigegebene Sample-Daten |
| Windows-Sammeltest | `Milestone1_pruefen.bat` | beide Python-Prüfungen unter Windows |

Die Regression für Spielversion `2.57.1.67`
meldet 1.977 bestandene Fälle, 206 Wurzelziele und 49 übersprungene Sonderfälle ohne Fehler.

## Was die Regression prüft

- Ziel ist in `required_vehicle_ids`
- GE-Gesamtsumme entspricht den Fahrzeugzeilen
- jede ausgewiesene Rangschranke ist erfüllt

Sie überspringt ausgeblendete Ziele und Ziele mit `reqUnlock`; diese 49 Fälle sind keine bestätigten
Erfolge und brauchen gezielte Fixtures.

Die Python-Regression berechnet jeden regulären Fall zusätzlich über `GraphDatabaseAdapter` und
vergleicht das vollständige `SolveResult`. `mirror_matches` muss exakt `passed` entsprechen. Der
Legacy-Solver und `solver.py` werden für diesen Vergleich nicht verändert.

Accuracy 3 erweitert dies um die regelweise Mirror Evaluation aller 2.232 Ziele. Das Gate verlangt
`mismatch == 0`; unresolved Fälle werden getrennt gezählt und dürfen nicht in `exact_match` erscheinen.
Die generierte Sonderfallmatrix muss exakt 49 deterministische Zeilen enthalten: 31 reqUnlock und 18
hiddenResearch. Tests decken jede Kantenklasse, alle vier Statuswerte, Folderanomalien,
Unlockklassifikation, Rank-Evidence und deterministische Edge-IDs ab.

Accuracy 4 ergänzt 12 fokussierte Resolver-Tests sowie das separate Vollmatrix-Gate. Die Matrix
vergleicht 1.990 Aufrufe und verlangt `mismatch == 0`. Aktuell entstehen 1.926 exact matches,
0 equivalent matches, 63 ehrlich unresolved Fälle, 1 unsupported Vergleich und 0 mismatches. Die
13 PlayerProgress-Fälle müssen vollständig einer Kategorie zugeordnet sein. Bei einer Abweichung
enthält das Artefakt Ziel, Start, Szenario, Legacy-/Graph-Mengen, Differenzen, Regeln, Evidence und
Explanation Trace.

Die 49er Sonderfallprüfung verwendet nur explizite Evidenz: Hidden wird gezielt aktiviert und externe
Unlocks werden gezielt angenommen. Sie darf Folder-Unklarheiten nicht heuristisch grün machen. Der
Vorher-/Nachher-Vertrag lautet derzeit 0 → 35 aufgelöste Fälle, 14 unresolved, 0 unsupported und
0 mismatch.

## Neue Tests

- kleine synthetische Datenbanken für Randfälle bevorzugen
- reale Beispiel-IDs für End-to-End-Realismus verwenden
- Rundung bei 0, 1, `rpPerGE` und `rpPerGE + 1` abdecken
- Zyklen, unbekannte Vorgänger, falsche Bäume und Sicherheitslimit testen
- bei UI-Arbeit fachliche Logik separat testbar halten

## Release-Gate

Python-Tests, beide Regressionen und Browser-Tests müssen grün sein. Gespeicherte Berichte dürfen nur aktualisiert werden, wenn
die Änderung beabsichtigt und im PR erklärt ist.

Das CI erzeugt zusätzlich beide `WT_Health_*`-Dateien, validiert deren Pflichtstruktur und verlangt
`passed=true` sowie exakt null `error`-Findings für die Sample-Datenbank. `git diff --check` ist ein
eigenes Gate. Neue Validatorregeln brauchen eine fehlerhafte Mini-Datenbank, ein positives
Gegenbeispiel und dürfen die echte Sample-Datenbank nicht durch Testlockerung freigeben.

CI lädt zusätzlich `Graph_Resolution_2.57.1.67.json` hoch. Das Artefakt enthält keine Kosten und muss
`graphCostCalculationPerformed=false`, `costValuesEmitted=false` sowie
`optimizerSelectionPerformed=false` ausweisen. Die getrennte Legacy-Compatibility-Auswahl bleibt
ausdrücklich als `legacyCompatibilityModeEnabled=true` sichtbar; einzelne Resolution Results nennen
zusätzlich, ob die Strategie tatsächlich aufgerufen wurde.

`tests/validator_rule_matrix.py` ist der ausführbare Coverage-Vertrag. Der Test verlangt exakt dieselbe
Rule-ID-Menge wie das Produktions-Registry und führt für jede Regel ein negatives Beispiel, das den
Befund auslöst, sowie ein positives Gegenbeispiel ohne diesen Befund aus. Der Converter entdeckt
`testedRules` aus dieser Matrix; CI verlangt `implementedRules == testedRules` und `coverage == 100`.
Die vollständige Rule-Dokumentation wird ebenfalls aus dem Registry gerendert und bytegenau geprüft.
