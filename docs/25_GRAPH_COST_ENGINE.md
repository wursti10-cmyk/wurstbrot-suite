# Graph Cost Engine

## Zweck und Abgrenzung

`GraphCostEngine` berechnet in Shadow oder ausdrücklich aktiviertem CLI Graph Experimental RP-, GE-
und SL-Kosten für eine bereits erzeugte
`PrerequisiteResolution`. Die Engine wählt keine Fahrzeuge, löst keine Regeln und verändert den
standardmäßigen `ResearchSolver` nicht.

| Ebene | Verantwortung | Kostenwerte |
|---|---|---:|
| Rule Evaluation | einzelne Voraussetzung bewerten | nein |
| Prerequisite Resolution | erforderliche Fahrzeugmenge bestimmen | nein |
| Graph Cost Engine | belegte Fahrzeugmenge bepreisen | ja, Shadow/CLI Experimental |

GUI, Browser, Desktop, GE-Pakete, Europreise und Crewkosten verwenden diese Schicht nicht.

## Cost Contract

`GraphCostResult` enthält deterministisch:

- Ziel- und Start-ID sowie den übernommenen `resolution_status`
- `cost_status`: `complete`, `partial` oder `unavailable`
- sortierte `vehicle_cost_lines`
- vollständige RP-/GE-/SL-Summen oder ausdrücklich `null`
- vorhandene GE, Convertible RP, SL-Rabatt und RP je GE
- `incomplete_reason_codes`, Warnungen, Evidence und nummerierten Explanation Trace
- getrennte bekannte Teilsummen für ein partielles Ergebnis

Eine `GraphVehicleCostLine` enthält Fahrzeug-ID, Kostenursache, Gesamt- und Fortschritts-RP,
Rest-RP, individuell gerundete GE, Basis- und rabattierte SL, getrennte Forschungs-/Kauf-Flags,
`cost_applicable` und Quelldaten-Evidence.

## Status-Propagation

| Resolution | Cost status | Verhalten |
|---|---|---|
| `resolved` | `complete` | vollständige Fahrzeugzeilen und Gesamtsummen |
| `unresolved` | `partial` | nur bekannte Zeilen und Teilsummen; vollständige Summen sind `null` |
| `blocked` | `unavailable` | keine Zeilen oder Summen |
| `unsupported` | `unavailable` | keine Zeilen oder Summen |

Vorhandene GE werden nie auf partielle Kosten angewandt. Damit kann eine Teilrechnung nicht wie eine
vollständige Kaufanforderung erscheinen.

## RP und Fortschritt

Für valide angeforschte RP gilt je Fahrzeug:

```text
remaining_rp = max(total_rp - researched_rp, 0)
```

- Negative, nicht ganzzahlige oder über Gesamt-RP liegende Fortschrittswerte blockieren die
  Graph-Kostenberechnung; sie werden nicht geklemmt.
- `researched=True` bedeutet 0 Rest-RP, auch wenn das Fahrzeug noch nicht gekauft ist.
- `purchased=True` impliziert 0 Rest-RP und 0 zusätzliche SL.
- Forschungs- und Kaufstatus bleiben getrennt in jeder Zeile sichtbar.
- Reservefahrzeuge verursachen keine zusätzlichen Kosten.
- Null-RP- und Null-SL-Werte bleiben mit Evidence und Warning sichtbar.

Der Legacy-Solver klemmt aus Kompatibilitätsgründen weiterhin numerische Fortschrittswerte. Diese
unterschiedliche Eingabevalidierung bleibt als sichtbare Contract-Differenz bestehen; Graph
Experimental verwendet in diesem Fall Legacy-Fallback.

## GE

```text
vehicle_ge = ceil(remaining_rp / rp_per_ge)
```

Die Aufrundung erfolgt für jedes Fahrzeug einzeln. Erst anschließend werden die GE-Zeilen summiert
und vorhandene GE abgezogen. Das Ergebnis nach Abzug ist mindestens 0. Ein nicht positiver
`rp_per_ge`-Wert macht Kosten vollständig unavailable.

## SL

Die Shadow Engine akzeptiert ausschließlich die belegten Rabattstufen 0 %, 30 % und 50 %. Der
Rabatt wird mit dem bestehenden deterministischen `apply_discount` pro Fahrzeug angewandt. Gekaufte
und Reservefahrzeuge erzeugen 0 zusätzliche SL. Andere Rabattwerte werden mit
`INVALID_SL_DISCOUNT` abgelehnt.

## Convertible RP

Bei begrenzten Convertible RP gilt für vollständige Ergebnisse:

```text
shortfall = max(total_remaining_rp - convertible_rp_available, 0)
```

`None` bedeutet nicht angegeben beziehungsweise unbegrenzt; der Shortfall ist dann 0. Für partielle
oder nicht verfügbare Ergebnisse bleibt der Shortfall `null`.

## Shadow-Vergleich

Der Vergleich prüft Fahrzeugmenge, Rest-RP, GE und SL pro Fahrzeug, alle Gesamtsummen, vorhandene GE
und Convertible-RP-Shortfall. Kategorien entsprechen dem Resolution-Vertrag:

- `exact_match`: Reihenfolge, Fahrzeugzeilen und Summen identisch
- `equivalent_match`: gleiche Fahrzeugkosten und Summen bei anderer Darstellung
- `unresolved_expected`: nur partielle Graphkosten zulässig
- `unsupported`: keine belastbare gemeinsame Kostenrepräsentation
- `mismatch`: beide Ergebnisse sind eindeutig und unterscheiden sich

Jeder breite `mismatch` beendet das CI-Gate mit Fehler. Die Diagnose enthält Ziel, Start, komplettes
Fortschrittsszenario, Resolution-/Cost-Status, beide VehicleCostLine-Listen, Fahrzeugdifferenzen,
RP-/GE-/SL-Differenzen, abweichende Rundung, Evidence und Explanation Trace.

## Sample-Ergebnis 2.57.1.67

Die breite Matrix enthält 1.977 bestehende Regressionen und 18 Cost-Szenarien:

| Kategorie | Anzahl |
|---|---:|
| `exact_match` | 1.932 |
| `equivalent_match` | 0 |
| `unresolved_expected` | 63 |
| `unsupported` | 0 |
| `mismatch` | **0** |

Cost-Status: 1.932 `complete`, 63 `partial`, 0 `unavailable`.

Die 18 fokussierten Szenarien ergeben 16 exact und 2 unresolved expected. Sie decken leeren,
teilweisen und vollständigen Forschungsfortschritt, Kaufstatus, Start A, vorhandene GE, Convertible
RP, drei SL-Rabatte, Null-RP, Null-SL sowie je einen offenen Folder- und Unlock-Fall ab.

Die [49er Kostensonderfallmatrix](26_GRAPH_COST_SPECIAL_CASE_MATRIX.md) enthält 35 vollständige und
14 partielle Ergebnisse. Kein Sonderfall wird durch eine Folder-, Unlock- oder
Mehrfachvorgänger-Heuristik vollständig gerechnet.

## Nicht-Ziele und Grenzen

- keine Default-Solver-Umschaltung
- keine neue Rank-Auswahl oder Optimizer-Semantik
- keine Euro-, Paket-, Crew- oder Sale-Logik
- keine Kosten für unbekannte Voraussetzungen
- keine Verteilung vorhandener GE oder Convertible RP auf einzelne Fahrzeugzeilen
- keine GUI-, Browser- oder Desktop-Integration

Die `LegacyRankCompatibilityStrategy` kann weiterhin nur die Legacy-Fahrzeugmenge für den
Dual-Vergleich liefern. Ihre Auswahl ist keine fachliche Graph-Optimizer-Regel. Ein Optimizer-Ausbau
ist bis Version 1.0 kein Arbeitsziel.
