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

Unlockklassifikationen sind `internally_resolvable`, `external_assumed_satisfied`,
`external_not_checkable`, `unknown` und `contradictory`. Nur eine explizite Aufruferannahme darf einen
externen Token satisfied setzen.

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
