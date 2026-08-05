# Core

Gemeinsame Datenmodelle und Berechnungslogik. `research_graph.py` enthält die additive typisierte
Graphabstraktion mit Diagnostik und deterministischem Debug-Export. `graph_adapter.py` spiegelt deren
Vorgänger-Closures in den unveränderten Legacy-Solver; sie ist noch keine neue Solverimplementierung.

`graph_semantics.py` definiert den ausführbaren Vertrag aller Kantentypen. `graph_evaluation.py`
bewertet Eligibility-Regeln ohne Kosten- oder Kandidatenauswahl. `graph_analysis.py` erzeugt die
vollständige Mirror-Klassifikation und die deterministische 49er Sonderfallmatrix.
