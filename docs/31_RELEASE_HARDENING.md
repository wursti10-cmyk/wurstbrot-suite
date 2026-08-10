# Accuracy 10 Release Hardening

## Zweck und Scope

Accuracy 10 ist ein reines Release-Gate für den bestehenden Kernrechner. Es ergänzt keine
Solverregel, keine Graphsemantik und keine Benutzerfunktion. Legacy bleibt Standard und Empfehlung;
`shadow` bleibt eine Vergleichsausführung und `graph_experimental` bleibt pro CLI-Aufruf opt-in.
Browser, Desktop und GUI verwenden weiterhin ausschließlich Legacy.

## Unabhängige reale A→B-Abnahme

Die maschinenlesbare Eingabematrix liegt in
`accuracy/acceptance/release_hardening_2.57.1.67.json`. Sie ist
`manual_review_only`, unveränderlich markiert und besitzt keinen automatischen Updatepfad.

| Quelle | Reale A→B-Fälle | Sollwertquelle |
|---|---:|---|
| Accuracy-10-Direktmatrix | 44 | statischer direkter Vorgänger plus Datamine-RP/SL und verbindliche Formeln |
| bestehende streng geprüfte Golden E2E | 9 | eingefrorene Golden Expectations |
| Accuracy-9-Kernreferenzen | 8 | Datamine, Formel und manueller Review |
| **Gesamt** | **61** | Legacy ist nie alleinige Sollwertquelle |

Die 44 neuen Fälle decken jeden Forschungsbaum genau einmal ab. Sie verwenden absichtlich
eindeutige sichtbare, ordnerfreie, unlockfreie Vorgängerkanten desselben Rangs. Dadurch ist der
statisch gespeicherte Direktpfad unabhängig aus der Datamine beweisbar. Ein Reservefall aktiviert
`include_start_vehicle` ausdrücklich und prüft dadurch echte Null-RP-/Null-SL-Kostenzeilen; die
übrigen Direktfälle erwarten nur das Ziel. Kosten werden je Fahrzeug aus
Datamine-RP/SL, Fortschritt, `ceil(remainingRP / rpPerGE)`, vorhandenem GE, Convertible RP und dem
0/30/50-SL-Vertrag abgeleitet. Graph- und Legacy-Ausgaben werden nur gegen diese Sollwerte geprüft.

Gemeinsam mit den bestehenden Referenzen umfasst die Matrix alle zehn Nationen, alle fünf
Fahrzeugarten, alle 44 Bäume, kurze/mittlere/lange Pfade, Root→Mid, Mid→Late, Rankwechsel,
Fortschritts- und Kaufzustände, Folder, `reqUnlock`, `hiddenResearch`, Reserve-, Null-RP-/Null-SL-
Fälle, vorhandene GE, Convertible RP und alle drei gültigen SL-Rabatte.

## Execution-Mode-Gate

Jeder der 44 direkten Fälle läuft durch exakt drei Modi:

- `legacy`: Legacy ist Ergebnisquelle; Graph wird nicht ausgeführt.
- `shadow`: Legacy bleibt Ergebnisquelle; der Vergleich muss `exact_match` sein.
- `graph_experimental`: Graph darf nur bei `complete + exact_match` Ergebnisquelle sein; für diese
  eindeutigen Fälle ist kein Fallback zulässig.

Die bestehenden Accuracy-8-Fallback-, Partial- und Invalid-Input-Verträge bleiben unverändert. Ein
`equivalent_match` ist weiterhin nicht ausreichend.

## Deterministische Boundary-Matrix

Die zusätzliche Matrix enthält 32 benannte Fälle ohne Zufall oder Fuzz-Seed:

- 20 ungültige Eingaben: leere/unbekannte IDs, fremde Nation/Fahrzeugart, negative oder überhöhte
  RP, widersprüchlicher Research-/Purchase-Status, negative GE/Convertible RP, ungültige Rabatte
  und unbekannte Optimierungsoption;
- 12 gültige Grenzen: 0/1/`total-1`/volle RP, gekauft, sehr große nichtnegative GE/Convertible RP,
  Convertible RP an der exakten Grenze sowie Rabatt 0/30/50.

Ungültige Graph-Experimental-Eingaben liefern kein Benutzerergebnis und keinen Legacy-Fallback.
Eine bestehende Repräsentationsdifferenz bleibt sichtbar: Ein leerer optionaler Start wird von der
Legacy-Python-API wie `None` behandelt, die Graphgrenze lehnt ihn als `invalid_input` ab. Graph
Experimental verwirft das Legacy-Ergebnis. Diese Zeile ist ausdrücklich ein Contract-Unterschied,
kein Match und kein stiller Erfolg; der CLI-Normalfall verwendet `None` für einen nicht gesetzten
Start.

## Partial- und Performance-Gate

Alle 14 Hidden-Folder-Ziele werden erneut gegen die Accuracy-9-Akte geprüft. Sie müssen `partial`
bleiben und im Experimentalmodus sichtbar Legacy-Fallback verwenden. Die Matrix darf weder die
Zahl senken noch eine Folder-, Kauf-, Rang- oder Unlock-Heuristik einführen.

Der Performance-Smoke misst 132 Ausführungen der 44 direkten Fälle über drei Modi mit einer bewusst
großzügigen 30-Sekunden-Grenze. Er erkennt nur grobe Regressionen und ist kein Benchmark. Die
gemessene Zeit ist plattformabhängig und daher vom fachlichen Report-Fingerprint ausgeschlossen.

## Browser und Python-Versionen

`tests/accuracy_cross_python.py` validiert zusätzlich den eingefrorenen
`accuracy10-direct-results-v1`-Fingerprint in der CI-Matrix unter Python 3.10, 3.12 und 3.13.
`tests/browser_release_hardening.mjs` rechnet dieselben 44 direkten Fälle mit der produktiven
Legacy-Browserengine und prüft statisch, dass Web und Desktop-GUI keine Graphaktivierung enthalten.
Es wird keine Browser-Graph-Runtime eingeführt.

## Readiness Report

CI erzeugt:

- `Accuracy_Release_Hardening_<gameVersion>.json`
- `Accuracy_Release_Hardening_<gameVersion>.txt`

Der Readiness-Block enthält mindestens:

- `ready_for_rc_review`, `ready_for_release_candidate`, `ready_for_default_use`;
- Mismatches, Internal Errors, bestandene Golden-/Real-/Boundary-Fälle;
- Cross-Python- und Browser-Legacy-Status;
- offene Contract Decisions, Partial-Fälle, Blocker und Warnungen.

`ready_for_rc_review` und `ready_for_release_candidate` werden nur ohne Blocker true: 0 Mismatches,
0 Internal Errors, alle unabhängigen Referenzen und Boundary-Fälle grün, mindestens 50 reale A→B-
Fälle, 14 dokumentierte Partial-Fälle, kein Health Error, keine offene Contract Decision sowie
belegte Cross-Python- und Browser-Legacy-Gates. Zusätzlich müssen Python-Regression, Graph Mirror
und Browser-Regression jeweils 1.977/1.977 sowie der Validator 100 Prozent Coverage bei identischer
implementierter und getesteter Regelmenge melden. `ready_for_default_use` bleibt in Accuracy 10
hart auf `false`; der Bericht schaltet keine Engine um.

## Befehle

```bash
python tests/accuracy_cross_python.py
node tests/browser_release_hardening.mjs
python tests/release_hardening_matrix.py \
  --shadow-report build/health/Graph_Shadow_2.57.1.67.json \
  --experimental-report build/health/Graph_Experimental_2.57.1.67.json \
  --confidence-report build/health/Accuracy_Confidence_2.57.1.67.json \
  --health-report build/health/WT_Health_2.57.1.67.json \
  --browser-report build/health/Browser_Release_Hardening_2.57.1.67.json \
  --python-regression-report build/health/Python_Regression_2.57.1.67.json \
  --browser-regression-report build/health/Browser_Regression_2.57.1.67.json \
  --output build/health
```

Die Release-Hardening-Fixture darf nicht automatisch aus Legacy oder Graph neu erzeugt werden. Eine
Änderung erfordert bewussten Datamine-/Formelreview und einen neuen versionierten Fingerprint.
