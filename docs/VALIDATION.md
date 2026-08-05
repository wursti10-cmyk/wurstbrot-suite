# Validierung

Der Converter verwendet den strukturierten Validator aus `packages/validator`. Verbindliche Regeln,
Severity und Health-Report-Schema stehen in [`../specs/DATAMINE_SCHEMA.md`](../specs/DATAMINE_SCHEMA.md);
die Datamine-Referenz enthält die kompakte Rule-ID-Übersicht.

`error` blockiert eine neue Datenbank. `warning` erlaubt Verarbeitung mit sichtbarer Diagnose.
`info` dokumentiert Sonderfälle und Statistiken. Der Legacy-Export `WT_Validation_*` bleibt erhalten.
