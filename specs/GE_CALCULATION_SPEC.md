# GE Calculation Specification

Status: verbindlich für produktiven Legacy-Core und additive Graph-Cost-Engine. Abweichende
Eingabevalidierung ist unten ausdrücklich getrennt.

## Eingaben

- `rpPerGE`: positiver Integer aus `economy.rpPerGE`
- je benötigtem Fahrzeug: Gesamt-RP und bereits erforschte RP
- `owned_ge`: nichtnegative vorhandene GE
- `sl_discount_percent`: Legacy Integer 0 bis 100; Graph-Cost ausschließlich 0, 30 oder 50
- optional `convertible_rp`
- fertiges `PrerequisiteResolution` für Graph-Cost

## Legacy-Normalisierung

```text
researched_rp = min(max(input_rp, 0), vehicle.rp)
remaining_rp  = 0, falls owned, sonst max(vehicle.rp - researched_rp, 0)
vehicle_ge    = 0, falls remaining_rp == 0,
                sonst ceil(remaining_rp / rpPerGE)
vehicle_sl    = 0, falls owned,
                sonst round(vehicle.sl * (1 - discount / 100))
```

Der produktive Legacy-Solver bleibt in Accuracy 5 unverändert. Er definiert `owned` weiterhin als
`researched=True` und `purchased=True` und klemmt numerische Fortschrittswerte auf 0 bis Fahrzeug-RP.

## Graph-Cost-Validierung und Fahrzeugzeile

Graph-Cost erfindet oder klemmt keine ungültigen Daten:

- `total_rp`, `base_sl`, `owned_ge` und ein vorhandenes `convertible_rp` sind nichtnegative Integer.
- `rpPerGE` ist ein positiver Integer.
- `researched_rp` liegt einschließlich Grenzen zwischen 0 und `total_rp`.
- Rabatt ist exakt 0, 30 oder 50.
- Required- und satisfied-Mengen sind disjunkt und enthalten keine unbekannten IDs.

Bei einem Verstoß ist `cost_status=unavailable`; vollständige oder partielle Summen werden nicht
ausgegeben.

```text
already_researched = researched oder purchased oder reserve
                     oder total_rp == 0 oder researched_rp == total_rp
effective_researched_rp = total_rp, falls already_researched,
                          sonst researched_rp
remaining_rp = 0, falls purchased oder reserve oder already_researched,
               sonst max(total_rp - effective_researched_rp, 0)
vehicle_ge = ceil(remaining_rp / rpPerGE), falls remaining_rp > 0, sonst 0
discounted_sl = 0, falls purchased oder reserve,
                sonst round(base_sl * (1 - discount / 100))
```

`researched` und `purchased` bleiben getrennte Ausgabefelder. Ein erforschtes, nicht gekauftes
Fahrzeug kann damit 0 RP/GE und weiterhin SL besitzen.

## Vollständige Aggregation

```text
total_rp              = sum(vehicle.remaining_rp)
total_ge_before_owned = sum(vehicle.ge)
total_ge_after_owned  = max(total_ge_before_owned - owned_ge, 0)
total_sl              = sum(vehicle.sl)
convertible_shortfall = max(total_rp - convertible_rp, 0), falls angegeben, sonst 0
```

Vorhandene GE werden nach der Summe aller individuell gerundeten Fahrzeug-GE abgezogen.

## Status-Propagation

| `resolution_status` | `cost_status` | Vollständige Summen | Teilzeilen |
|---|---|---:|---:|
| `resolved` | `complete` | ja | nicht erforderlich |
| `unresolved` | `partial` | nein (`null`) | nur eindeutig bekannte Required-IDs |
| `blocked` | `unavailable` | nein (`null`) | nein |
| `unsupported` | `unavailable` | nein (`null`) | nein |

Partielle Werte stehen ausschließlich in `partial_remaining_rp`, `partial_ge_before_owned` und
`partial_sl`. Vorhandene GE und Convertible-RP-Shortfall werden nicht auf Teilkosten angewandt.

## Invarianten

- alle Summen sind nichtnegative Integer
- `total_ge_after_owned <= total_ge_before_owned`
- GE-Rundung erfolgt nie auf der Gesamt-RP-Summe
- Fortschritt über Gesamt-RP ist im Graph-Contract ungültig und erzeugt keine Kosten
- ungültiges `rpPerGE <= 0` und nicht erlaubte Rabatte blockieren Graph-Cost
- vollständige Summen existieren genau dann, wenn `cost_status=complete`
- `partial` darf nie als vollständiger Bedarf dargestellt werden
- Required- und satisfied-Fahrzeuge werden nie doppelt bepreist

## Beispiele

- 0 RP bei 45 RP/GE → 0 GE
- 45 RP → 1 GE
- 46 RP → 2 GE
- zwei Fahrzeugzeilen mit je 1 RP → 2 GE

## Grenze zur Graph Resolution

`GraphPrerequisiteResolver` ist nicht Teil der Kostenberechnung. Sein Ergebnis enthält keine RP-, GE-,
SL- oder Euro-Werte. `GraphCostEngine` konsumiert diesen Contract, verändert ihn aber nicht.
`LegacyRankCompatibilityStrategy` darf im Shadow Mode die bestehende kostenbewusste Auswahl delegieren
und so eine Fahrzeugmenge reproduzieren, aber weder Kosten ausgeben, neue Kostenlogik definieren noch
als neuer Optimizer gelten.

## Shadow-Vertrag

Legacy und Graph werden auf Required-Set, Rest-RP/GE/SL pro Fahrzeug, Gesamtsummen, vorhandene GE und
Convertible-RP-Shortfall verglichen. `equivalent_match` ist nur bei identischen Kosten je Fahrzeug und
identischen Summen zulässig. `unresolved_expected` und `unsupported` sind weder Match noch Fehler;
jeder definitive `mismatch` ist ein CI-Fehler.

## Accuracy-6-Orchestrierungsvertrag

`GraphCalculationPipeline` darf Kosten ausschließlich erzeugen, indem sie zuerst
`GraphRuleEvaluator`, danach `GraphPrerequisiteResolver` und zuletzt `GraphCostEngine` aufruft. Der
Orchestrator besitzt keine eigene RP-, GE-, SL-, Folder-, Unlock- oder Rank-Semantik.

Vor Cost Calculation gilt eine gemeinsame Input-Grenze. Ungültige RP-Fortschritte, GE, Convertible
RP, Optionen oder Graph-Rabatte ergeben `invalid_input`; ungültige Datenbankkosten ergeben
`unavailable` mit Ursache `datamine_error`. Ein nicht blockierender Konflikt zwischen
`researched=True` und numerischen RP bleibt mit Rule ID sichtbar. Der Dual-Vergleich klassifiziert
einen daraus entstehenden Unterschied als `input_contract_difference`, niemals still als Match.

Vollständige Kosten sind im Pipeline-Ergebnis genau dann vergleichbar, wenn
`pipeline_status=complete` und `cost_status=complete` gelten. Partial behält vollständige Summen auf
`null`; vorhandene GE werden nicht angewandt. Der `DualEngineRunner` vergleicht alle in diesem
Dokument definierten Kostenwerte, verwendet produktiv aber ausschließlich `legacy_result`.
