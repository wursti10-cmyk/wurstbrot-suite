# AI Context

## Auftrag

KI-Agenten arbeiten faktenbasiert am Repository. Vor Änderungen sind relevante Implementierung,
Tests, `VERSION`, Changelog, Spezifikationen und offene PRs zu prüfen.

## Harte Regeln

1. Die aktuelle Release-Linie ist `0.9.0-beta`; offene PRs sind kein ausgelieferter Stand.
2. Keine erfundenen Gaijin-Regeln oder Datamine-Felder.
3. GE wird pro Fahrzeug aufgerundet.
4. Ein Fahrzeug ist nur mit `researched=True` und `purchased=True` im Solver „owned“.
5. A und B müssen denselben `countryId` und `branchId` besitzen.
6. Neue UI-Fachlogik gehört in den Core oder braucht Contract Tests.
7. Keine Accountdaten, proprietären Assets oder Datamine-Großdateien ungefragt committen.
8. Bei Solveränderungen Unit Tests und Regression ausführen.
9. Python und Browser müssen die gemeinsame Contract-Fixture und ihre Regressionen bestehen.
10. Jeder Datamine-Bug erhält zuerst eine synthetische Regression; neue Regeln werden in
    `specs/DATAMINE_SCHEMA.md` dokumentiert.
11. `error`-Findings blockieren Datenbankveröffentlichung. Warnungen und Infos dürfen nicht
    stillschweigend entfernt oder in Tests ausgeblendet werden.
12. Neue Rule-IDs zuerst im zentralen `RULE_DEFINITIONS`-Registry anlegen, dann negative und positive
    Matrixfälle ergänzen und die generierte Rule-Referenz aktualisieren. Coverage-Zahlen nie manuell
    setzen.
13. Der Health Score ist bewusst nicht implementiert. Ohne versionierte empirische Gewichte darf kein
    Prozentwert erfunden werden.
14. `ResearchGraph` ist eine parallele Architektur- und Diagnoseschicht, noch keine neue Research
    Engine. Keine Produktlogik ohne gesonderten fachlichen Sprint darauf umstellen.
15. Graphänderungen müssen Legacy- und Adapter-Solver vollständig spiegeln; `mirror_matches` muss
    `passed` entsprechen.
16. Folder-, Unlock- und Rank-Kanten sind strukturierte Fakten. Aus ihnen dürfen ohne Datamine- oder
    Spec-Nachweis keine neuen Kauf- oder Freischaltungsregeln abgeleitet werden.
17. Graph Rule Evaluation ist keine Solverablösung: Sie bewertet Voraussetzungen, erzeugt aber keine
    Kosten und wählt keine Rank-Kandidaten.
18. `unresolved` darf nie als bestanden gezählt werden. Mirror-Ausgaben müssen exact_match,
    unresolved_expected, mismatch und unsupported getrennt melden; jeder mismatch ist ein Fehler.
19. Mehrfachvorgänger niemals still auswählen. Alle betroffenen Kanten als unresolved Evidence melden.
20. Externe Unlocks nur bei ausdrücklichem `fulfilled_unlocks`-Eintrag oder expliziter Option
    satisfied setzen; nie aus Namen erraten.
21. Evaluation bewertet einzelne Regeln; Resolution erzeugt daraus eine Voraussetzungsliste. Diese
    Verträge nicht vermischen.
22. `GraphPrerequisiteResolver` bleibt Shadow Mode. Produktiven Legacy-Solver, Browser oder GUI nicht
    ohne eigenen Migrationssprint umstellen.
23. Rank-Auswahl ist nur in der ausdrücklich benannten `LegacyRankCompatibilityStrategy` zulässig.
    Sie ist kein Graph Optimizer und darf keine Kosten in den Resolution Contract schreiben.
24. Owned oder Start A beweisen ihre bereits überwundenen Folder-/Unlock-Voraussetzungen. Die
    Quellanomalie bleibt Evidence, darf aber nicht erneut als offene Eligibility gewertet werden.
25. `equivalent_match` verlangt exakt dieselbe Fahrzeugmenge. Unresolved und unsupported sind weder
    Match noch Mismatch; jeder echte Mismatch ist ein Fehler.

## Orientierung

- Datenmodell: `packages/core/wurstbrot_core/models.py`
- Loader/Graph: `database.py`
- paralleles Graphmodell/Diagnostik: `research_graph.py`
- Mirror-Adapter: `graph_adapter.py`
- Kantenvertrag: `graph_semantics.py`
- Regelauswertung: `graph_evaluation.py`
- Mirror-/Sonderfallanalyse: `graph_analysis.py`
- Voraussetzungsermittlung: `graph_resolution.py`
- Shadow-/Progress-/Sonderfallvergleich: `graph_resolution_analysis.py`
- Solver/Optimierer: `solver.py`
- Kosten: `economy.py`
- Converter: `apps/datamine-manager/wurstbrot_converter.py`
- strukturierter Validator: `packages/validator/wurstbrot_validator/validator.py`
- Rule-Registry: `packages/validator/wurstbrot_validator/rules.py`
- Rule-Verträge: `tests/validator_rule_matrix.py`
- vollständige Rule-Referenz: `docs/19_VALIDATOR_RULES.md`
- verbindliche Details: `specs/`

## Änderungsbericht

Am Ende Branch, Commit/PR, geänderte Verträge, ausgeführte Prüfungen und verbleibende Risiken nennen.
Unsicherheit ausdrücklich markieren statt plausibel klingende Fakten zu erfinden.

Bei Datamine-Arbeit zuerst Health Report und genaue `rule_id` nennen. `reqUnlock`,
`hiddenResearch`, Reserven und herausgefilterte Gruppenmitglieder sind bekannte Sonderfälle; sie sind
nicht ohne Datamine-Nachweis in harte Fehler umzuwandeln.
