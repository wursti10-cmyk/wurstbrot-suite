# Research Graph

## Modell

Der normalisierte Graph ist eine Menge von Fahrzeugen und eine Map
`predecessors[vehicle_id] -> predecessor_id | null`. Damit besitzt jedes Fahrzeug höchstens einen
direkten Vorgänger; mehrere Nachfolger sind möglich. Der Graph wird pro Nation und Fahrzeugart
betrachtet.

Parallel dazu existiert das additive `ResearchGraph`: ein typisierter Multi-Edge-Graph mit Vehicle-,
Folder-, Unlock- und Rank-Knoten. Er trägt Architektur, Export, Diagnose, Rule Evaluation,
Prerequisite Resolution und Cost Calculation im Shadow sowie im ausdrücklich aktivierten
CLI-Experimentalmodus. Der Standard-Solververtrag bleibt das Schema-v1-Modell. Details stehen in
[Graph Engine Foundation](20_GRAPH_ENGINE_FOUNDATION.md).

## Pfadabschluss

`VehicleDatabase.closure(target)` läuft vom Ziel rückwärts bis zur Wurzel, erkennt Zyklen und gibt den
Pfad anschließend in Forschungsreihenfolge zurück. Das Ziel ist immer das letzte Element.

## Startfahrzeug A

Ein Startfahrzeug muss im selben `countryId` und `branchId` wie B liegen. A darf in einer anderen Linie
desselben Baums stehen. Sein eigener Vorgängerabschluss gilt als bereits überwunden. Standardmäßig wird
A selbst ebenfalls als vorhanden behandelt; mit `include_start_vehicle` kann A als Kostenzeile erscheinen.

## Besitz

Ein `VehicleProgress` gilt nur dann als `owned`, wenn `researched` und `purchased` wahr sind. Besitz
impliziert die Pflichtvorgänger dieses Fahrzeugs. Reservefahrzeuge werden für die Solverberechnung als
vorhanden behandelt.

## Rangschranken

Für jeden relevanten Rang vor dem Ziel liest der Solver die erforderliche Fahrzeugzahl aus
`rankUnlock`. Fehlen Fahrzeuge, sucht der Optimierer zusätzliche Kandidaten samt deren Vorgängern.

## Mirror-Pfad

`GraphDatabaseAdapter` stellt dem unveränderten `ResearchSolver` dieselben Reads bereit, löst
`closure()` aber über `predecessor`-Kanten. Die breite Python-Regression vergleicht das vollständige
Legacy- und Mirror-Ergebnis für alle 1.977 regulären Fälle. Mehrfachvorgänger bleiben im Graphmodell
darstellbar, werden vom Legacy-Adapter mangels belegter AND-/OR-Semantik jedoch abgelehnt.

## Rule Evaluation

Die getrennte Evaluationsschicht versteht die belegbare Semantik von `predecessor`, `folder_member`,
`unlock_requirement` und `rank_requirement`. Sie meldet je Regel satisfied, unsatisfied,
not_applicable oder unresolved samt Evidence und Edge-IDs. Sie berechnet keine Preise und wählt keine
Rank-Kandidaten. Der vollständige Vertrag steht in [Graph Rule Evaluation](22_GRAPH_RULE_EVALUATION.md).

Mehrfachvorgänger bleiben unresolved. Folder sind Mitgliedschaft und Reihenfolge, keine eigenständige
Erwerbsregel. Externe Unlocks bleiben getrennte Bedingungen. Rank Evaluation zählt und erklärt, ohne
einen günstigsten Pfad zu wählen.

## Prerequisite Resolution

Der additive `GraphPrerequisiteResolver` übersetzt Rule Results erstmals in eine deterministische
Voraussetzungsmenge. Er löst eindeutige Vorgängerketten und interne Unlock-Closures auf, unterscheidet
Folder-Mitgliedschaft von separaten Pflichten und beschreibt Rank-Lücken samt Kandidaten. Unbekannte
Mehrfachvorgänger-, Folder- und externe Unlock-Semantik bleibt unresolved.

Der Resolver läuft ausschließlich innerhalb von Shadow oder explizitem CLI Graph Experimental. Für
vollständige Vergleiche kann eine ausdrücklich benannte Legacy-Rank-Compatibility-Strategie dieselbe
bestehende Rangmenge wählen. Das ist weder neue Kostenlogik noch Optimizer-Semantik. Details und aktuelle Matrix stehen in
[Graph Prerequisite Resolution](23_GRAPH_PREREQUISITE_RESOLUTION.md).

## Graph Cost Calculation

`GraphCostEngine` verarbeitet ausschließlich das fertige `PrerequisiteResolution`-Ergebnis. Sie
bestimmt keine Vorgänger, Folderregeln, Unlocks oder Rank-Kandidaten. Vollständige Summen werden nur
bei `resolved` ausgegeben; `unresolved` liefert höchstens klar markierte Teilzeilen. `blocked` und
`unsupported` erzeugen keine Kosten. Details und aktuelle Matrix stehen in
[Graph Cost Engine](25_GRAPH_COST_ENGINE.md).

Der Cost-Shadow-Vergleich prüft die Legacy-Zeilen fahrzeugweise auf Rest-RP, individuell gerundete GE
und rabattierte SL sowie auf identische Summen. `CalculationEngine` darf vollständige, exakt gleiche
Kosten im ausdrücklich aktivierten CLI-Experimentalmodus in das bestehende `SolveResult`-Format
adaptieren. Jeder andere Fall bleibt Legacy-Fallback.
`invalid_input` ist davon ausgenommen und bleibt ohne Benutzerergebnis; unterschiedliche
Fehlerrepräsentationen dürfen keine erfolgreiche Berechnung erzeugen.

## Graph Calculation Pipeline

Accuracy 6 orchestriert Evaluation, Resolution und Cost über `GraphCalculationPipeline`. Der
Orchestrator besitzt keine eigene Folder-, Unlock-, Rank- oder Kostenregel. Er definiert nur die
gemeinsame Input-Grenze, Statuspropagation, Evidence, den zusammenhängenden Trace und den
versionierten Fingerprint.

`DualEngineRunner` führt Legacy und Graph parallel aus. Nicht strukturierte Legacy-Felder wie
satisfied, Folder und Unlock werden mit Grund ausgeschlossen statt geschätzt. Die 2.090-Fall-Matrix
meldet 1.988 exact, 80 unresolved expected, 2 unsupported, 20 Input-Contract-Differenzen sowie
0 Mismatches und 0 Internal Errors. Vollständiger Vertrag:
[Dual Engine Orchestration](27_DUAL_ENGINE_ORCHESTRATION.md).

## Experimental Execution

Accuracy 8 ergänzt keine Graphregel. Die separate Execution-Schicht definiert `legacy`, `shadow` und
`graph_experimental`; Default bleibt Legacy. Graph wird nur bei `complete` + `exact_match` als
Benutzerquelle verwendet. Partial, unavailable, Fehler oder Adapterverletzung führen zu sichtbarem
Legacy-Fallback. Input-Contract-Differenzen werden sichtbar abgelehnt und erzeugen kein
Benutzerergebnis. Desktop und Browser bleiben Legacy-only.

## Independent Confidence Layer

Accuracy 7 ändert das Graphmodell nicht. Eine getrennte Schicht führt die bestehende Pipeline gegen
60 unveränderliche Erwartungen aus: alle 44 realen Forschungsbäume, neun manuell geprüfte A→B-Fälle
und sieben isolierte Contracts. Erforderliche Fahrzeugmengen müssen weiterhin aus der versionierten
Vorgänger-Closure stammen; gekaufte Fahrzeuge und der erfüllte Startabschnitt dürfen nicht erneut in
`required_vehicle_ids` erscheinen.

Die 14 Hidden-Folder-Fälle bleiben bewusst partial und sind mit exakten Datamine-Feldern in der
[Partial-Folder-Akte](29_PARTIAL_FOLDER_RESEARCH.md) dokumentiert. Confidence-Ausgaben dürfen diese
Grenze weder durch Legacy-Vergleich noch durch eine Folder-Heuristik auflösen.
