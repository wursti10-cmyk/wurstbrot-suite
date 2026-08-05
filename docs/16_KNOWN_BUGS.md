# Known Bugs and Limitations

## Modellgrenzen

- 49 Ziele mit `hiddenResearch` oder `reqUnlock` werden von der breiten Regression übersprungen.
- Sonderfreischaltungen werden als Warnung beschrieben, aber nicht allgemein als zusätzliche Bedingung gelöst.
- Der Optimierer bricht nach 75.000 Zuständen ab.
- `convertible_rp_shortfall` ist Information; verfügbare Convertible RP verteilen die Fahrzeugzeilen nicht.
- Eurokosten und GE-Paketpreise werden nicht berechnet.
- Der Graph kann nur einen direkten Vorgänger pro Fahrzeug darstellen.
- Der Validator erkennt mehrere Vorgänger nur, wenn ein nicht schemakonformes Array vorliegt; das
  Schema selbst kann widersprüchliche Quellen nach der Normalisierung nicht mehr rekonstruieren.
- `SPECIAL_NON_REGULAR` kann Event-, Squadron- und andere Sonderfahrzeuge derzeit nicht getrennt
  klassifizieren, weil das normalisierte Schema nur das gemeinsame Boolean-Feld `special` bewahrt.
- Die Schwelle für `RANK_UNLOCK_UNREALISTIC` ist eine dokumentierte Diagnosegrenze von 20 und keine
  behauptete War-Thunder-Spielregel. `RANK_UNLOCK_EXCEEDS_AVAILABLE` verwendet dagegen exakt die
  verfügbaren normalisierten Nicht-Premium-/Nicht-Spezialfahrzeuge.
- Der Browser bietet noch keine komfortable Mehrfachauswahl beliebiger bereits gekaufter Fahrzeuge;
  die Solver-API unterstützt diese Fortschrittsdaten bereits.

## Pflege

Ein Eintrag wird erst entfernt, wenn Fix und Regressionstest in `main` liegen. Offene PRs dürfen nur in
der Statusspalte erwähnt werden.
