# AI Context

## Auftrag

KI-Agenten arbeiten faktenbasiert am Repository. Vor Änderungen sind relevante Implementierung,
Tests, `VERSION`, Changelog, Spezifikationen und offene PRs zu prüfen.

## Harte Regeln

1. Die aktuelle Release-Linie ist `1.0.0-rc.2`; offene PRs sind kein ausgelieferter Stand.
2. Keine erfundenen Gaijin-Regeln oder Datamine-Felder.
3. GE wird pro Fahrzeug aufgerundet.
4. Ein Fahrzeug ist nur mit `researched=True`, vollständigen numerischen RP und `purchased=True` im
   Solver „owned“.
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
14. `ResearchGraph` bleibt eine experimentelle Rechenquelle. Ohne ausdrücklichen
    `graph_experimental`-Modus darf keine Produktlogik darauf umschalten; Default bleibt Legacy.
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
22. `GraphPrerequisiteResolver` darf nur durch Shadow oder explizites CLI Graph Experimental laufen.
    Browser und GUI bleiben Legacy; eine Standardumschaltung braucht einen eigenen Review.
23. Rank-Auswahl ist nur in der ausdrücklich benannten `LegacyRankCompatibilityStrategy` zulässig.
    Sie ist kein Graph Optimizer und darf keine Kosten in den Resolution Contract schreiben.
24. Owned oder Start A beweisen ihre bereits überwundenen Folder-/Unlock-Voraussetzungen. Die
    Quellanomalie bleibt Evidence, darf aber nicht erneut als offene Eligibility gewertet werden.
25. `equivalent_match` verlangt exakt dieselbe Fahrzeugmenge. Unresolved und unsupported sind weder
    Match noch Mismatch; jeder echte Mismatch ist ein Fehler.
26. Cost Calculation konsumiert Resolution, wählt aber niemals Voraussetzungen oder Rank-Kandidaten.
27. Vollständige Kosten sind nur bei `resolution_status=resolved` und `cost_status=complete` zulässig.
    Partial darf nie als vollständiger Bedarf dargestellt werden.
28. Legacy, Graph und Browser lehnen negative oder über Gesamt-RP liegende Fortschrittswerte ab;
    niemals klemmen oder still korrigieren.
29. GE immer pro Fahrzeug aufrunden. Der gemeinsame v1-SL-Rabattvertrag umfasst ausschließlich 0,
    30 oder 50 Prozent.
30. Cost Shadow vergleicht Zeilen und Summen. Equivalent darf keine numerische Abweichung verbergen;
    jeder definitive Mismatch ist ein Gate-Fehler.
31. `GraphCostEngine` darf Shadow und explizites CLI Graph Experimental bedienen. Legacy-Default,
    Browser, Desktop und GUI nicht umstellen.
32. `GraphCalculationPipeline` darf ausschließlich Evaluation, Resolution und Cost orchestrieren;
    keine fachliche Regel in den Orchestrator kopieren.
33. `internal_error` niemals als unresolved oder unsupported kaschieren. Roh-Exceptions nicht als
    fachliche Explanation exportieren.
34. Der Dual-Runner bleibt eine Vergleichskomponente und erzeugt beide Resultate. Nur der separate
    `CalculationEngine` darf bei explizitem `graph_experimental`, `complete` und `exact_match` das
    adaptierte Graphresultat freigeben; sonst gilt Legacy-Fallback.
35. `input_contract_difference` ist weder Match noch Fehler. Nach Accuracy 9 bezeichnet es bei den
    Validierungsfällen die strukturierte Graphfehler- gegenüber der Legacy-Fehlerrepräsentation,
    nicht mehr eine offene Produktsemantik. Jede Differenz braucht Rule ID, Contract-Regel und
    Begründung; Mismatch und Internal Error bleiben harte Gates.
36. Fingerprints nur aus kanonischen fachlichen Inhalten bilden. Keine Zeitstempel, Pfade,
    Objektadressen oder instabile Reihenfolgen aufnehmen.
37. `ready_for_default_use` nur bei vollständig belegten Kriterien setzen. Null Mismatches allein
    genügt nicht.
38. Golden Fixtures sind `manual_review_only` und unveränderlich. Niemals Erwartungen aus aktueller
    Legacy- oder Graphausgabe automatisch überschreiben.
39. `LEGACY_CONFIRMED` ist nur eine Herkunftsstütze; mindestens Datamine, Formel, manueller Review
    oder synthetischer Contract muss unabhängig belegen.
40. Confidence- und Baseline-Fingerprints schließen Zeitstempel, lokale Pfade, Plattform,
    Python-Executable und Objektadressen aus.
41. Browserstatus `fixture_validation_only` nie als Graph-Runtime-Parität oder erfolgreichen
    Engine-Vergleich ausgeben.
42. Die 14 Hidden-Folder-Fälle bleiben partial, bis konkrete neue Evidenz vorliegt. Keine Heuristik,
    um die Zahl kosmetisch zu senken.
43. `ready_for_experimental_use` gilt für Shadow sowie explizites CLI Graph Experimental mit
    Legacy-Fallback. `ready_for_default_use` bleibt false; Confidence darf nie automatisch umschalten.
44. Kein Confidence-Prozentwert erfinden. Berichte nennen belegte Zähler, Kriterien und Blocker.
45. Bis Version 1.0 ausschließlich Forschungsweg A → B und RP-/GE-/SL-Kosten bearbeiten. Keine neue
    Explain Engine, kein Dashboard, kein Project Intelligence, kein Optimizer-Ausbau und kein
    visueller Tech Tree.
46. Standardmodus ist exakt `legacy`. `partial`, `unavailable`, Internal Error, nicht exakter
    Vergleich oder Adapterverletzung dürfen nie als vollständiges Graph-Benutzerergebnis erscheinen.
47. `graph_experimental` mit deaktiviertem Prozess-Flag führt Graph nicht aus und verwendet sichtbar
    Legacy. Ein `invalid_input` darf dagegen niemals durch Legacy-Fallback wie eine erfolgreiche
    Berechnung erscheinen; Ergebnisquelle und Ergebnis bleiben in diesem Fall leer.
48. Die v1-Entscheidungen für Rabatt-Domain, ungültigen Progress und Forschungsstatus-/RP-Konflikt
    sind angenommen. Änderungen daran brauchen einen neuen fachlichen Entscheidungsreview.
49. Alle 14 Hidden-Folder-Ziele bleiben evidenzbasiert `partial`. Offizielle Gruppenquellen belegen
    keine Forschungs-, Kauf- oder Rangzählungsregel für diese versteckten Legacy-Folder.
50. Die Sample-Daten besitzen 31 externe `reqUnlock`-Tokens, aber keinen internen und keinen
    unbekannten Token. Nur exakter PlayerProgress oder die explizite Option erfüllt sie.
51. Die Sample-Daten besitzen keinen Mehrfachvorgänger. AND/OR-Semantik nicht aus synthetischen
    Kanten ableiten; sie bleiben unresolved.
52. Accuracy-10-Sollwerte nie aus aktueller Legacy- oder Graphausgabe regenerieren. Die 44 direkten
    Fälle verwenden statische Vorgängerkanten und Datamine-/Formelorakel; Fixture-Änderungen sind
    ausschließlich manueller Review.
53. `ready_for_rc_review` ist keine Default-Umschaltung. Legacy bleibt Standard,
    `ready_for_default_use=false`, und die 14 Hidden-Folder-Fälle bleiben partial.
54. Ein leerer optionaler Start ist eine dokumentierte Input-Repräsentationsdifferenz: Legacy
    behandelt ihn wie `None`, Graph lehnt ihn ab. Graph Experimental darf das Legacy-Ergebnis dafür
    nicht als gültigen Fallback anzeigen.

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
- Shadow-Kostenvertrag: `graph_cost.py`
- Cost-Matrizen und Abweichungsdiagnostik: `graph_cost_analysis.py`
- Pipeline, Input-Grenze und Fingerprint: `graph_pipeline.py`
- vollständiger Legacy-/Graph-Vergleich: `dual_engine.py`
- Vollmatrix, Shadow Report und Readiness: `graph_shadow.py`
- Execution Modes, Result Adapter und Fallback: `engine_execution.py`
- Experimental-Matrix und A→B-Abnahmen: `experimental_switch_analysis.py`
- unabhängige Golden-/Metamorphic-/Confidence-Verträge: `accuracy_confidence.py`
- versionierte Referenzartefakte: `accuracy/`
- Confidence-Vertrag: `docs/28_ACCURACY_CONFIDENCE.md`
- 14-Partial-Fall-Akte: `docs/29_PARTIAL_FOLDER_RESEARCH.md`
- Accuracy-9-Kernreferenzen: `accuracy/golden/core_contract_2.57.1.67.json`
- Accuracy-9-Evidenzabschluss: `accuracy/research/core_contract_closure_2.57.1.67.json`
- experimenteller Switch- und Rollback-Plan: `docs/30_GRAPH_ROLLBACK_PLAN.md`
- Release-Hardening-Matrix und RC-Readiness: `docs/31_RELEASE_HARDENING.md`
- unveränderliche Accuracy-10-Direktfälle: `accuracy/acceptance/release_hardening_2.57.1.67.json`
- Release-Hardening-Auswertung: `release_hardening.py`
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
