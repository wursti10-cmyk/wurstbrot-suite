# Datamine Database Schema

Status: Schema-Version 1, erzeugt durch den Converter.

## Wurzel

| Feld | Typ | Bedeutung |
|---|---|---|
| `schemaVersion` | Integer | derzeit exakt `1` |
| `converter` | Objekt | Name und Converter-Version |
| `gameVersion` | String | Inhalt von `version.txt` oder `unbekannt` |
| `generatedAt` | ISO-8601 String | UTC-Erzeugungszeit |
| `economy.rpPerGE` | positiver Integer | RP je GE |
| `vehicles` | Array | reguläre normalisierte Fahrzeuge |
| `predecessors` | Objekt | ID auf Vorgänger-ID oder `null` |
| `groups` | Objekt | Gruppen-ID auf geordnete Fahrzeug-IDs |
| `rankUnlock` | Objekt | Land → Fahrzeugart → Rang → erforderliche Käufe |
| `sourceFiles` | Objekt | Pfad, Größe und SHA-256 je Quelldatei |

## Vehicle

Pflicht für den Core sind `id`, `countryId`, `branchId`, `rank`; Kostenfelder fallen auf 0 zurück.
Der Converter erzeugt zusätzlich:

```text
name, country, branch, rp, sl, gePurchase,
crewTrainSL, expertCrewSL, aceCrewGE,
column, order, premium, special, reserve, zeroRP,
hiddenResearch, reqUnlock, unlockDescription,
rankPosXY, fakeReqUnitPosXY, group, groupIndex
```

## Kompatibilität

Leser müssen unbekannte additive Felder ignorieren. Brechende Umbenennungen, Typänderungen oder eine
andere Semantik erfordern eine neue `schemaVersion`. IDs sind opaque Strings und dürfen nicht aus
Anzeigenamen rekonstruiert werden.

## Health Report

Der strukturierte Report heißt `WT_Health_<gameVersion>.json` und hat Schema-Version 2. Das
maschinenlesbare JSON Schema liegt in [`HEALTH_REPORT_SCHEMA.json`](HEALTH_REPORT_SCHEMA.json).
Pflichtfelder:

```text
schemaVersion, gameVersion, generatedAt, passed, validatorVersion, validationDuration,
findingsByRule, findingsBySeverity, findingsByCategory,
vehicleStatistics, graphStatistics, folderStatistics,
implementedRules, testedRules, coverage, findings, ignoredRules,
healthScore, healthScoreStatus
```

`counts` enthält `error`, `warning` und `info`. `passed` ist genau dann wahr, wenn `error` null ist.
`graphStatistics` enthält mindestens Fahrzeug-, Kanten-, Wurzel-, Zyklus- und Fehlvorgängerzahl sowie
die maximale beobachtete Pfadtiefe. Der gleichnamige `.txt`-Report ist eine kompakte menschliche
Zusammenfassung. `WT_Validation_<gameVersion>.json` bleibt als Legacy-Export erhalten und verweist mit
`healthReport` auf den neuen Bericht.

Die V1-Felder `counts`, `countsByRule`, `vehicleCount`, `countryCount`, `treeCount` und `groupCount`
bleiben in V2 als additive Kompatibilitätsaliase erhalten. `findingsBy*` sind kompakte Zählmaps; die
vollständigen Befunde stehen ausschließlich in `findings`, damit der Report sie nicht mehrfach
dupliziert. `validationDuration` ist die monotonic gemessene Laufzeit in Millisekunden und darf sich
zwischen Läufen unterscheiden.

`implementedRules` stammt aus dem ausführbaren Rule-Registry. `testedRules` wird aus der ausführbaren
Positiv-/Negativ-Matrix entdeckt. `coverage` ist reproduzierbar definiert als
`100 * |testedRules ∩ implementedRules| / |implementedRules|`, auf zwei Dezimalstellen gerundet. Eine
fehlende Regel kann daher nicht durch eine manuell gepflegte Gesamtzahl verdeckt werden.

## Deterministische Findings

Findings werden aufsteigend nach folgender Schlüsselfolge sortiert:

1. Severity mit fester Ordnung `error`, `warning`, `info`
2. `rule_id`
3. `entity_type`
4. `entity_id` oder leerer String
5. `message`

Nur für vollständig identische Primärschlüssel folgen `source_field` und kanonisches `details` als
stabile Tie-Breaker. `generatedAt` und `validationDuration` sind erwartungsgemäß laufabhängig.

## Health Score

V2 berechnet bewusst keinen Score. `healthScore` ist `null` und `healthScoreStatus` ist
`future_extension`. ERROR/WARNING/INFO sind nicht ohne fachliche Gewichte vergleichbar: Reserven,
externe Unlocks und Hidden-Legacy-Fahrzeuge sind absichtliche Infos; unbekannte Ordnerreferenzen können
bewusst herausgefilterte Sonderfahrzeuge sein. Eine Gewichtung würde deshalb derzeit Genauigkeit
vortäuschen. Ein zukünftiger Score benötigt versionierte, empirisch begründete Regelgewichte,
Normalisierung nach Datenbankgröße und Golden-Datamine-Vergleiche.

## Zukünftige Historie

Der Validator speichert noch keine Historie. Das vorbereitete Schema
[`HEALTH_HISTORY_SCHEMA.json`](HEALTH_HISTORY_SCHEMA.json) definiert nur den späteren Envelope mit
`history`, `previousVersion`, `currentVersion`, `createdAt`, `validatorVersion` und `gameVersion`.
Weder Converter noch CI schreiben derzeit eine History-Datei.

## Verbindliche Regeln und Severity

Die vollständige, aus dem Rule-Registry erzeugte Referenz mit Beschreibung, Severity, Begründung,
Beispiel und Beispielausgabe steht in
[`../docs/19_VALIDATOR_RULES.md`](../docs/19_VALIDATOR_RULES.md). Die folgende Tabelle bleibt die
kompakte Schemazusammenfassung.

| Rule-ID | Severity | Bedingung |
|---|---|---|
| `SCHEMA_MISSING_FIELD` | error | Pflichtfeld der Datenbankwurzel fehlt |
| `SCHEMA_INVALID_TYPE` | error | Wurzel-, Vorgänger-, Gruppen- oder Rangstruktur hat falschen Typ |
| `SCHEMA_INVALID_VERSION` | error | `schemaVersion` ist nicht exakt 1 |
| `GAME_VERSION_MISSING` | error | `gameVersion` fehlt oder ist leer |
| `GAME_VERSION_INVALID` | error | Version ist unbekannt oder keine gepunktete Spielversion |
| `ECONOMY_INVALID_RP_PER_GE` | error | `rpPerGE` ist kein positiver Integer |
| `VEHICLE_DUPLICATE_ID` | error | Fahrzeug-ID tritt mehrfach auf |
| `VEHICLE_MISSING_FIELD` | error | Pflichtfeld `id`, `name`, `countryId`, `branchId`, `rank`, `rp` oder `sl` fehlt |
| `VEHICLE_INVALID_FIELD_TYPE` | error | Fahrzeug- oder Rangfreischaltungsfeld hat falschen Typ |
| `RANK_INVALID` | error | Rang ist kein positiver Integer |
| `COST_NON_NUMERIC` | error | RP oder SL ist nicht ganzzahlig |
| `COST_NEGATIVE_RP`, `COST_NEGATIVE_SL` | error | Kosten sind negativ |
| `COST_ZERO_RP_WITH_SL`, `COST_ZERO_SL_WITH_RP` | warning | Nullkosten-Kombination ist auffällig |
| `GRAPH_MISSING_PREDECESSOR` | error | Vorgänger-ID fehlt im Fahrzeugbestand |
| `GRAPH_SELF_REFERENCE`, `GRAPH_CYCLE` | error | Selbstkante oder Zyklus |
| `GRAPH_CROSS_NATION`, `GRAPH_CROSS_BRANCH` | error | Kante wechselt Nation oder Fahrzeugart |
| `GRAPH_RANK_BACKWARDS` | error | Vorgänger hat höheren Rang |
| `GRAPH_UNREACHABLE` | warning | kein expliziter Vorgängereintrag; Fahrzeug wird als Wurzel behandelt |
| `GRAPH_CONFLICTING_PREDECESSORS` | error | nicht schemakonforme Mehrfachdefinition erkannt |
| `GROUP_UNKNOWN_VEHICLE` | warning | Ordner enthält gefilterte oder unbekannte ID |
| `GROUP_CONFLICTING_MEMBERSHIP` | error | Fahrzeug steht in mehreren Ordnern |
| `GROUP_SINGLE_VEHICLE` | info | Ordner hat nur ein Mitglied |
| `GROUP_INDEX_MISMATCH` | warning | `group`/`groupIndex` widerspricht der Ordnerliste |
| `GROUP_CROSS_TREE` | error | Ordner wechselt Nation oder Fahrzeugart |
| `RANK_UNLOCK_NEGATIVE` | error | Freischaltungszahl ist negativ |
| `RANK_UNLOCK_UNREALISTIC` | warning | Freischaltungszahl liegt über Diagnosegrenze 20 |
| `RANK_UNLOCK_EXCEEDS_AVAILABLE` | error | Zahl übersteigt Nicht-Premium-/Nicht-Spezialfahrzeuge des Rangs |
| `RANK_UNLOCK_MISSING` | warning | höherer Rang existiert, Anforderung fehlt oder ist null |
| `RANK_UNLOCK_ORDER_CONFLICT` | error | Rangschlüssel ist nicht numerisch |
| `LOCALIZATION_MISSING_NAME`, `LOCALIZATION_EMPTY` | warning | Namensfeld fehlt oder ist leer |
| `LOCALIZATION_INTERNAL_ID` | warning | Anzeigename entspricht interner ID |
| `LOCALIZATION_DUPLICATE_NAME` | info | sichtbarer Name ist im selben Baum mehrfach vorhanden |
| `SPECIAL_HIDDEN_RESEARCH`, `SPECIAL_EXTERNAL_UNLOCK`, `SPECIAL_RESERVE` | info | tolerierter Forschungs-Sonderfall |
| `SPECIAL_PREMIUM`, `SPECIAL_NON_REGULAR` | info | toleriertes Kauf-/Event-/Squadron-/Legacy-Fahrzeug |

### Abbruch und Unterdrückung

Der Converter schreibt bei Fehlern Diagnoseberichte, aber keine neue `WT_Database_*`-Datei. Die
Prüfung einer vorhandenen Datenbank liefert Exitcode 1. `ignoredRules` ist standardmäßig leer;
Unterdrückung verändert nie die Eingabedaten und muss im Report sowie im Review begründet werden.
