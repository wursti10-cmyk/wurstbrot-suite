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
| `folder` | Folder → Fahrzeug | geordnete Mitgliedschaft |
| `unlock` | Unlock → Fahrzeug | bewahrte externe Bedingung |
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
