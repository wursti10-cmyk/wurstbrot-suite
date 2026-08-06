# Core

Gemeinsame Datenmodelle und Berechnungslogik. `research_graph.py` enthält die additive typisierte
Graphabstraktion mit Diagnostik und deterministischem Debug-Export. `graph_adapter.py` spiegelt deren
Vorgänger-Closures in den unveränderten Legacy-Solver; sie ist noch keine neue Solverimplementierung.

`graph_semantics.py` definiert den ausführbaren Vertrag aller Kantentypen. `graph_evaluation.py`
bewertet Eligibility-Regeln ohne Kosten- oder Kandidatenauswahl. `graph_analysis.py` erzeugt die
vollständige Mirror-Klassifikation und die deterministische 49er Sonderfallmatrix.

`graph_resolution.py` bestimmt parallel im Shadow Mode eindeutige Voraussetzungen.
`graph_resolution_analysis.py` vergleicht diese mit dem produktiven Legacy-Vertrag. Eine optionale
`LegacyRankCompatibilityStrategy` dient ausschließlich der vollständigen Mirror-Auswertung; sie ist
kein neuer Optimizer und schreibt keine Kosten in den Resolution Contract.

`graph_cost.py` bepreist ein fertiges Resolution-Ergebnis streng und deterministisch, ohne Fahrzeuge
auszuwählen. `graph_cost_analysis.py` vergleicht die Shadow-Kosten fahrzeugweise mit Legacy und
klassifiziert die 18 Cost-Szenarien sowie 49 Sonderfälle. Produktive Oberflächen importieren diese
Schicht nicht.

`graph_pipeline.py` orchestriert Evaluation, Resolution und Cost ohne Fachregeln zu duplizieren.
`dual_engine.py` vergleicht die vollständige Graphpipeline mit dem weiterhin produktiven Legacy-
Ergebnis. `graph_shadow.py` erzeugt Options-, Input-, Sonderfall- und Vollmatrizen sowie die
versionierten `Graph_Shadow_*`-Berichte. Keine dieser Schichten ist in GUI oder Browser eingebunden.
