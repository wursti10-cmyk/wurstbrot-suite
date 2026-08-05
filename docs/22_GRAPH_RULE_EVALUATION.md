# Graph Rule Evaluation

## Status

Die Evaluationsschicht bewertet Voraussetzungen parallel zum unveränderten Legacy-Solver. Sie wählt
keine Fahrzeuge aus, optimiert keine Kosten und erzeugt keine Benutzererklärung. Eingaben sind
`ResearchGraph`, Ziel-ID, `PlayerProgress`, `SolveOptions` sowie optional Startfahrzeug und ausdrücklich
angenommene externe Unlock-Tokens.

Jede `RuleEvaluation` enthält:

- `rule_id`
- `status`: `satisfied`, `unsatisfied`, `not_applicable` oder `unresolved`
- deterministisch sortierte `affected_node_ids`
- JSON-native `evidence`
- technische `explanation`
- deterministisch sortierte `source_edge_ids`
- `blocking`

## Statussemantik

| Status | Bedeutung |
|---|---|
| `satisfied` | Die Regel gilt und ist mit den vorliegenden Daten erfüllt. |
| `unsatisfied` | Die Regel ist eindeutig, aber der aktuelle Fortschritt erfüllt sie nicht. |
| `not_applicable` | Für das Ziel existiert keine entsprechende Voraussetzung. |
| `unresolved` | Quelldaten oder Semantik reichen nicht für eine eindeutige Entscheidung. |

`unresolved` ist weder bestanden noch automatisch ein Datenfehler. `blocking` beschreibt, ob die
ungeklärte beziehungsweise unerfüllte Regel Research Eligibility verhindert. Folder-Unklarheit ist
beispielsweise diagnostisch unresolved, aber nicht blockierend, weil keine eigenständige
Freischaltungswirkung belegt ist.

## Verbindliche Kantensemantik

| Kante | Richtung | Kardinalität | Eligibility und Fortschritt | Kosten |
|---|---|---|---|---|
| `predecessor` | Vehicle → Vehicle | Graph: 0..n; Legacy-Adapter: 0..1 | genau eine Kante ist Pflicht; mehrere sind unresolved; erfüllte Fahrzeuge können für Rang zählen | Kante selbst kostet nichts |
| `folder_member` | Folder → Vehicle | Folder: 0..n; Vehicle erwartet 0..1 Folder | Mitgliedschaft und Reihenfolge sind Fakten, aber keine eigene Research-, Purchase- oder Rank-Regel | kein Einfluss |
| `unlock_requirement` | Unlock → Vehicle | 0..n; verschiedene Tokens sind widersprüchlich | internes Ziel ist prüfbar; externer Zustand kann unresolved sein; nie als Vorgänger behandeln | externer Erwerbspreis unbekannt |
| `rank_requirement` | Rank → Vehicle des Folgerangs | Gate: 0..n Ziele | positive `requiredVehicles` sperren Forschung des Folgerangs; Evaluation zählt und listet, wählt aber nicht | Kandidatenauswahl bleibt späterem Optimizer vorbehalten |

Die ausführbare Quelle ist `EDGE_SEMANTICS` in `graph_semantics.py`; die Spec enthält denselben Vertrag.

## Regeln

### TARGET_VISIBILITY

Ein nicht verstecktes Ziel ist `not_applicable`. `hiddenResearch` ist nur mit
`include_hidden_legacy=True` satisfied, andernfalls eindeutig unsatisfied und blockierend. Die Regel
behauptet keine Erwerbsmethode.

### PREDECESSOR_REQUIREMENTS

Alle eingehenden `predecessor`-Kanten werden vollständig traversiert. Besitz impliziert die jeweilige
Vorgänger-Closure. Eine Start-ID behandelt ihre Closure entsprechend dem Legacyvertrag als erfüllt;
`include_start_vehicle` lässt das Startfahrzeug selbst in der Required-Menge. Reservefahrzeuge zählen
bei Rank Evaluation als vorhanden, werden aber nicht fälschlich als Start-Closure interpretiert.

Null Vorgänger ergibt `not_applicable`. Mehrere Vorgänger oder ein Zyklus ergeben `unresolved` mit allen
beteiligten Edge-IDs; es wird keine Kante ausgewählt.

### START_TREE_COMPATIBILITY

Ohne Startfahrzeug ist die Regel not_applicable. Andernfalls müssen Start und Ziel dasselbe Land und
dieselbe Fahrzeugart besitzen. Ein Baumwechsel ist eindeutig unsatisfied und blockierend; die
Start-Closure wird dann nicht als erfüllt übernommen.

### FOLDER_MEMBERSHIP

Belegt sind ausschließlich Mitgliedschaft und `groupIndex`-Reihenfolge. Folder erzeugen keine eigene
Research-, Purchase-, Rank- oder Kostenregel. Fehlende Mitglieder, mehrere Folder, versteckte
Mitglieder oder widersprüchliche Reihenfolge werden unresolved dokumentiert. Singleton-Folder und
bereits besessene Mitglieder bleiben gültige Mitgliedschaften.

### UNLOCK_REQUIREMENT

| Klassifikation | Entscheidung |
|---|---|
| `internally_resolvable` | Token referenziert ein bekanntes Fahrzeug; Owned-State ist prüfbar |
| `external_assumed_satisfied` | Aufrufer hat genau dieses externe Token ausdrücklich angenommen |
| `external_not_checkable` | bekanntes externes Tokenmuster, aber kein PlayerProgress-Zustand |
| `unknown` | Token besitzt keine definierte Semantik |
| `contradictory` | mehrere unterschiedliche Tokens betreffen dasselbe Ziel |

Nicht prüfbare, unbekannte und widersprüchliche Unlocks sind unresolved. Externe Unlocks werden nie in
normale Vorgängerkanten umgewandelt.

### RANK_REQUIREMENT_n

Für jeden positiven Gate-Wert vor dem Ziel meldet die Evaluation:

- benötigte Fahrzeuganzahl
- vorhandene qualifizierende Fahrzeuge
- fehlende Anzahl
- alle qualifizierenden Kandidaten
- ausgeschlossene Kandidaten mit Grund
- `selectionPerformed: false`

Als vorhanden zählen Besitz, Start-Closure, Reserve und ohnehin notwendige Vorgängerpfade im selben
Land, derselben Fahrzeugart und demselben Rang. Premium, `special`, standardmäßig Hidden sowie
ungeklärte `reqUnlock`-Kandidaten werden mit Grund ausgeschlossen. Es wird keine günstigste Kombination
ausgewählt.

## Mirror Evaluation 2.57.1.67

| Kategorie | Anzahl | Bedeutung |
|---|---:|---|
| `exact_match` | 2.170 | Legacy-Direct-Requirements und Graph Evaluation sind identisch |
| `unresolved_expected` | 44 | externe Unlock- oder belegte Folder-Unklarheit; nicht als Erfolg gezählt |
| `mismatch` | 0 | jede Zahl größer null ist ein Fehler |
| `unsupported` | 18 | Hidden-Ziel wird vom Default-Legacyvertrag abgelehnt |

Die Kategorien decken alle 2.232 Sample-Fahrzeuge ab. Die bisherige 1.977er Solverregression bleibt
zusätzlich unverändert bestehen.

## Verfeinerte Graphdiagnostik 2.57.1.67

| Knotentyp | Roots | Leaves | Isoliert |
|---|---:|---:|---:|
| Vehicle | 96 | 604 | 11 |
| Folder | 395 | 6 | 6 |
| Unlock | 21 | 0 | 0 |
| Rank | 450 | 205 | 205 |
| **Gesamt** | **962** | **815** | **222** |

Komponenten nach Fahrzeugklasse zählen Komponenten, die mindestens ein entsprechendes Fahrzeug
enthalten:

| Klasse | Komponenten |
|---|---:|
| regulär | 129 |
| Premium | 0 |
| hiddenResearch | 5 |
| reqUnlock | 21 |
| Reserve | 45 |

Weitere Komponentenkennzahlen:

- 351 schwach zusammenhängende Komponenten insgesamt
- 234 Komponenten ohne regulären Vehicle-Root
- 11 Komponenten ausschließlich mit Sonderfahrzeugen
- Komponenten mit Vehicle Nodes: 140; Folder: 70; Unlock: 21; Rank: 249
- Fahrzeugarten: Army 55, Aviation 55, Boats 12, Helicopters 10, Ships 8
- Nationen: Britain 17, China 11, France 17, Germany 18, Israel 3, Italy 15, Japan 16,
  Sweden 12, USA 16, USSR 15

Getrennte und reine Sonderfallkomponenten sind erwartete Struktur, kein Fehler. Isolierte Knoten und
Komponenten ohne regulären Root sind `attention`; sie verlangen Kontextprüfung. Nur Zyklen werden als
`invalid` klassifiziert, im Sample sind es null.

## Evaluationsstatusverteilung

Über alle pro Ziel erzeugten Regeln:

| Status | Anzahl |
|---|---:|
| `satisfied` | 885 |
| `unsatisfied` | 8.275 |
| `not_applicable` | 8.669 |
| `unresolved` | 58 |

Hohe `unsatisfied`-Zahlen sind erwartbar: Evaluation prüft Ziele gegen leeren `PlayerProgress` und
wählt absichtlich keine Rank-Kandidaten.

## Sonderfälle

Die generierte [49er Sonderfallmatrix](21_GRAPH_SPECIAL_CASE_MATRIX.md) dokumentiert pro Ziel Flags,
Folder, Status, Regressionsblocker und benötigte zusätzliche Daten. 31 externe Unlock-Ziele sind
unresolved; 18 Hidden-Ziele sind unter Default-Optionen unsatisfied. Event und Squadron bleiben mangels
entsprechender Evidenz im regulär gefilterten Sample unklassifiziert.
