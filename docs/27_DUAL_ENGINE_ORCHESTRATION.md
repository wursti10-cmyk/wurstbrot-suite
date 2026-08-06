# Dual Engine Orchestration

## Zweck

Accuracy 6 verbindet die drei getrennten Graphschichten zu einer einheitlichen Shadow-Pipeline:

```text
GraphRuleEvaluator -> GraphPrerequisiteResolver -> GraphCostEngine
```

`GraphCalculationPipeline` orchestriert diese Komponenten, dupliziert aber keine fachliche Regel.
`DualEngineRunner` führt zusätzlich den unveränderten `ResearchSolver` aus und vergleicht beide
Ergebnisse strukturiert. Kein produktiver Aufrufer verwendet das Graph-Ergebnis.

## Pipeline Contract

Eingaben sind `VehicleDatabase` oder `GraphDatabaseAdapter`, Ziel, optionaler Start,
`PlayerProgress` und `SolveOptions`. Das Ergebnis enthält:

- vollständige Rule Evaluation
- `PrerequisiteResolution`
- `GraphCostResult`
- Pipeline-Status und Status-Contract
- Input-Findings
- zusammenhängende Evidence und nummerierten Explanation Trace
- Graph- und Komponentendiagnostik
- stabilen fachlichen Fingerprint

| Status | Ursache | Blocking | User-safe | Legacy-vergleichbar |
|---|---|---:|---:|---:|
| `complete` | alle Komponenten vollständig | nein | ja | ja |
| `partial` | mindestens eine Regel unresolved | nein | ja | nein |
| `blocked` | eindeutig blockierende Regel | ja | ja | nein |
| `unavailable` | Dataminefehler oder nicht unterstütztes Modell | abhängig | ja | nein |
| `invalid_input` | Aufruf verletzt den Input-Contract | ja | ja | nein |
| `internal_error` | unerwarteter Komponentenfehler | ja | nein | nein |

Interne Exceptions werden auf Fehlercode, fehlgeschlagene Stufe und Exception-Typ reduziert. Ihre
Rohmeldung wird nicht als fachliche Explanation exportiert. `internal_error` darf niemals als
`unresolved` erscheinen.

## Input Validation Boundary

Die Pipeline unterscheidet:

- `invalid_input`: Ziel, Start, Fortschritt oder Optionen sind ungültig.
- `datamine_error`: ein notwendiger Datenbankwert ist strukturell unbrauchbar.
- `unresolved_rule`: die Quellen belegen eine fachliche Regel nicht eindeutig.
- `unsupported_feature`: das aktuelle Graphmodell kann den Fall nicht darstellen.
- `internal_error`: eine Implementierung ist unerwartet fehlgeschlagen.

Die ausführbare Input-Matrix deckt automatisch 18 Rule IDs ab: unbekannte Fahrzeuge,
Bauminkompatibilität, ungültige RP-Fortschritte und Status, ungültige GE/Convertible RP,
Unlock-Tokens, Boolean-Optionen, `optimize_for` und SL-Rabatte. Die Datamine-Grenze besitzt zusätzlich
drei fokussiert getestete Regeln für `gameVersion`, `rpPerGE` und Fahrzeugkosten.

`researched=True` mit einer nicht zum Fahrzeug passenden numerischen RP-Zahl ist ein nicht
blockierendes, aber sichtbares `INPUT_RESEARCH_FLAG_RP_CONFLICT`. Der Dual-Vergleich klassifiziert
diesen Fall als `input_contract_difference`; er wird nicht still normalisiert oder als Match gezählt.

## Dual Engine Contract

`DualEngineRunner` führt in fester Reihenfolge aus:

1. produktiven Legacy-Solver als Vergleichsquelle
2. vollständige Graphpipeline
3. deterministischen Feldvergleich

Ausgabe:

- serialisiertes Legacy-Ergebnis oder strukturierter Legacy-Fehler
- vollständiges Graphpipeline-Ergebnis
- Vergleichsstatus
- Feldunterschiede samt Contract-Regel und Rule IDs
- vergleichbare und ausgeschlossene Felder
- Evidence, Explanation Trace und beide Teil-Fingerprints
- Dual-Fingerprint

Verglichen werden Required-IDs, Rank-Anforderungen, RP/Rest-RP/GE/SL pro Fahrzeug, alle
vollständigen Summen, vorhandene GE und Convertible-RP-Shortfall. Legacy stellt
`satisfied_vehicle_ids`, Folder-, Unlock- und Rule-Evaluation-Ergebnisse nicht strukturiert bereit.
Diese Felder stehen deshalb mit Begründung in `excluded_fields`; der Graphwert wird nicht in Legacy
hineininterpretiert.

## Vergleichskategorien

| Kategorie | Bedeutung |
|---|---|
| `exact_match` | geordnete Voraussetzungen, Kostenzeilen und Summen identisch |
| `equivalent_match` | ausschließlich andere Reihenfolge/Repräsentation bei gleichen Mengen und Zahlen |
| `unresolved_expected` | Graph bewahrt eine offene Regel und gibt nur partielle Kosten aus |
| `unsupported` | keine belastbare gemeinsame Ergebnisrepräsentation |
| `input_contract_difference` | neue Input-Grenze und Legacy-Verhalten unterscheiden sich ausdrücklich |
| `mismatch` | beide Ergebnisse sind definitiv, aber fachlich verschieden |
| `internal_error` | mindestens eine Engine ist unerwartet fehlgeschlagen |

`mismatch` und `internal_error` sind CI-Fehler. `input_contract_difference` ist weder Match noch
Fehler und braucht eine dokumentierte Contract-Entscheidung.

## Fingerprints

- Graphpipeline: `graph-pipeline-fingerprint-v1`
- Legacy-Ergebnis: `legacy-result-v1`
- Dual-Vergleich: `dual-engine-comparison-v1`
- Gesamtbericht: `graph-shadow-report-v1`

Fingerprints verwenden kanonisches JSON über fachliche Eingaben, Status und Ergebnisse. Sie schließen
Zeitstempel, Dateipfade, Objektadressen und zufällige Reihenfolgen aus. Sie dienen ausschließlich der
Regressionserkennung und sind kein Sicherheits- oder Signaturmechanismus. Eine fachliche Änderung an
Fortschritt, Optionen oder Ergebnis ändert den Fingerprint.

## Full Shadow Matrix 2.57.1.67

Zählebene ist immer ein benannter Pipeline-Aufruf. Überschneidende Sachverhalte werden nur in ihrer
ausdrücklich ausgewiesenen Ebene gezählt:

| Ebene | Fälle |
|---|---:|
| reguläre Regression | 1.977 |
| Cost-Szenarien | 18 |
| PlayerProgress | 13 |
| Options-Kompatibilität | 15 |
| Sonderfälle | 49 |
| Invalid Input | 18 |
| **Gesamt** | **2.090** |

| Vergleich | Anzahl |
|---|---:|
| `exact_match` | 1.988 |
| `equivalent_match` | 0 |
| `unresolved_expected` | 80 |
| `unsupported` | 2 |
| `input_contract_difference` | 20 |
| `mismatch` | **0** |
| `internal_error` | **0** |

Pipeline-Status: 1.989 complete, 80 partial, 2 blocked, 0 unavailable, 19 invalid input und
0 internal error. Options- und Input-Validation-Coverage betragen jeweils 100 %.

Die 49 Sonderfälle bleiben 35 complete und 14 partial. Die partiellen Fälle sind keine vollständigen
Kosten und erhalten weiterhin keine angewandten vorhandenen GE.

## Shadow Report

CI veröffentlicht:

- `Graph_Shadow_<gameVersion>.json`
- `Graph_Shadow_<gameVersion>.txt`

Der JSON-Bericht enthält Komponenten-Versionen, Zählebenen, Vergleichs- und Statusverteilungen,
Options-/Input-Abdeckung, Sonderfallstatistik, einen kompakten Index aller 2.090 Berechnungen,
vollständige Diagnosen aller nicht exakten Fälle, Fingerprints, Grenzen und Readiness. Der Textbericht
ist die kompakte Gate-Zusammenfassung.

## Release Readiness

Aktueller maschinenlesbarer Status:

```json
{
  "ready_for_experimental_use": true,
  "ready_for_default_use": false
}
```

Shadow-Experimente sind erlaubt, weil Mismatch und Internal Error null sind und beide Coverage-Gates
100 % erreichen. Eine Default-Umschaltung ist blockiert durch offene Folderfälle,
Input-Contract-Entscheidungen, die Legacy-Rank-Compatibility-Brücke und die fehlende Graphpipeline im
Browser. Der Rollback-Pfad ist objektiv: `ResearchSolver` bleibt die produktive Ergebnisquelle.

## Nicht-Ziele

- keine produktive Solver-Umschaltung
- kein GUI- oder Browser-Schalter
- kein Optimizer und keine neue Rangwahl
- keine Folder- oder Unlock-Heuristik
- keine Telemetrie
- keine Euro-, Paket- oder Crewkosten
- keine automatische Release-Erstellung
