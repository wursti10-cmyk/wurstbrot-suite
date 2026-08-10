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
| Graph-Cost-Matrix | `python tests/graph_cost_matrix.py` | 1.977 bestehende Fälle plus 18 Cost-Szenarien, VehicleCostLine-Vergleich und 49 Kostensonderfälle |
| Full Pipeline Shadow | `python tests/graph_shadow_matrix.py --output build/health` | 2.090 klar getrennte Zählebenen, Dual-Vergleich, Optionen, Invalid Input, Fingerprints und Readiness |
| Graph Experimental | `python tests/graph_experimental_matrix.py --output build/health` | Execution-Mode, Result Adapter, Fallback, neun reale A→B-Abnahmen und alle 49 Sonderfälle |
| Golden References | `python tests/accuracy_golden_matrix.py` | 60 eingefrorene Erwartungen, 44 Bäume, sechs Herkunftskategorien und direkte Formelprüfung |
| Accuracy-9-Kernreferenzen | `python tests/accuracy_core_reference_matrix.py` | acht manuell geprüfte Kernfälle über sechs Nationen und fünf Fahrzeugarten |
| Metamorphic Accuracy | `python tests/accuracy_metamorphic_matrix.py` | 16 deterministische Monotonie-, Summen-, Status- und Fingerprint-Eigenschaften |
| Cross-Python | `python tests/accuracy_cross_python.py` | identische Golden- und Kernreferenz-Fingerprints unter Python 3.10/3.12/3.13 |
| Browser Shadow Fixture | `node tests/browser_shadow_harness.mjs` | kanonische Inputs/Ergebnisse ohne zweite Graphimplementierung; Runtime-Parität bleibt offen |
| Browser Release Hardening | `node tests/browser_release_hardening.mjs` | 44 reale Direktfälle mit produktiver Legacy-Browserengine; keine Graphaktivierung |
| Accuracy 10 Release Hardening | `python tests/release_hardening_matrix.py ... --output build/health` | 61 reale A→B-Abnahmen, drei Modi, 32 Boundaries, 14 Partial-Fälle und RC-Readiness |
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

Accuracy 5 ergänzt 14 fokussierte Cost-Tests und ein separates Cost-Shadow-Gate. Die breite Matrix
vergleicht 1.995 Aufrufe: 1.932 exact, 0 equivalent, 63 unresolved expected, 0 unsupported und
0 mismatch. Cost-Status sind 1.932 complete, 63 partial und 0 unavailable. Die 18 fokussierten
Szenarien ergeben 16 exact und 2 unresolved expected; alle sind reproduzierbar benannt.

Die Kostenprüfung vergleicht Required-Set, Rest-RP, GE und SL pro Fahrzeug, Gesamtsummen, vorhandene
GE und Convertible-RP-Shortfall. Jeder definitive Mismatch ist ein Fehler. Ein bewusst synthetischer
Unit Test erzeugt eine bekannte Legacy-/Graph-Divergenz, um die vollständige Mismatch-Diagnostik zu
prüfen; breite und veröffentlichte Matrizen müssen dagegen `mismatch == 0` erfüllen.

Die 49er Kostensonderfallmatrix muss 35 vollständige und 14 partielle Ergebnisse enthalten. Partielle
Zeilen dürfen keine vollständigen Summen oder angewandte vorhandene GE ausweisen.

Accuracy 6 ergänzt Pipeline-, Dual-Runner- und Shadow-Report-Tests. Die Vollmatrix zählt genau 2.090
benannte Aufrufe: 1.977 reguläre Regressionen, 18 Cost-, 13 Progress-, 15 Options-, 49 Sonderfall-
und 18 Invalid-Input-Fälle. Jede Zeile besitzt eine Zählebene und einen stabilen Fingerprint.

Aktueller Vertrag: 1.988 exact, 0 equivalent, 80 unresolved expected, 2 unsupported,
20 input contract differences, 0 mismatches und 0 internal errors. Nach der Accuracy-9-
Vertragsentscheidung sind die Pipeline-Status 1.988 complete, 80 partial, 2 blocked, 0 unavailable,
20 invalid input und 0 internal error. Der Forschungsstatus-/RP-Konflikt ist jetzt blockierender
Invalid Input. Mismatch und Internal Error sind harte Gate-Fehler. Options- und
Input-Validation-Coverage müssen automatisch 100 % ergeben; `ready_for_default_use` bleibt false.

Accuracy 7 ergänzt 60 Golden Cases: 44 Baumreferenzen, neun reale A→B-Referenzen und sieben gezielte
Contracts. Herkunft: 37 Datamine Direct, 7 Formula Derived, 1 Legacy Confirmed mit unabhängiger
Stütze, 10 Manually Reviewed, 3 Synthetic Contract und 2 Unresolved Source Limitation. Alle
Erwartungen sind statisch; der Test besitzt keinen Schreib- oder Updatepfad.

Die 16 metamorphischen Tests verwenden keine Zufallswerte. Die Cross-Python-CI-Matrix muss unter
3.10, 3.12 und 3.13 denselben `accuracy-golden-results-v1`-Fingerprint liefern. Der
JavaScript-Harness prüft dieselben Fixture-Werte, kennzeichnet den Browserstatus aber ausdrücklich
als `fixture_validation_only`, nicht als Graph-Runtime-Parität.

Accuracy 8 führt dieselben 2.090 Requests durch den ausdrücklich aktivierten
`graph_experimental`-Modus. Zählebene bleibt ein Request: 1.988 Benutzerergebnisse stammen aus Graph,
80 aus diagnostiziertem Legacy-Fallback und 22 sind `unavailable`: 20 Input-Contract-Differenzen
werden ausdrücklich ohne Legacy-Fallback abgelehnt, zwei Fälle sind blockiert. Vergleichskategorien
bleiben 1.988 exact, 80 unresolved expected,
2 unsupported, 20 input contract differences, 0 mismatches und 0 internal errors.

Die neun unabhängig festgeschriebenen realen A→B-Abnahmen müssen Graph vollständig und ohne Fallback
verwenden. In der 49er-Sonderfallmatrix müssen 35 vollständige Graph-Ergebnisse und 14 sichtbare
`partial`-Graphstatus mit Legacy-Fallback entstehen. Separat getestete Fallback-Verträge decken
deaktiviertes Feature Flag, `internal_error`, `unavailable`, `blocked`, `unsupported`, `partial`,
`mismatch`, abgelehntes `equivalent_match`, nicht adaptierbare Ergebnisse und Adapter-Contract-
Verletzungen ab. `invalid_input` besitzt einen eigenen Negativtest und darf kein vollständiges
Benutzerergebnis oder Legacy-Fallback erzeugen. Der Standardmodus-Test beweist, dass
ohne `--engine` kein Graph-Aufruf erfolgt.

Accuracy 9 ergänzt acht statische Kernreferenzen. Sieben sind vollständig, ein Hidden-Folder-Fall
ist bewusst partial. Die Suite prüft Datamine-/Formelwerte, Unveränderlichkeit und den festen
`accuracy-core-reference-results-v1`-Fingerprint; Legacy ist nicht die erwartete Wahrheit. Der
Browser-Harness validiert damit 68 Fixtures (60 + 8), bleibt aber `fixture_validation_only`.

Die maschinenlesbare Kernabschlussakte prüft außerdem 15 PlayerProgress-Kategorien gegen die
bestehenden 13 Resolution- und 18 Cost-Szenarien. Der erfüllte External-Unlock-Fall besitzt einen
exakten `fulfilled_unlocks`-Token. Alle 14 Hidden-Folder-Ziele werden einzeln gegen Datamine,
Legacy-Pfad und Graphstatus geprüft und bleiben `partial`; kein Test darf sie heuristisch auflösen.
Die drei früher deferred Verträge testen nun für Legacy, Graph und Browser: nur 0/30/50 Prozent
Rabatt, strikte RP-Bereiche sowie Ablehnung inkonsistenter Research-/Purchase-Status.

Accuracy 10 ergänzt 44 manuell eingefrorene direkte A→B-Fälle: genau einen pro Forschungsbaum.
Zusammen mit neun streng geprüften Golden-E2E- und acht Accuracy-9-Kernreferenzen umfasst die reale
Abnahme 61 Fälle. Die 44 direkten Fälle laufen in `legacy`, `shadow` und `graph_experimental`; alle
132 Modusausführungen müssen die unabhängigen Datamine-/Formelwerte treffen. Ein Reservefall nimmt
das Startfahrzeug ausdrücklich auf und beweist echte Null-RP-/Null-SL-Kostenzeilen. Legacy ist dabei
nie alleinige Sollwertquelle.

Die deterministische Boundary-Matrix enthält 20 ungültige und 12 gültige Grenzfälle. Ungültige
Graph-Experimental-Eingaben dürfen kein Ergebnis und keinen Fallback liefern. Der leere optionale
Start bleibt eine sichtbare Repräsentationsdifferenz: Legacy interpretiert ihn als nicht gesetzt,
Graph lehnt ihn ab. Das ist kein Match und wird nicht still normalisiert. Alle 14 Hidden-Folder-
Fälle müssen weiterhin partial bleiben. Der Performance-Smoke ist nur ein grobes 30-Sekunden-Gate;
die Messzeit ist kein fachlicher Fingerprintbestandteil.

## Neue Tests

- kleine synthetische Datenbanken für Randfälle bevorzugen
- reale Beispiel-IDs für End-to-End-Realismus verwenden
- Rundung bei 0, 1, `rpPerGE` und `rpPerGE + 1` abdecken
- Graph-Cost-Fortschritt unter 0 und über Gesamt-RP als ungültig testen, nie wegklemmen
- die SL-Rabatte 0, 30 und 50 positiv sowie andere Werte negativ testen
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

CI lädt außerdem `Graph_Cost_2.57.1.67.json` hoch. Das Artefakt muss die breite Cost-Matrix, die
18er-Szenariomatrix und die 49er-Sonderfallmatrix enthalten. Es bestätigt Shadow Mode,
`productiveLegacySolverModified=false`, `guiModified=false`, `browserModified=false` und
`optimizerSelectionPerformed=false`.

CI lädt zusätzlich `Graph_Shadow_2.57.1.67.json` und `.txt` hoch. Der Bericht enthält einen kompakten
Index jedes Pipeline-Aufrufs, vollständige Diagnostik aller nicht exakten Vergleiche, Komponenten-
Versionen, Statusverteilungen, Options-/Input-Coverage, Sonderfallstatus, Fingerprints und den
maschinenlesbaren Readiness-Block. Zeitstempel und Dateipfade sind kein Fingerprint-Bestandteil.

CI lädt zusätzlich `Accuracy_Core_References_2.57.1.67.json`,
`Browser_Shadow_2.57.1.67.json` und `Accuracy_Confidence_2.57.1.67.json/.txt` hoch. Der
Confidence-Bericht muss Golden, Accuracy-9-Kernreferenzen und Metamorphic vollständig grün,
Pipeline-Mismatch/Internal Error bei null und `ready_for_default_use=false` ausweisen. Ein
numerischer Confidence-Score ist verboten.

CI lädt außerdem `Graph_Experimental_2.57.1.67.json` und `.txt` hoch. Das Artefakt enthält die
Execution-Mode- und Feature-Flag-Verträge, einen Index aller 2.090 Requests, Ergebnisquellen,
Fallbackgründe, neun reale Abnahmen, die 49 Sonderfälle und den stabilen
`graph-experimental-report-v1`-Fingerprint. Es muss Default und Empfehlung als `legacy`, 0 Mismatches,
0 Internal Errors, 9/9 Abnahmen sowie 35 Graph-/14 Legacy-Fallback-Sonderfälle ausweisen.

CI lädt zusätzlich `Browser_Release_Hardening_2.57.1.67.json` sowie
`Accuracy_Release_Hardening_2.57.1.67.json/.txt` hoch. Das Release-Gate verlangt 61/61 reale
A→B-Abnahmen, 32/32 Boundary-Fälle, 14/14 bewusst partielle Hidden-Folder-Fälle, 0 Mismatches,
0 Internal Errors und keine offene Contract Decision. Zusätzlich müssen Python-Regression, Graph
Mirror und Browser-Regression jeweils 1.977 Fälle sowie der Validator 42/42 Regeln bei 100 Prozent
Coverage nachweisen. `ready_for_rc_review` darf dann true sein; `ready_for_default_use` bleibt immer
false.

`tests/validator_rule_matrix.py` ist der ausführbare Coverage-Vertrag. Der Test verlangt exakt dieselbe
Rule-ID-Menge wie das Produktions-Registry und führt für jede Regel ein negatives Beispiel, das den
Befund auslöst, sowie ein positives Gegenbeispiel ohne diesen Befund aus. Der Converter entdeckt
`testedRules` aus dieser Matrix; CI verlangt `implementedRules == testedRules` und `coverage == 100`.
Die vollständige Rule-Dokumentation wird ebenfalls aus dem Registry gerendert und bytegenau geprüft.
