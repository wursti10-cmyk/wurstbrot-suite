# Database Schema

Die erzeugte Datenbank enthält unter anderem:

```json
{
  "schemaVersion": 1,
  "gameVersion": "2.57.1.67",
  "economy": {
    "rpPerGE": 45
  },
  "vehicles": [],
  "predecessors": {},
  "groups": {},
  "rankUnlock": {}
}
```

## vehicles

Jedes Fahrzeug kann enthalten:

- `id`
- `name`
- `country`
- `branch`
- `rank`
- `rp`
- `sl`
- `reserve`
- `hiddenResearch`
- `reqUnlock`
- `group`
- `column`
- `rankPosXY`

## predecessors

Map von Fahrzeug-ID auf direkte Vorgänger-ID.

## groups

Fahrzeugordner und deren enthaltene Fahrzeuge.

## rankUnlock

Benötigte Anzahl gekaufter Fahrzeuge zur Freischaltung des nächsten Rangs.
