# Graph Prerequisite Resolution

## Zweck und Abgrenzung

`GraphPrerequisiteResolver` bestimmt in Shadow oder ausdrücklich aktiviertem CLI Graph Experimental,
welche Fahrzeuge und fachlichen Voraussetzungen
für ein Forschungsziel notwendig sind. Er baut auf `ResearchGraph` und `GraphRuleEvaluator` auf, gibt
aber weder RP, GE, SL oder Euro aus noch ersetzt er den standardmäßigen `ResearchSolver`.

Evaluation und Resolution sind getrennte Schritte:

| Ebene | Frage | Darf Fahrzeuge ergänzen? | Darf Kosten optimieren? |
|---|---|---:|---:|
| Rule Evaluation | Ist eine einzelne Regel erfüllt? | nein | nein |
| Prerequisite Resolution | Welche belegbaren Voraussetzungen fehlen? | ja | nein |
| Legacy Compatibility | Welche Rangmenge hätte der bestehende Solver gewählt? | nur in Vergleichsmodi | delegiert temporär an Legacy |

## Eingabe

- `ResearchGraph`
- `target_vehicle_id`
- optional `start_vehicle_id`
- `PlayerProgress`
- `SolveOptions`
- optional eine ausdrücklich aktivierte `LegacyRankCompatibilityStrategy`

`PlayerProgress.fulfilled_unlocks` enthält ausschließlich explizit bekannte Unlock-Tokens.
`SolveOptions.assume_external_unlocks=True` ist eine bewusste globale Annahme des Aufrufers. Ohne
eine dieser beiden Evidenzen wird ein externer Unlock niemals als erfüllt behandelt.

## Resolution Contract

`PrerequisiteResolution` enthält deterministisch:

- `target_vehicle_id`
- `start_vehicle_id`
- `required_vehicle_ids`
- `satisfied_vehicle_ids`
- `blocking_rule_results`
- `unresolved_rule_results`
- `rank_requirements`
- `folder_requirements`
- `unlock_requirements`
- `resolution_status`
- JSON-native `evidence`
- nummerierten `explanation_trace`
- `compatibility_mode`

Alle Fahrzeuglisten verwenden ohne Compatibility Mode den Graph-Sortierschlüssel Rang, Spalte,
Reihenfolge und ID. Der Compatibility Mode verwendet bewusst denselben stabilen Sortierschlüssel wie
der Legacy-Solver. Rule Results werden nach Rule-ID, Status, betroffenen Nodes, Edge-IDs und Erklärung
sortiert. Wiederholte Aufrufe mit identischen Eingaben erzeugen identische serialisierbare Ergebnisse.

## Resolution Status

| Status | Bedeutung |
|---|---|
| `resolved` | Alle notwendigen Voraussetzungen sind eindeutig bestimmt. |
| `blocked` | Eine eindeutige Regel verbietet den Aufruf mit den aktuellen Optionen oder Eingaben. |
| `unresolved` | Daten oder Semantik reichen für mindestens eine notwendige Entscheidung nicht aus. |
| `unsupported` | Ziel, Start oder Compatibility-Ausführung sind mit dem aktuellen Modell nicht zuverlässig vergleichbar. |

Priorität bei mehreren Befunden: `unsupported`, danach `blocked`, danach `unresolved`, danach
`resolved`. Ein unresolved Ergebnis ist weder Erfolg noch Mismatch. Unsupported wird ebenfalls weder
als Match noch als Fehler gewertet, solange beide Vergleichspfade keine belastbare gemeinsame
Voraussetzungsmenge liefern.

## Vorgängerauflösung

- Eindeutige `predecessor`-Kanten werden vollständig bis zur Wurzel traversiert.
- Das Ziel bleibt Teil der aufgelösten Kette; ist es bereits owned, erscheint es in
  `satisfied_vehicle_ids` statt erneut in `required_vehicle_ids`.
- Owned bedeutet weiterhin `researched=True` und `purchased=True`.
- Eine Owned-ID impliziert ihre eindeutige Vorgänger-Closure.
- Start A impliziert seine Closure. Mit `include_start_vehicle=True` wird A selbst wieder required.
- Ein nur erforschtes, nicht gekauftes A ist nicht owned.
- Teil-RP am Ziel ändert die Voraussetzungsliste nicht.
- Mehrfachvorgänger oder Zyklen bleiben mit allen Kanten unresolved; keine Kante wird gewählt.
- Hidden-Pflichtvorgänger werden ohne explizite Hidden-Option nicht still übergangen.

## Folder Resolution

Folder bleiben belegte Mitgliedschaft und Reihenfolge. Der Resolver unterscheidet:

- `membership_only`: Ziel ist Folder-Mitglied, daraus entsteht keine zusätzliche Pflicht.
- `required_member`: Das Mitglied ist wegen einer separaten Vorgängerkante erforderlich.
- `satisfied_member`: Das Mitglied ist durch Besitz oder Start A bereits erfüllt.

Fehlende Mitglieder, widersprüchliche Reihenfolge, versteckte Mitglieder oder mehrere Folder bleiben
unresolved, solange sie eine noch zu bestimmende Voraussetzung betreffen. Bei einem bereits erfüllten
Mitglied wird die Quellenanomalie als Evidence bewahrt, aber die Eligibility nicht erneut geöffnet.
Es gilt weder „erstes Mitglied genügt“ noch „alle Mitglieder sind Pflicht“.

## Unlock Resolution

| Fall | Verhalten |
|---|---|
| interne Fahrzeugreferenz | fehlende eindeutige Closure wird zu `required_vehicle_ids` ergänzt |
| interne Referenz bereits owned | satisfied |
| Token in `PlayerProgress.fulfilled_unlocks` | `fulfilled_by_progress` |
| globale explizite Annahme | `external_assumed_satisfied` |
| externer Token ohne Evidenz | unresolved |
| unbekannter oder widersprüchlicher Token | unresolved |
| reqUnlock-Fahrzeug bereits durch Owned/Start erfüllt | satisfied; Bedingung wird nicht erneut verlangt |

Unlocks werden nicht in `predecessor`-Kanten umgedeutet. Externe Erwerbswege oder Preise werden nicht
erraten.

## Rank Resolution und Compatibility Mode

Für jedes relevante positive Gate werden ausgewiesen:

- benötigte Anzahl
- bereits erfüllte Anzahl
- anfänglich fehlende Anzahl
- nach Resolution fehlende Anzahl
- zulässige Kandidaten
- ausgeschlossene Kandidaten mit Grund
- gegebenenfalls ausgewählte Compatibility-IDs

Ohne Compatibility Mode bleibt eine notwendige Kandidatenauswahl unresolved. Die
`LegacyRankCompatibilityStrategy` ist eine quarantänisierte Übergangsstrategie: Sie delegiert nur die
deterministische Rank-Auswahl an den unveränderten, kostenbewussten bestehenden Algorithmus. Ihr
Ergebnis heißt ausdrücklich nicht Graph-Optimizer-Ausgabe. Der Resolver selbst berechnet keine
Graphkosten und exportiert keinerlei Kostenwerte; die Delegation bleibt als
`legacyCompatibilityModeEnabled` und `legacyCompatibilitySelectionPerformed` sichtbar.

## Shadow-Kategorien

| Kategorie | Definition |
|---|---|
| `exact_match` | geordnete Legacy- und Graph-Voraussetzungslisten sind identisch |
| `equivalent_match` | Reihenfolge oder Repräsentation weicht ab, aber die fachliche Fahrzeugmenge ist exakt gleich |
| `unresolved_expected` | Graph bewahrt mindestens eine nicht eindeutig entscheidbare Voraussetzung |
| `unsupported` | keine belastbare gemeinsame Voraussetzungsliste ist vergleichbar |
| `mismatch` | beide Pfade liefern eindeutige, fachlich unterschiedliche Voraussetzungen |

`equivalent_match` darf nur bei identischen Mengen verwendet werden. Jeder `mismatch` lässt Test und
CI fehlschlagen. Eine Abweichungsdiagnose enthält Ziel, Start, vollständiges Progress-Szenario,
Legacy-/Graph-Mengen, beide Mengendifferenzen, abweichende Regeln, Evidence und Explanation Trace.

## Sample-Ergebnis 2.57.1.67

Die Vollmatrix umfasst die bestehenden 1.977 regulären Regressionen und 13 zusätzliche
PlayerProgress-Szenarien, insgesamt 1.990 Vergleiche:

| Kategorie | Anzahl |
|---|---:|
| `exact_match` | 1.926 |
| `equivalent_match` | 0 |
| `unresolved_expected` | 63 |
| `unsupported` | 1 |
| `mismatch` | **0** |

Die 63 unresolved Vergleiche teilen sich reproduzierbar in 26 Fälle mit
`FOLDER_MEMBERSHIP` und 37 Fälle mit `UNLOCK_REQUIREMENT` auf.

Die 13 Progress-Szenarien sind: kein Fortschritt, Start A owned, A nur erforscht, Ziel teilweise
angeforscht, ein vorhandener Vorgänger, mehrere vorhandene Fortschrittsfahrzeuge, Rang erfüllt, Rang
teilweise erfüllt, Folder-Mitglied owned, Hidden erlaubt/nicht erlaubt sowie externer Unlock
angenommen/nicht angenommen. Ergebnis: 10 exact, 2 unresolved expected, 1 unsupported, 0 mismatch.

Die [49er Vorher-/Nachher-Matrix](24_GRAPH_RESOLUTION_SPECIAL_CASE_MATRIX.md) verbessert die explizit
aufgelösten Fälle von 0 auf 35. Vierzehn Hidden-Folder-Ziele bleiben wegen der bereits dokumentierten
Folder-Quelldaten bewusst unresolved; unsupported und mismatch sind jeweils 0.

## Nicht-Ziele und Grenzen

- keine Default-Ablösung des Legacy-Solvers
- keine RP-/GE-/SL-/Euro-Berechnung
- keine neue Rank- oder Kostenoptimierung
- keine automatische AND-/OR-Entscheidung für Mehrfachvorgänger
- keine Folder-Heuristik
- keine implizite externe Unlock-Annahme
- keine GUI- oder Browser-Laufzeitintegration

Die Compatibility-Strategie greift vorübergehend auf eine private, unveränderte Legacy-Methode zu.
Diese Kopplung ist absichtlich isoliert und muss entfernt werden, sobald ein späterer Optimizer-Sprint
einen eigenen belegten Auswahlvertrag bereitstellt. Ein solcher Sprint ist bis Version 1.0
ausdrücklich kein Arbeitsziel.

## Nachgelagerte Kostenprojektion

Accuracy 5 ergänzt downstream eine separate `GraphCostEngine`. Sie konsumiert dieses unveränderte
Resolution-Ergebnis, darf keine Required-IDs ergänzen und gibt vollständige Summen ausschließlich bei
`resolution_status=resolved` aus. Der Resolver selbst bleibt kostenfrei. Details stehen in
[Graph Cost Engine](25_GRAPH_COST_ENGINE.md).
