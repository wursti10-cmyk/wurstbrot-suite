# Accuracy Confidence and Golden References

## Zweck und Grenze

Accuracy 7 prüft die bestehende Graphpipeline unabhängig vom Legacy-Solver. Die Pipeline selbst wird
nicht erweitert. Accuracy 8 verwendet diese Evidenz für einen ausdrücklich aktivierten
CLI-Experimentalmodus. Legacy bleibt Standard und Empfehlung; GUI, Desktop-App und Browserlogik
verwenden keine Graphresultate.

Die Confidence-Schicht besteht aus versionierten Daten unter `accuracy/`, dem additiven Modul
`accuracy_confidence.py` und ausführbaren Python-/JavaScript-Harnesses. Sie besitzt keine
Folder-, Unlock-, Rank-, Optimizer- oder Kostenregel.

## Eingefrorene Baseline

`accuracy/baselines/2.57.1.67.json` friert folgende Fakten ohne Zeitstempel oder lokale Pfade ein:

- Datamine-, Validator-, Graph-, Pipeline- und Fingerprint-Versionen
- 2.232 Fahrzeuge, 44 Forschungsbäume, 395 Gruppen und 42 Validatorregeln
- semantischen Datamine- und vollständigen Graph-Fingerprint
- die Accuracy-6-Vergleichsbasis mit 2.090 Fällen
- fünf bekannte Contract-Differenzen
- 80 `unresolved_expected`, 80 partielle Pipeline-Ergebnisse und die 14 Partial-Sonderziele

Der Baseline-Fingerprint ist `accuracy-baseline-v1`. Er umfasst ausschließlich kanonischen,
fachlichen JSON-Inhalt. Eine neue Datamine-Version braucht eine neue Baseline-Datei; die alte Datei
wird nicht in-place auf die neue Version umgedeutet.

## Golden Reference Suite

`accuracy/golden/2.57.1.67.json` ist `manual_review_only` und `immutable`. Tests lesen die Datei nur;
es gibt keinen Update- oder Overwrite-Modus. Eine Änderung erfordert einen bewussten Review des
Fixture- und Result-Fingerprints.

| Teilmenge | Fälle |
|---|---:|
| alle realen Forschungsbäume | 44 |
| streng geprüfte reale A→B-Referenzen | 9 |
| gezielte Hidden-, Unlock-, Rank- und Long-Chain-Contracts | 7 |
| **Gesamt** | **60** |

Jeder Fall enthält ID, Zweck, Spielversion, Eingabe, erforderliche Fahrzeuge,
VehicleCostLines, vollständige Summen oder ausdrücklich `partial`/`blocked`, Rule IDs, einen
kanonischen Explanation Trace, Begründung, Herkunft und Reviewstatus. Erwartete RP-/SL-Grundwerte
werden direkt gegen die Datamine geprüft. Rest-RP, individuell aufgerundete GE, Rabatt-SL,
vorhandene GE und Convertible-RP-Shortfall werden nochmals unabhängig aus den dokumentierten
Formeln berechnet.

### Herkunft

| Herkunft | Fälle | Bedeutung |
|---|---:|---|
| `DATAMINE_DIRECT` | 37 | Erwartung folgt unmittelbar aus versionierten Feldern |
| `FORMULA_DERIVED` | 7 | Erwartung folgt aus Dataminewert und verbindlicher Formel |
| `LEGACY_CONFIRMED` | 1 | Legacy bestätigt nur; unabhängige Quellen sind zusätzlich Pflicht |
| `MANUALLY_REVIEWED` | 10 | A→B- oder Contract-Erwartung wurde fachlich geprüft |
| `SYNTHETIC_CONTRACT` | 3 | explizite Mini-Datenbank beweist einen isolierten Vertrag |
| `UNRESOLVED_SOURCE_LIMITATION` | 2 | `partial` ist die festgeschriebene korrekte Erwartung |

Ein Fall mit primärer Herkunft `LEGACY_CONFIRMED` muss mindestens Datamine, Formel, manuellen Review
oder einen synthetischen Contract als unabhängige Stütze nennen. Ein Legacy-Ergebnis allein ist kein
Golden-Beweis.

### Release-Candidate-Referenzen

Die neun besonders streng geprüften A→B-Fälle decken Deutschland, USA, UdSSR, Japan und Israel Boden,
eine Flugzeuglinie, einen Hubschrauberbaum, Bluewater und Coastal ab. Gemeinsam enthalten sie
Teilfortschritt am Ziel und Zwischenfahrzeug, ein gekauftes Zwischenfahrzeug, vorhandene GE,
Convertible-RP-Shortfall sowie 0/30/50-Prozent-SL-Rabatte. Rank- und Folder-Ergebnisse bleiben als
strukturierte Felder im erwarteten Contract sichtbar.

## Metamorphic Suite

Die 16 deterministischen Eigenschaften sind fahrzeugwertunabhängige Verträge:

1. mehr gültige RP erhöhen weder Rest-RP noch GE;
2. ein gekauftes Pflichtfahrzeug erhöht seine RP-/GE-/SL-Kosten nicht;
3. mehr vorhandene GE erhöhen den Restbedarf nicht und Rest-GE werden nie negativ;
4. ausreichende Convertible RP erzeugen keinen Shortfall, mehr davon erhöhen ihn nicht;
5. 30 % SL sind nicht teurer als 0 %, 50 % nicht teurer als 30 %;
6. Gesamt-GE sind die Summe individuell aufgerundeter Fahrzeugwerte;
7. identische Inputs und reine Mapping-Reihenfolgeänderungen bewahren Fingerprints;
8. irrelevanter Fortschritt verändert die fachliche Ergebnisprojektion nicht;
9. `complete` enthält keine unresolved Blocking Rule;
10. `partial` besitzt keine verbindlichen Summen;
11. `unavailable`/`blocked` erfindet keine VehicleCostLines.

Es werden keine Zufallswerte verwendet; `seed` ist deshalb ausdrücklich `null`.

## Cross-Python-Vertrag

`tests/accuracy_cross_python.py` muss unter Python 3.10, 3.12 und 3.13 exakt denselben
`accuracy-golden-results-v1`-Fingerprint liefern. Python-Version, Implementierung, Executable,
Plattform, Zeitstempel, Pfade und Objektadressen sind aus fachlichen Fingerprints ausgeschlossen.

## Browser-Shadow-Harness

`tests/browser_shadow_harness.mjs` liest dieselben unveränderlichen Golden Inputs und Ergebnisse. Es
prüft Fixture-/Result-Fingerprint, Status, Rule IDs, RP-/GE-/SL-Zeilen, Summen und incomplete-Semantik.
Es implementiert bewusst keine zweite Graphengine.

Der Status lautet `fixture_validation_only`: Eine Browser-Graph-Runtime existiert noch nicht.
Das ist dokumentierte fehlende Runtime-Parität, kein Match. `apps/web/`, UI und produktiver
Browser-Solver bleiben unverändert.

## Contract Decision Register

`accuracy/contracts/decision_register.json` führt fünf Punkte verbindlich:

| Entscheidung | Status | Release-blocking |
|---|---|---:|
| SL-Rabatt-Domain | `deferred` | ja |
| ungültige Progress-Werte | `deferred` | ja |
| `researched=True`/RP-Konflikt | `deferred` | ja |
| vorhandene GE bei Partial | `accepted` | nein |
| Legacy-Rank-Compatibility als Vergleichsbrücke | `accepted` | nein |

`deferred` wird nicht als Match behandelt. Für einen Shadow Release Candidate genügt, dass eine
offene Entscheidung ausdrücklich als release-blocking gekennzeichnet ist. Vor produktiver
Default-Nutzung muss sie beschlossen sein.

## Confidence Report

CI erzeugt `Accuracy_Confidence_<gameVersion>.json` und `.txt`. Der JSON-Bericht enthält Golden- und
Metamorphic-Ergebnisse, Herkunftsverteilung, Cross-Python-Vertrag, Browserstatus,
Pipeline-Vergleichszahlen, offene Entscheidungen, Sonderfallstatus, Readiness, Grenzen und
`accuracy-confidence-report-v1`-Fingerprint. Es gibt bewusst keinen Prozent- oder Health-Score.

## Readiness

- `ready_for_experimental_use=true` erlaubt Shadow und explizites CLI Graph Experimental mit
  parallelem Legacy-Vergleich und Fallback. Es ist keine Default-Freigabe.
- `ready_for_release_candidate=true` bezeichnet ausschließlich diesen geprüften Experimentalumfang:
  null
  Mismatches/Internal Errors, Golden und Metamorphic grün, 100 % Options-/Input-Abdeckung,
  dokumentierte Decisions, Browserstatus, Rollback-Plan und neun reale Referenzen.
- `ready_for_default_use=false` bleibt hart gesetzt. Browser-Runtime-Parität, Folder-Evidenz,
  Product-Owner-Entscheidungen, Entfernung oder Ablösung der Compatibility-Brücke und ein eigener
  Default-Umschalt-Review fehlen weiterhin.

Readiness aktiviert nie selbst eine Rechenquelle. `graph_experimental` verlangt bei jedem
CLI-Aufruf eine ausdrückliche Option; die Auswahl wird nicht gespeichert.

## Befehle

```bash
python tests/accuracy_golden_matrix.py
python tests/accuracy_metamorphic_matrix.py
python tests/accuracy_cross_python.py
python tests/graph_experimental_matrix.py --output build/health
node tests/browser_shadow_harness.mjs
```

Der vollständige Confidence Report benötigt zusätzlich den erzeugten Graph-Shadow- und
Browser-Shadow-Bericht; CI führt den vollständigen Aufruf reproduzierbar aus.
