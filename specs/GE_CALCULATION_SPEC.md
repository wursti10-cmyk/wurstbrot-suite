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

Der Legacy-Solver bleibt unverändert und ist weiterhin Standard und Empfehlung. Er definiert `owned` weiterhin als
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
`LegacyRankCompatibilityStrategy` darf ausschließlich in den vergleichsbasierten Modi Shadow und
Graph Experimental die bestehende kostenbewusste Auswahl delegieren
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
Dokument definierten Kostenwerte und entscheidet selbst nicht über die Benutzer-Ergebnisquelle.

## Accuracy-8-Ausführungsvertrag

Die Auswahl der Rechenquelle liegt ausschließlich in `CalculationEngine`:

```text
legacy             -> nur ResearchSolver -> SolveResult
shadow             -> DualEngineRunner -> Legacy-SolveResult für den Benutzer
graph_experimental -> DualEngineRunner -> Graph-Adapter nur bei complete + exact_match
                                      -> sonst Legacy-Fallback
```

Ohne explizite Auswahl gilt `legacy`. Das Feature Flag für `graph_experimental` ist standardmäßig
false, pro Prozess lokal, nicht persistent und darf nicht durch Readiness- oder Confidence-Werte
aktiviert werden.

Der Graph-Adapter darf nur ein vollständiges `GraphCostResult` übernehmen. Er muss exakt die
Required-IDs und Cost-Line-Reihenfolge erhalten und folgende bestehende `SolveResult`-Felder
reproduzieren:

- `required_vehicle_ids`;
- Rest-RP, GE und SL je Fahrzeug;
- `total_rp`, `total_ge_before_owned`, `total_ge_after_owned`, `total_sl`;
- `convertible_rp_shortfall`;
- bestehende Rank Requirements und Warnungen.

Die Warntexte bleiben für Accuracy 8 der bestehende Legacy-Vertrag. Graph Experimental führt keine
neue Explain-Semantik ein; Pfad und numerische Kernwerte stammen weiterhin aus dem adaptierten
Graphresultat.

Der Graphwert ist als Benutzerergebnis nur zulässig, wenn Pipeline `complete`, Cost `complete`, alle
Summen nicht `null` und der Dual-Vergleich `exact_match` sind. `equivalent_match` reicht für diesen
ersten Experimentalvertrag absichtlich nicht.

Fallback auf ein vorhandenes Legacy-Ergebnis ist verbindlich bei:

- `internal_error`;
- `unavailable`;
- `invalid_input`, falls Legacy denselben Request akzeptiert;
- `partial` oder `blocked`;
- jeder nicht exakten Vergleichskategorie;
- nicht darstellbarem oder vertragswidrigem Adapter-Ergebnis.

Bei `partial` dürfen Graph-Teilsummen niemals als vollständiger Benutzerbedarf erscheinen. Der
Graphstatus bleibt diagnostisch sichtbar, das Legacy-Ergebnis liefert die bestehenden Kernwerte.
Fehlt auch Legacy, ist das Ausführungsergebnis `unavailable` und enthält keine erfundenen Kosten.

Desktop und Browser bleiben außerhalb dieses Vertrags auf Legacy. Der CLI-Experimentalmodus ist vor
Version 1.0 nicht die empfohlene Quelle und erweitert den Produktumfang nicht über Forschungsweg A → B
sowie RP-, GE- und SL-Kosten hinaus.

## Independent Reference Contract

Golden Expectations dürfen während eines Tests weder aus Legacy noch aus Graph berechnet oder
überschrieben werden. Für jede erwartete VehicleCostLine gelten unabhängig:

- `total_rp` und `base_sl` stimmen bytegenau mit der versionierten Datamine überein;
- `remaining_rp` folgt dem hier definierten Progress-Vertrag;
- `ge` ist `ceil(remaining_rp / rpPerGE)` je Fahrzeug;
- `discounted_sl` folgt dem erlaubten 0/30/50-Prozent-Graphvertrag;
- vollständige Summen sind exakt die Zeilensummen und nur bei `complete` vorhanden;
- `partial` besitzt ausschließlich diagnostische Teilsummen und wendet vorhandene GE nicht an;
- `blocked`/`unavailable` besitzt keine erfundenen Kostenzeilen.

Monotonie ist verbindlich: mehr gültige RP, vorhandene GE oder Convertible RP dürfen ihren jeweiligen
Restbedarf nicht erhöhen; 50 % SL dürfen nicht teurer als 30 %, 30 % nicht teurer als 0 % sein.
Die kanonische Referenz und ihr Fingerprint müssen unter Python 3.10, 3.12 und 3.13 identisch sein.
