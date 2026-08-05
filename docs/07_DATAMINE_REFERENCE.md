# Datamine Reference

## Eingaben

| Schlüssel | Datei | Pflicht | Verwendung |
|---|---|---:|---|
| `shop` | `shop.blkx` | ja | Forschungsbaum, Reihenfolge, Gruppen, Freischaltungen |
| `wpcost` | `wpcost.blkx` | ja | RP-, SL-, GE- und Crewkosten |
| `rank` | `rank.blkx` | ja | Käufe zum Öffnen des nächsten Rangs |
| `warpoints` | `warpoints.blkx` | ja | Umrechnungsrate `playerExpToCountryFor1Gold` |
| `unlocks` | `unlocks.blkx` | ja | Beschreibung spezieller Freischaltungen |
| `units` | `units.csv` | ja | deutsche bzw. englische Anzeigenamen |
| `version` | `version.txt` | nein | Spielversion |
| weitere | `unittags.blkx`, CSVs | nein | werden gefunden und im Manifest erfasst |

## Dateisuche

Der Converter durchsucht rekursiv. Duplikatsuffixe wie `shop(3).blkx` werden normalisiert. Bevorzugt
werden bekannte Datamine-Pfade, exakte Dateinamen und flachere Treffer. Fehlt eine Pflichtdatei,
bricht die Konvertierung mit `ConversionError` ab.

## Normalisierung

- unterstützt: `army`, `aviation`, `helicopters`, `ships`, `boats`
- Premium- und Spezialfahrzeuge werden aus der regulären Calculator-Datenbank entfernt.
- Ungültige Vorgänger auf entfernte Fahrzeuge werden abgeschnitten und als `cutReferences` gemeldet.
- Gruppen werden in ihrer Reihenfolge verkettet.
- Quelldateien erhalten relativen Pfad, Größe und SHA-256 im Manifest.

## Parsergrenze

BLKX muss als JSON lesbar sein. Binäre VROMFS-Dateien werden nicht selbst entpackt. Änderungen an
Gaijins Strukturen müssen zuerst mit einer kleinen Fixture und danach mit einer realen Datamine geprüft
werden.

## Strukturierte Validierung

Der Validator arbeitet auf der vollständig normalisierten Datenbank, bevor sie veröffentlicht wird.
Jeder Befund enthält `rule_id`, `severity`, `message`, `entity_type`, `details` und – soweit bekannt –
`entity_id`, `source_field` sowie eine optionale `suggestion`.

- `error`: Ausgabe darf nicht als Calculator-Datenbank veröffentlicht oder verwendet werden; der
  Converter schreibt Diagnoseberichte und bricht mit Exitcode 1 ab.
- `warning`: auffällige Daten, die Verarbeitung bleibt zulässig.
- `info`: explizite Sonderfälle oder Statistiken ohne Abbruch.

Findings werden deterministisch nach Severity (`error`, `warning`, `info`), Rule-ID, Entity Type,
Entity ID und Message sortiert. Feld und kanonische Details brechen nur vollständige Gleichstände.
Regelunterdrückung ist nur über die Python-API erlaubt und erscheint immer in `ignoredRules`.

## Rule-IDs

| Bereich | Rule-IDs |
|---|---|
| Schema | `SCHEMA_MISSING_FIELD`, `SCHEMA_INVALID_TYPE`, `SCHEMA_INVALID_VERSION`, `GAME_VERSION_MISSING`, `GAME_VERSION_INVALID`, `ECONOMY_INVALID_RP_PER_GE` |
| Fahrzeug | `VEHICLE_DUPLICATE_ID`, `VEHICLE_MISSING_FIELD`, `VEHICLE_INVALID_FIELD_TYPE`, `RANK_INVALID` |
| Kosten | `COST_NON_NUMERIC`, `COST_NEGATIVE_RP`, `COST_NEGATIVE_SL`, `COST_ZERO_RP_WITH_SL`, `COST_ZERO_SL_WITH_RP` |
| Graph | `GRAPH_MISSING_PREDECESSOR`, `GRAPH_SELF_REFERENCE`, `GRAPH_CYCLE`, `GRAPH_CROSS_NATION`, `GRAPH_CROSS_BRANCH`, `GRAPH_RANK_BACKWARDS`, `GRAPH_UNREACHABLE`, `GRAPH_CONFLICTING_PREDECESSORS` |
| Ordner | `GROUP_UNKNOWN_VEHICLE`, `GROUP_CONFLICTING_MEMBERSHIP`, `GROUP_SINGLE_VEHICLE`, `GROUP_INDEX_MISMATCH`, `GROUP_CROSS_TREE` |
| Rang | `RANK_UNLOCK_NEGATIVE`, `RANK_UNLOCK_UNREALISTIC`, `RANK_UNLOCK_EXCEEDS_AVAILABLE`, `RANK_UNLOCK_MISSING`, `RANK_UNLOCK_ORDER_CONFLICT` |
| Namen | `LOCALIZATION_MISSING_NAME`, `LOCALIZATION_EMPTY`, `LOCALIZATION_INTERNAL_ID`, `LOCALIZATION_DUPLICATE_NAME` |
| Sonderfälle | `SPECIAL_HIDDEN_RESEARCH`, `SPECIAL_EXTERNAL_UNLOCK`, `SPECIAL_RESERVE`, `SPECIAL_PREMIUM`, `SPECIAL_NON_REGULAR` |

Die genaue Severity und Semantik jeder Regel ist in `specs/DATAMINE_SCHEMA.md` verbindlich. Die
vollständige Einzelreferenz mit Begründung und Ein-/Ausgabebeispiel ist
[`19_VALIDATOR_RULES.md`](19_VALIDATOR_RULES.md); sie wird direkt aus dem Rule-Registry erzeugt und
durch einen Gleichheitstest gegen Drift geschützt.

## Health Report V2

V2 gruppiert Befundzahlen nach Regel, Severity und Kategorie und enthält Fahrzeug-, Graph- und
Ordnerstatistiken, Validatorversion sowie Validierungsdauer. Implementierte Regeln stammen aus dem
Registry, getestete Regeln aus der ausführbaren Positiv-/Negativ-Matrix; die Coverage wird daraus
automatisch berechnet. Der Health Score bleibt bewusst `null`, bis fachlich belastbare Gewichte und
eine größenunabhängige Normalisierung existieren. Das History-Schema ist definiert, wird aber noch
nicht gespeichert.

## Tolerierte Sonderfälle

`hiddenResearch`, `reqUnlock`, Reserve-, Premium- und andere nicht reguläre Fahrzeuge werden nicht
stillschweigend verworfen. Der Validator meldet sie als `info`. Unbekannte Gruppenmitglieder sind eine
`warning`, weil der Converter Premium-, Event- oder Squadron-Fahrzeuge bewusst aus der regulären
Calculator-Datenbank entfernen kann. Ein externer Unlock ist allein kein Graphfehler.
