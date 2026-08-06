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
  Analysestruktur und keine automatischen Validatorfehler.
- Der Graph Resolver ist nur in Shadow und im ausdrücklich aktivierten CLI-Modus
  `graph_experimental` erreichbar. Standard-CLI und alle Oberflächen verwenden Legacy.
- Die `LegacyRankCompatibilityStrategy` delegiert vorübergehend an die private bestehende
  Rangwahlmethode. Sie ist absichtlich kein eigenständiger Optimizervertrag.
- Die Graph-Cost-Engine läuft in Shadow oder im ausdrücklich aktivierten CLI-Experimentalmodus. Sie
  berechnet keine GE-Pakete, Europreise, Crewkosten oder Sale-Empfehlungen und verteilt vorhandene GE
  nicht auf Fahrzeugzeilen.
- Bei partiellen Kosten werden vorhandene GE und Convertible-RP-Shortfall bewusst nicht angewandt,
  weil unbekannte Voraussetzungen die vollständige Summe verändern können.
- Der Graph-Cost-Contract akzeptiert nur 0/30/50 Prozent SL-Rabatt; Legacy akzeptiert historisch
  0 bis 100 Prozent. Diese Eingabegrenze wird erst bei einer späteren produktiven Migration vereinigt.
- `researched=True` ohne passende numerische `researched_rp` bedeutet im Graph-Contract vollständig
  erforscht. Legacy berücksichtigt für nicht gekaufte Fahrzeuge derzeit nur die numerischen RP. Ein
  synthetischer Test hält diese bekannte Divergenz sichtbar; die reale Shadow-Matrix verwendet
  konsistente Status- und RP-Werte.
- Die Sample-Datenbank enthält kein reguläres Fahrzeug mit positivem RP und 0 SL. Die Null-SL-Regel
  ist deshalb synthetisch sowie mit einem Reservefahrzeug belegt, aber nicht breit realdatenvalidiert.
- Die Python-CLI kann ein Graphresultat ausdrücklich experimentell konsumieren, aber nur bei
  `pipeline_status=complete` und `comparison_status=exact_match`. Desktop, GUI und Browser besitzen
  weiterhin keine Graphintegration; insbesondere existiert keine Browser-Graphpipeline.
- Legacy stellt satisfied-Fahrzeuge, Folder-, Unlock- und Rule-Evaluation-Ergebnisse nicht
  strukturiert bereit. Diese Felder bleiben im Dual-Vergleich mit Begründung ausgeschlossen.
- 20 Accuracy-6-Aufrufe sind bewusste Input-Contract-Differenzen: 18 Validierungsfälle und zwei
  zusätzliche Legacy-Rabatte. Sie sind weder Match noch Mismatch und brauchen vor einer Umschaltung
  eine ausdrückliche Contract-Entscheidung.
- Fingerprints erkennen kanonische fachliche Änderungen, sind aber keine kryptografische Signatur
  oder Herkunftsbestätigung.
- Der Browser-Shadow-Harness prüft nur kanonische Golden Fixtures. Eine ausführbare Browser-
  Graphpipeline und echte Python-/Browser-Runtime-Parität existieren weiterhin nicht.
- Drei Produktsemantik-Entscheidungen sind deferred und ausdrücklich release-blocking: Rabatt-Domain,
  ungültiger Fortschritt und `researched=True`/RP-Konflikt.
- Die Accuracy-Baseline gilt nur für `2.57.1.67`. Eine neue Datamine braucht eine neue, geprüfte
  Baseline und darf die bestehende Datei nicht still überschreiben.
- Ein Confidence-Prozentwert ist absichtlich nicht definiert; die aktuelle Evidenz wird als Zähler,
  Herkunft und Readiness-Kriterien dargestellt.
- `graph_experimental` ist kein Default und vor 1.0 nicht empfohlen. Die Aktivierung gilt nur für
  den aktuellen CLI-Aufruf; es gibt weder gespeicherte Aktivierung noch automatische Umschaltung.
- In Accuracy 8 verwenden 96 von 2.090 Experimental-Requests Legacy-Fallback und sechs liefern kein
  darstellbares Ergebnis. Diese sechs sind keine stillen Erfolge; Quelle und Status bleiben im
  Report sichtbar.

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
- Die Accuracy-4-Vollmatrix löst 1.926 von 1.990 Vergleichen exakt, bewahrt 63 als unresolved und
  klassifiziert einen Hidden-Default-Fall als unsupported; mismatch bleibt 0.
- Mit expliziter Hidden-/Unlock-Evidenz werden 35 der 49 bekannten Sonderfälle aufgelöst. Vierzehn
  Hidden-Ziele in vier Folder-Familien bleiben wegen versteckter Mitgliedschaft beziehungsweise
  Folder-Reihenfolge unresolved.
- Die Accuracy-5-Cost-Matrix liefert 1.932 vollständige und 63 partielle Ergebnisse bei 0 Mismatches.
  Die separate Sonderfallmatrix enthält 35 vollständige und 14 partielle Kostenfälle; die 14
  Hidden-Folder-Ziele erhalten keine erfundene vollständige Summe.
- Die Accuracy-6-Vollmatrix enthält 2.090 getrennt gezählte Aufrufe: 1.988 exact, 80 unresolved,
  2 unsupported, 20 Input-Contract-Differenzen, 0 mismatch und 0 internal error. Experimenteller
  Shadow-Betrieb ist freigegeben; Default-Nutzung bleibt wegen der dokumentierten Blocker false.
- Accuracy 7 klassifiziert alle 14 Partial-Ziele in vier Hidden-Folder-Ursachengruppen. Dataminewerte
  und Reihenfolge sind bekannt; Erwerbs-, Kauf- und Rangzählungssemantik fehlen weiterhin. Die
  vollständige Evidenzanforderung steht in [Partial Folder Research](29_PARTIAL_FOLDER_RESEARCH.md).
- Accuracy 8 ändert diese Semantik nicht: 35 Sonderfälle verwenden vollständige Graph-Ergebnisse,
  14 zeigen `partial` und verwenden Legacy-Fallback. Die neun realen A→B-Abnahmen verwenden Graph
  vollständig; Full Matrix und Abnahmen enthalten 0 Mismatches und 0 Internal Errors.

## Pflege

Ein Eintrag wird erst entfernt, wenn Fix und Regressionstest in `main` liegen. Offene PRs dürfen nur in
der Statusspalte erwähnt werden.
