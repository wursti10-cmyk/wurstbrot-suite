# Known Bugs and Limitations

## Modellgrenzen

- 49 Ziele mit `hiddenResearch` oder `reqUnlock` werden von der breiten Regression übersprungen.
- Diese 49 Sonderfälle werden vom Validator sichtbar klassifiziert, aber ihre Freischaltbarkeit ist
  dadurch noch nicht rechnerisch bewiesen.
- Sonderfreischaltungen werden als Warnung beschrieben, aber nicht allgemein als zusätzliche Bedingung gelöst.
- Der Optimierer bricht nach 75.000 Zuständen ab.
- `convertible_rp_shortfall` ist Information; verfügbare Convertible RP verteilen die Fahrzeugzeilen nicht.
- Eurokosten und GE-Paketpreise werden nicht berechnet.
- Der Graph kann nur einen direkten Vorgänger pro Fahrzeug darstellen.
- Das additive `ResearchGraph` kann mehrere Vorgängerkanten darstellen; der Legacy-Adapter lehnt sie
  weiterhin ab, weil AND-/OR-Semantik noch nicht spezifiziert ist.
- Der Validator erkennt mehrere Vorgänger nur, wenn ein nicht schemakonformes Array vorliegt; das
  Schema selbst kann widersprüchliche Quellen nach der Normalisierung nicht mehr rekonstruieren.
- Ordnerreferenzen auf herausgefilterte Fahrzeuge sind nicht eindeutig von wirklich veralteten IDs zu
  unterscheiden. Deshalb bleibt `GROUP_UNKNOWN_VEHICLE` WARNING statt ERROR.
- `SPECIAL_NON_REGULAR` kann Event-, Squadron- und andere Sonderfahrzeuge derzeit nicht getrennt
  klassifizieren, weil das normalisierte Schema nur das gemeinsame Boolean-Feld `special` bewahrt.
- Event- und Squadron-Erwerbsregeln werden nicht aus `special` rekonstruiert. Premiumkauf, Legacy-
  Verfügbarkeit und externe `reqUnlock`-Bedingungen werden diagnostiziert, aber nicht gelöst.
- `WT_Validation_*` bleibt ein Legacy-Kompatibilitätsformat und enthält nicht alle V2-Statistiken; neue
  Integrationen müssen `WT_Health_*` lesen.
- Die Schwelle für `RANK_UNLOCK_UNREALISTIC` ist eine dokumentierte Diagnosegrenze von 20 und keine
  behauptete War-Thunder-Spielregel. `RANK_UNLOCK_EXCEEDS_AVAILABLE` verwendet dagegen exakt die
  verfügbaren normalisierten Nicht-Premium-/Nicht-Spezialfahrzeuge.
- Der Health Score ist absichtlich nicht implementiert, weil noch keine empirisch belegten Gewichte
  oder eine datenbankgrößenunabhängige Normalisierung existieren.
- Der Browser bietet noch keine komfortable Mehrfachauswahl beliebiger bereits gekaufter Fahrzeuge;
  die Solver-API unterstützt diese Fortschrittsdaten bereits.
- Graphdiagnostik zählt alle Kantentypen gemeinsam. Folder-, Unlock- und Rank-Kanten sind
  Analysestruktur und noch keine vom Solver ausführbaren Bedingungen.

## Klassifizierte offene Semantik

- 31 Sample-Ziele besitzen externe `reqUnlock`-Tokens ohne abbildbaren PlayerProgress-Zustand und
  bleiben in der Rule Evaluation unresolved.
- 18 Hidden-Ziele sind unter Default-Optionen eindeutig unsatisfied, ihre konkrete Erwerbs- und
  Verfügbarkeitssemantik bleibt außerhalb des normalen Solvers.
- 44 Ziele sind in der breiten Mirror Evaluation erwartbar unresolved: externe Unlocks oder Folder mit
  fehlenden beziehungsweise versteckten Mitgliedern. Sie werden nicht als exact_match kaschiert.
- Mehrfachvorgänger werden vollständig erkannt und unresolved gemeldet; AND-/OR-Semantik ist weiterhin
  nicht spezifiziert.
- Rank Evaluation nennt Kandidaten und Ausschlussgründe, entscheidet aber absichtlich keine Kombination.

## Pflege

Ein Eintrag wird erst entfernt, wenn Fix und Regressionstest in `main` liegen. Offene PRs dürfen nur in
der Statusspalte erwähnt werden.
