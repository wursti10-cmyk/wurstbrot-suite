# GE Calculation Specification

Status: verbindlich für den aktuellen Python-Core.

## Eingaben

- `rpPerGE`: positiver Integer aus `economy.rpPerGE`
- je benötigtem Fahrzeug: Gesamt-RP und bereits erforschte RP
- `owned_ge`: nichtnegative vorhandene GE
- `sl_discount_percent`: Integer 0 bis 100
- optional `convertible_rp`

## Normalisierung

```text
researched_rp = min(max(input_rp, 0), vehicle.rp)
remaining_rp  = 0, falls owned, sonst max(vehicle.rp - researched_rp, 0)
vehicle_ge    = 0, falls remaining_rp == 0,
                sonst ceil(remaining_rp / rpPerGE)
vehicle_sl    = 0, falls owned,
                sonst round(vehicle.sl * (1 - discount / 100))
```

## Aggregation

```text
total_rp              = sum(vehicle.remaining_rp)
total_ge_before_owned = sum(vehicle.ge)
total_ge_after_owned  = max(total_ge_before_owned - owned_ge, 0)
total_sl              = sum(vehicle.sl)
convertible_shortfall = max(total_rp - convertible_rp, 0), falls angegeben, sonst 0
```

## Invarianten

- alle Summen sind nichtnegative Integer
- `total_ge_after_owned <= total_ge_before_owned`
- GE-Rundung erfolgt nie auf der Gesamt-RP-Summe
- Fortschritt über Gesamt-RP erzeugt keine negativen Restkosten
- ungültiges `rpPerGE <= 0` und Rabatt außerhalb 0..100 sind Fehler

## Beispiele

- 0 RP bei 45 RP/GE → 0 GE
- 45 RP → 1 GE
- 46 RP → 2 GE
- zwei Fahrzeugzeilen mit je 1 RP → 2 GE
