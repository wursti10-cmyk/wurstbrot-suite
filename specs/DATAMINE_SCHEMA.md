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
