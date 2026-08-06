# Research Graph Specification

## Zwei parallele Verträge

1. **Legacy-Vertrag:** Schema-v1-`predecessors` und `VehicleDatabase.closure`; produktive Grundlage des
   unveränderten Solvers.
2. **Foundation-Vertrag:** `ResearchGraph` mit typisierten Knoten und Kanten; derzeit ausschließlich
   Adapter-, Mirror-, Diagnose- und Debug-Export-Schicht.

Eine spätere Graph Engine darf erst nach eigenem fachlichen Sprint den Legacy-Vertrag ersetzen.

## Begriffe

- **Baum:** alle Fahrzeuge mit gleichem `countryId` und `branchId`
- **Vorgänger:** `predecessors[id]`
- **Closure:** geordnete Pflichtkette von Wurzel bis einschließlich Ziel
- **Owned:** erforscht und gekauft
- **Required:** Fahrzeug, dessen Kosten im Ergebnis betrachtet werden

## Gültigkeit

1. Jede Fahrzeug-ID ist eindeutig.
2. Jeder nichtleere Vorgänger verweist auf eine bekannte ID.
3. Vorgängerkanten bilden keinen Zyklus.
4. Kanten dürfen nicht Nation oder Fahrzeugart wechseln.
5. Der Vorgängerrang darf nicht über dem Nachfolgerrang liegen.

Der Loader erzwingt 1 bis 3. Der Converter-Validator prüft zusätzlich 4 und 5.

## Solve(A, B)

1. B laden und verstecktes B standardmäßig ablehnen.
2. Falls A gesetzt: gleicher Baum wie B, sonst Fehler.
3. Owned um Closures explizit vorhandener Fahrzeuge erweitern.
4. Falls A gesetzt: Closure(A) als überwunden behandeln; A nur mit Option berechnen.
5. Closure(B) minus Owned bildet den direkten Pflichtpfad.
6. Reservefahrzeuge als vorhanden zählen.
7. Für relevante Ränge die `rankUnlock`-Anzahl prüfen.
8. Fehlende Rangfahrzeuge kostenoptimiert samt Closure ergänzen.
9. Required deterministisch nach Rang, Spalte, Reihenfolge und ID sortieren.

## Fehler

Unbekannte IDs, Zyklen, Baumwechsel, nicht erfüllbare Rangschranken und überschrittenes Suchlimit sind
keine Teilresultate, sondern Fehler.

## Foundation-Knoten

| Typ | Identität | Verbindliche Quelle |
|---|---|---|
| `vehicle` | Fahrzeug-ID | `vehicles[].id` |
| `folder` | Gruppen-ID | `groups`-Schlüssel |
| `unlock` | Hash-ID, vollständiger Wert in `entityId` | nichtleeres `reqUnlock` |
| `rank` | Land/Fahrzeugart/Quellrang | `rankUnlock` |

## Foundation-Kanten

Alle Kanten zeigen von Voraussetzung oder Struktur zum betroffenen Fahrzeug.

| Typ | Quelle → Ziel | Semantik |
|---|---|---|
| `predecessor` | Fahrzeug → Fahrzeug | direkte Forschungsvoraussetzung |
| `folder_member` | Folder → Fahrzeug | geordnete Mitgliedschaft |
| `unlock_requirement` | Unlock → Fahrzeug | bewahrte externe Bedingung |
| `rank_requirement` | Rank → Fahrzeug im Folgerang | Zuordnung der Rangschranke |

Folder-, Unlock- und Rank-Kanten erzeugen im aktuellen Solver keine zusätzlichen Kosten. Das Modell
erlaubt mehrere Vorgängerkanten; `GraphDatabaseAdapter.closure()` verlangt für Legacy-Kompatibilität
weiterhin höchstens eine eingehende Vorgängerkante.

## Determinismus und Export

- Knoten sortieren nach `node_id`.
- Kanten sortieren nach Typ, Quelle, Ziel und kanonischen Metadaten.
- JSON-Export verwendet `schemaVersion: 1` und enthält `gameVersion`, `nodes`, `edges` und
  `diagnostics`.
- Wiederholter Build derselben Datenbank muss identische serialisierbare Strukturen liefern.

## Mirror-Invariante

Für jeden regulären Fall der bestehenden Python-Regression gilt:

`ResearchSolver(VehicleDatabase).solve(input) == ResearchSolver(GraphDatabaseAdapter).solve(input)`

Verglichen wird das vollständige unveränderliche `SolveResult`. Jede Abweichung ist ein Testfehler.

## Diagnostik

- Roots: Eingangsgrad null über alle Kanten.
- Leaves: Ausgangsgrad null über alle Kanten.
- Components: schwach zusammenhängende Komponenten.
- Cycles: zyklische stark zusammenhängende Komponenten einschließlich Selbstkanten.
- Longest Path: maximale Kantenzahl im DAG, andernfalls `null`.
- Average Branching Factor: Kanten geteilt durch Knoten mit Ausgangsgrad größer null.

## Verbindliche Kantensemantik

### PREDECESSOR (`predecessor`)

- Richtung: Voraussetzung-Fahrzeug → abhängiges Fahrzeug.
- Kardinalität: Graph 0..n eingehend; Legacy-Adapter 0..1.
- Pflicht: genau eine Kante ist eine Pflichtvoraussetzung. Mehrere sind ohne AND-/OR-Vertrag unresolved.
- Research Eligibility: Vorgänger muss erfüllt sein.
- Purchase Eligibility: keine unabhängige Regel belegt.
- Rank Progress: erfülltes qualifizierendes Fahrzeug kann zählen.
- Kosten: Kante selbst hat keinen Preis; Kosten bleiben im Legacy-Solver.

### FOLDER_MEMBER (`folder_member`)

- Richtung: Folder → Mitgliedfahrzeug.
- Kardinalität: Folder 0..n; Fahrzeug soll höchstens einem Folder angehören.
- Pflicht: Mitgliedschaft und Reihenfolge sind Fakten, keine zusätzliche Eligibility-Pflicht.
- Research/Purchase Eligibility: kein Effekt über separat kodierte Vorgängerkanten hinaus.
- Rank Progress und Kosten: kein Effekt.
- Fehlende, versteckte oder mehrfach zugeordnete Mitglieder sowie widersprüchliche Reihenfolge sind
  unresolved Evidence, keine erfundene Erwerbsregel.

### UNLOCK_REQUIREMENT (`unlock_requirement`)

- Richtung: Unlock-Bedingung → betroffenes Fahrzeug.
- Kardinalität: 0..n; mehrere verschiedene Tokens sind widersprüchlich.
- Pflicht: das Token ist eine Voraussetzung, seine Wahrheit kann extern unbeobachtbar sein.
- Research Eligibility: intern falsch ist unsatisfied; extern nicht prüfbar ist unresolved.
- Purchase Eligibility: keine zusätzliche Regel belegt.
- Rank Progress: ungeklärte externe Ziele werden nicht still als qualifiziert angenommen.
- Kosten: kein numerischer Kantenpreis; externe Erwerbskosten sind unbekannt.

### RANK_REQUIREMENT (`rank_requirement`)

- Richtung: Rang-Gate → jedes Fahrzeug des Folgerangs.
- Kardinalität: ein Gate zu 0..n Folgerang-Fahrzeugen.
- Pflicht: positive `requiredVehicles` sperren den Folgerang.
- Research Eligibility: erforderliche qualifizierende Anzahl muss erreicht sein.
- Purchase Eligibility: keine zusätzliche Regel über die Quellanzahl hinaus belegt.
- Rank Progress: Owned, Reserve, Start-Closure und Pflichtpfad können bei passendem Baum/Rang zählen.
- Kosten: keine; Kandidatenauswahl ist nicht Teil der Evaluation.

`EDGE_SEMANTICS` ist der ausführbare Spiegel dieses Abschnitts. Änderungen müssen Code, Spec und Tests
gemeinsam aktualisieren.

## Rule-Evaluation-Vertrag

Eingabe: `ResearchGraph`, Ziel-ID, `PlayerProgress`, `SolveOptions`, optional Start-ID und explizit
angenommene externe Unlock-Tokens.

Jede Ausgabe enthält zwingend:

- `rule_id`
- `status`: `satisfied | unsatisfied | not_applicable | unresolved`
- deterministisch sortierte `affected_node_ids`
- JSON-native, deterministische `evidence`
- technische `explanation`
- deterministisch sortierte `source_edge_ids`
- `blocking`

Regeln:

- `TARGET_VISIBILITY`
- `START_TREE_COMPATIBILITY`
- `PREDECESSOR_REQUIREMENTS`
- `FOLDER_MEMBERSHIP`
- `UNLOCK_REQUIREMENT`
- `RANK_REQUIREMENT_<sourceRank>` oder `RANK_REQUIREMENT` bei keiner positiven Schranke

Mehrfachvorgänger oder Zyklen ergeben unresolved mit allen beteiligten Kanten. Es ist verboten, eine
Kante still auszuwählen.

Unlockklassifikationen sind `internally_resolvable`, `fulfilled_by_progress`,
`external_assumed_satisfied`, `external_not_checkable`, `unknown` und `contradictory`. Nur ein
expliziter `PlayerProgress.fulfilled_unlocks`-Eintrag, ein bereits erfülltes Fahrzeug im
Resolution-Vertrag oder eine ausdrückliche Aufruferannahme darf einen externen Token satisfied setzen.

Rank-Evidence enthält required count, qualifizierende vorhandene IDs, missing count, Kandidaten,
ausgeschlossene Kandidaten mit Grund und immer `selectionPerformed: false`.

## Verfeinerte Diagnostik

Zusätzlich zu Gesamtwerten enthält die Diagnostik:

- Roots und Leaves je Knotentyp
- isolierte Knoten gesamt und je Knotentyp
- Komponenten je Nation, Fahrzeugart, Knotentyp und Fahrzeugklasse
- Komponenten ohne regulären Vehicle-Root
- Komponenten ausschließlich mit Sonderfahrzeugen
- diagnostische Kategorie `expected`, `attention` oder `invalid`

Komponentenstatistiken zählen schwach zusammenhängende Komponenten, die mindestens einen passenden
Knoten enthalten. Ein reguläres Fahrzeug ist weder Premium noch `special`, hiddenResearch oder
reqUnlock. Reserve bleibt eine eigene Flag-Aufschlüsselung und ist nicht automatisch ein Sonderfall.
Ein regulärer Vehicle-Root besitzt keine eingehende predecessor-Kante; strukturelle Folder-/Rank-Kanten
ändern diese Definition nicht.

- Getrennte Komponenten sind wegen Nationen, Fahrzeugarten und Strukturelementen grundsätzlich expected.
- Sonderfall-only-Komponenten sind expected und keine pauschalen Fehler.
- isolierte Knoten und Komponenten ohne regulären Root sind attention und brauchen Kontextprüfung.
- Zyklen sind invalid; null Zyklen ist expected.

## Semantik-Mirror

Alle 2.232 Sample-Ziele werden genau einer Kategorie zugeordnet:

- `exact_match`: Legacy-Direct-Requirements stimmen mit Graph Evaluation überein.
- `unresolved_expected`: mindestens eine relevante Regel ist ehrlich unresolved.
- `mismatch`: eindeutige Ergebnisse weichen ab; jeder Fall lässt das Gate fehlschlagen.
- `unsupported`: der Default-Legacyvertrag erzeugt kein vergleichbares Ergebnis.

Unresolved darf niemals in exact_match eingehen. Die 49 Sonderfälle werden zusätzlich einzeln mit
Flags, Status, Blocker und benötigten Quelldaten dokumentiert.

## Prerequisite-Resolution-Vertrag

Rule Evaluation und Prerequisite Resolution sind verschiedene Verträge. Evaluation entscheidet den
Status einer einzelnen Regel. Resolution darf aus eindeutig belegten Regeln eine notwendige
Fahrzeugmenge ableiten, aber keine RP-, GE-, SL- oder Eurokosten berechnen.

Eingabe:

- `ResearchGraph`
- Ziel-ID
- optional Start-ID
- `PlayerProgress`, einschließlich expliziter `fulfilled_unlocks`
- `SolveOptions`, einschließlich ausdrücklicher externer Unlock-Annahme
- optional eine getrennte Rank-Compatibility-Strategie

Das Ergebnis enthält mindestens:

- `target_vehicle_id`
- `start_vehicle_id`
- deterministische `required_vehicle_ids` und `satisfied_vehicle_ids`
- deterministische `blocking_rule_results` und `unresolved_rule_results`
- `rank_requirements`, `folder_requirements` und `unlock_requirements`
- `resolution_status`
- JSON-native Evidence
- deterministischen nummerierten Explanation Trace
- Kennzeichnung des Compatibility Mode

Zulässige Statuswerte:

- `resolved`: vollständige Voraussetzungsliste ist eindeutig.
- `blocked`: eine eindeutige Eingabe-/Eligibility-Regel ist nicht erfüllt.
- `unresolved`: mindestens eine notwendige fachliche Entscheidung ist nicht belegt.
- `unsupported`: Graph oder Compatibility-Vertrag können keinen belastbaren Vergleich erzeugen.

Bei gleichzeitigen Befunden gilt `unsupported` vor `blocked` vor `unresolved` vor `resolved`.

### Vorgänger

Eine eindeutige Closure wird vollständig aufgelöst. Owned-Fahrzeuge und Start A implizieren ihre
Closure. `include_start_vehicle` entfernt nur A selbst aus der erfüllten Menge und ergänzt A als
required. Teil-RP ist kein Besitz. Mehrfachvorgänger und Zyklen bleiben unresolved; eine stille
Kantenauswahl ist verboten.

### Folder

Resolution unterscheidet `membership_only`, `required_member` und `satisfied_member`. Nur eine separat
belegte Vorgängerkante kann ein Folder-Mitglied required machen. Fehlende, versteckte, mehrfach
zugeordnete oder widersprüchlich sortierte noch offene Mitglieder bleiben unresolved. Für ein bereits
erfülltes Mitglied bleibt die Quellenanomalie Evidence, öffnet seine Eligibility aber nicht erneut.

### Unlock

Eine interne Fahrzeugreferenz ergänzt ihre eindeutige fehlende Closure. Ein explizit in
`PlayerProgress.fulfilled_unlocks` enthaltenes Token ist `fulfilled_by_progress`. Ein externer Token
ist nur mit genau dieser Evidenz oder `assume_external_unlocks=True` erfüllt. Ohne Evidenz bleibt er
unresolved. Owned beziehungsweise Start A beweisen die bereits überwundene Unlock-Bedingung des
erfüllten Fahrzeugs. Unlocks dürfen nicht als normale Vorgängerkanten rekonstruiert werden.

### Rang

Rank Resolution nennt Required Count, bereits erfüllte Zahl, Missing Count, zulässige Kandidaten und
Ausschlussgründe. Ohne Auswahlstrategie bleibt eine notwendige Kombination unresolved. Die optionale
`LegacyRankCompatibilityStrategy` darf ausschließlich in den vergleichsbasierten Modi Shadow und
Graph Experimental die bestehende deterministische,
kostenbewusste Rank-Auswahl delegieren. Das Ergebnis muss `graphCostCalculationPerformed=false`,
`costValuesEmitted=false`, den aktivierten `legacyCompatibilityModeEnabled` und den tatsächlichen
`legacyCompatibilitySelectionPerformed`-Status sowie
`optimizerSelectionPerformed=false` ausweisen und darf nicht als zukünftige Optimizer-Semantik
dokumentiert werden.

## Resolution Shadow Mode

Der produktive `ResearchSolver` bleibt unverändert und wird separat ausgeführt. Vergleiche verwenden:

- `exact_match`: identische geordnete Voraussetzungsliste.
- `equivalent_match`: identische Fahrzeugmenge bei anderer Reihenfolge oder Repräsentation.
- `unresolved_expected`: Graph bewahrt eine fachlich offene notwendige Regel.
- `unsupported`: keine gemeinsame belastbare Ergebnisrepräsentation.
- `mismatch`: beide Ergebnisse sind eindeutig, aber fachlich verschieden.

Equivalent ist nur bei Mengengleichheit zulässig. Unresolved und unsupported sind weder Match noch
Mismatch. Jeder Mismatch ist ein Gate-Fehler. Abweichungsdiagnostik enthält Ziel, Start, vollständiges
Progress-Szenario, beide Fahrzeuglisten, beide Mengendifferenzen, abweichende Regeln, Evidence und
Explanation Trace.

Die Sample-Matrix umfasst 1.977 bestehende reguläre Fälle und 13 repräsentative Progress-Szenarien.
Die 49 Sonderfälle erhalten zusätzlich eine deterministische Accuracy-3-/Accuracy-4-Tabelle. Explizite
Hidden- oder Unlock-Evidenz darf Fälle lösen; Folder- oder Mehrfachvorgänger-Unklarheit darf dadurch
nicht kaschiert werden.

## Graph-Cost-Vertrag

Cost Calculation ist eine dritte, von Evaluation und Resolution getrennte Schicht. Eingabe ist ein
bereits fertiges `PrerequisiteResolution` zusammen mit derselben `VehicleDatabase`, `PlayerProgress`
und `SolveOptions`. Die Cost Engine darf weder Required-IDs ergänzen noch Rank-Kandidaten auswählen.

Das Ergebnis enthält mindestens:

- Ziel, Start, übernommenen `resolution_status` und eigenen `cost_status`
- deterministische VehicleCostLines
- vollständige RP-, GE- und SL-Summen oder ausdrücklich `null`
- vorhandene GE und Ergebnis nach deren Abzug
- Convertible RP und Shortfall
- Rabatt, RP je GE, Warnungen, Evidence und Explanation Trace
- `incomplete_reason_codes` sowie getrennte bekannte Teilsummen

Statusregeln:

- `resolved` → `complete`; vollständige Summen sind zulässig.
- `unresolved` → `partial`; nur bekannte Zeilen sind zulässig, vollständige Summen bleiben `null`.
- `blocked` oder `unsupported` → `unavailable`; es werden weder Zeilen noch Summen ausgegeben.
- Ungültige Kosten- oder Fortschrittsdaten → `unavailable`, unabhängig vom Resolution-Status.

Required- und satisfied-Mengen müssen disjunkt sein. Nur Required-IDs werden bepreist. Nullwerte,
Reserve, Hidden und reqUnlock bleiben als Evidence sichtbar; externe Erwerbskosten werden nicht
erfunden. Der numerische Vertrag steht in [GE Calculation](GE_CALCULATION_SPEC.md).

## Cost Shadow Mode

Der produktive `ResearchSolver` bleibt unverändert. Der Cost-Vergleich prüft mindestens Required-Set,
Rest-RP, individuell gerundete GE und rabattierte SL pro Fahrzeug, alle Summen, vorhandene GE und
Convertible-RP-Shortfall.

- `exact_match`: geordnete Zeilen und alle geprüften Werte sind identisch.
- `equivalent_match`: Kosten je Fahrzeug und Summen sind identisch; nur Darstellung/Reihenfolge
  unterscheidet sich.
- `unresolved_expected`: Graph darf nur partielle Kosten ausweisen.
- `unsupported`: keine gemeinsame belastbare Kostenrepräsentation.
- `mismatch`: beide Ergebnisse sind vollständig und fachlich verschieden.

Equivalent darf keine numerische Differenz verbergen. Jeder definitive Mismatch ist ein CI-Fehler.
Mismatch-Diagnostik enthält Ziel, Start, Fortschrittsszenario, Resolution-/Cost-Status, beide
VehicleCostLine-Listen, Fahrzeugdifferenzen, RP-/GE-/SL-Differenzen, Rundungsabweichungen, Evidence und
Explanation Trace.

Die Sample-Matrix umfasst 1.977 reguläre Fälle plus 18 Cost-Szenarien. Die separate 49er-Matrix weist
vollständige, partielle und nicht verfügbare Sonderfallkosten aus. Folder-, Unlock- und
Mehrfachvorgänger-Heuristiken bleiben verboten.

## Graph Calculation Pipeline Contract

Die zentrale Pipeline akzeptiert `VehicleDatabase` oder `GraphDatabaseAdapter`, Ziel, optionalen
Start, `PlayerProgress` und `SolveOptions`. Sie delegiert in dieser Reihenfolge:

1. `GraphRuleEvaluator`
2. `GraphPrerequisiteResolver`
3. `GraphCostEngine`

Ausgabe sind alle drei Teilresultate, Pipeline-Status, Status-Metadaten, Input-Findings, Evidence,
ein zusammenhängender nummerierter Trace, Diagnostics und ein versionierter Fingerprint. Zulässige
Statuswerte sind:

- `complete`: alle Teilverträge vollständig und Legacy-vergleichbar.
- `partial`: mindestens eine notwendige Regel unresolved; Kosten bleiben partial.
- `blocked`: eine eindeutige Regel blockiert den Aufruf.
- `unavailable`: Dataminefehler oder aktuell nicht unterstützte Modellierung.
- `invalid_input`: der Aufruf verletzt die gemeinsame Input-Grenze.
- `internal_error`: unerwarteter Implementierungsfehler; niemals unresolved.

Jeder Status enthält Ursache, betroffene Rule IDs, `blocking`, `user_safe`,
`comparable_to_legacy`, Explanation und Evidence. Interne Roh-Exceptions sind kein fachliches
Ergebnis und werden nicht ausgegeben.

## Dual Engine Comparison Contract

`DualEngineRunner` führt den unveränderten `ResearchSolver` und die Graphpipeline getrennt aus. Der
Runner selbst wählt keine Benutzer-Ergebnisquelle. Verglichen werden:

- Required-Fahrzeuge und strukturierte Rank-Anforderungen
- Gesamt-, Fortschritts- und Rest-RP je Fahrzeug
- GE und SL je Fahrzeug
- Gesamt-RP, Gesamt-GE vor/nach vorhandenen GE und Gesamt-SL
- Convertible-RP-Shortfall
- Ergebnisstatus

Legacy besitzt keine strukturierten satisfied-, Folder-, Unlock- oder Rule-Evaluation-Felder. Diese
Felder müssen in `excluded_fields` mit Begründung stehen; eine Ableitung aus Graphwerten ist verboten.

Vergleichswerte sind `exact_match`, `equivalent_match`, `unresolved_expected`, `unsupported`,
`input_contract_difference`, `mismatch` und `internal_error`. Equivalent darf ausschließlich eine
Darstellungs- oder Reihenfolgenabweichung bei identischen Mengen und Zahlen sein. Mismatch und
Internal Error sind CI-Fehler. Input-Contract-Differenzen brauchen Rule ID, Contract-Regel und
Begründung und zählen nicht als Match.

## Experimental Execution Contract

`CalculationEngine` definiert exakt `legacy`, `shadow` und `graph_experimental`. Ohne explizite
Auswahl gilt `legacy`; Graph Experimental ist pro Prozess deaktiviert, nicht persistent und darf
nicht automatisch aus Readiness abgeleitet werden.

- `legacy`: nur Legacy ausführen und verwenden;
- `shadow`: beide ausführen, Legacy verwenden;
- `graph_experimental`: beide ausführen, Graph ausschließlich bei `complete` und `exact_match`
  durch den Graph→`SolveResult`-Adapter verwenden.

Alle anderen Graphstatus oder Vergleichskategorien verwenden ein vorhandenes Legacy-Ergebnis als
sichtbar diagnostizierten Fallback. Insbesondere besitzt `partial` keine verbindlichen Graphsummen.
Ist auch Legacy nicht darstellbar, lautet der Ausführungsstatus `unavailable`. Desktop und Browser
bleiben Legacy-only.

## Deterministic Fingerprint Contract

Versionen:

- `graph-pipeline-fingerprint-v1`
- `legacy-result-v1`
- `dual-engine-comparison-v1`
- `graph-shadow-report-v1`
- `calculation-execution-v1`
- `graph-experimental-report-v1`

Grundlage ist kanonisches JSON über fachliche Eingaben, Status und Ergebnisse. Dictionary-Schlüssel,
Sets und Rule IDs sind deterministisch sortiert. Zeitstempel, Dateipfade, Objektadressen und zufällige
Reihenfolgen sind ausgeschlossen. Der Fingerprint ist eine Regressions-ID, keine Signatur.

## Full Shadow und Readiness

Der maschinenlesbare Bericht zählt jede Berechnung in genau einer benannten Ebene: 1.977 reguläre,
18 Cost-, 13 Progress-, 15 Options-, 49 Sonderfall- und 18 Invalid-Input-Fälle. Options- und
Input-Validation-Coverage werden aus den ausführbaren Cases abgeleitet.

`ready_for_experimental_use` verlangt mindestens 0 Mismatches, 0 Internal Errors sowie vollständige
Options- und Input-Abdeckung. `ready_for_default_use` verlangt zusätzlich beschlossene
Contract-Differenzen, belegte Folder-/Unlock-Grenzen, Browser-/Python-Abstimmung, repräsentative reale
Referenzen und einen Rollback-Pfad. Der aktuelle Stand erlaubt deshalb Shadow und ausdrücklich
aktiviertes CLI Graph Experimental, aber keine Default-Umschaltung.

## Accuracy Confidence Contract

Die unabhängige Confidence-Schicht konsumiert `ResearchGraph` und
`GraphCalculationPipeline`, definiert aber keine neue Graphregel. Ihr versionierter Vertrag umfasst:

- deterministische Baseline für Datamine, Validator, Graph, Pipeline und Fingerprints;
- statische Golden Inputs und Erwartungen für alle 44 realen Bäume;
- mindestens neun manuell geprüfte reale A→B-Referenzen;
- alle sechs Herkunftskategorien mit unabhängiger Stütze für `LEGACY_CONFIRMED`;
- deterministische metamorphische Eigenschaften;
- denselben Result-Fingerprint unter Python 3.10, 3.12 und 3.13;
- Browser-Fixture-Prüfung mit explizitem Status `fixture_validation_only`;
- Contract Decision Register, 14-Partial-Fall-Akte und Rollback-Plan.

Golden Fixtures sind read-only. Weder Legacy noch Graph dürfen sie im Test neu berechnen oder
überschreiben. Erwartete Required-IDs müssen aus der Datamine-Vorgänger-Closure stammen; erfüllter
Startabschnitt und gekaufte Fahrzeuge dürfen nicht erneut required sein. Mehrfachvorgänger-, Folder-
oder Unlock-Unklarheit bleibt `partial`/`unresolved`.

Readiness besitzt drei getrennte Werte:

- `ready_for_experimental_use`: Shadow sowie explizites CLI Graph Experimental mit Legacy-Fallback;
- `ready_for_release_candidate`: geprüfter Experimentalumfang mit null Mismatch/Internal Error, vollständig
  grünen Golden-/Metamorphic-Suites, voller Options-/Input-Abdeckung, dokumentierten Decisions,
  Browserstatus, Rollback und realen Referenzen;
- `ready_for_default_use`: Default-Umschaltung; bleibt in Accuracy 8 zwingend false.

Offene Decisions dürfen den Shadow-RC nur dann nicht blockieren, wenn sie ausdrücklich als
release-blocking dokumentiert sind. Für Default-Nutzung müssen sie angenommen oder verworfen sein.
Ein Confidence-Score ist nicht Teil des Vertrags.
