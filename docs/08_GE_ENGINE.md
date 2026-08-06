# GE Engine

## Gemeinsame Grundregel

Die Datenbank liefert `rpPerGE`, aktuell 45 in der Beispieldatenbank. Legacy- und Graph-Cost-Engine
runden für jedes noch zu erforschende Fahrzeug separat:

$$
GE_i = \left\lceil\frac{\max(RP_i - Fortschritt_i, 0)}{RPProGE}\right\rceil
$$

Danach werden die einzelnen `GE_i` summiert. Erst von dieser Summe werden vorhandene GE abgezogen:

$$
GE_{benötigt}=\max\left(\sum_i GE_i-GE_{vorhanden},0\right)
$$

## Verbindliche Konsequenzen

- Zwei Fahrzeuge mit je 1 fehlendem RP kosten zusammen 2 GE, nicht 1 GE.
- Die neue Graph-Cost-Engine lehnt negative, nicht ganzzahlige oder zu hohe Fortschritts-RP ab. Der
  unveränderte Legacy-Solver klemmt sie weiterhin aus Kompatibilitätsgründen.
- Vollständig erforschte Fahrzeuge kosten 0 RP/GE, können bis zum Kauf aber weiterhin SL kosten.
- Gekaufte und Reservefahrzeuge kosten 0 RP, GE und SL.
- `convertible_rp` begrenzt die Konvertierbarkeit nicht, sondern erzeugt aktuell nur den ausgewiesenen
  `convertible_rp_shortfall`. Bei partiellem Cost-Status wird kein vollständiger Shortfall behauptet.

## SL

SL werden pro nicht gekauftem, nicht als Reserve verfügbaren Fahrzeug angesetzt. Der produktive
Legacy-Solver akzeptiert historisch 0 bis 100 Prozent. Der neue Shadow-Contract akzeptiert nur die
belegten Stufen 0 %, 30 % und 50 %. Beide verwenden pro Fahrzeug das deterministische
`apply_discount` mit Python-`round` auf `value * (1 - discount/100)`.

## Vollständigkeit

`GraphCostEngine` übernimmt den Status aus `PrerequisiteResolution`:

| Resolution | Kosten |
|---|---|
| `resolved` | vollständige Summen (`complete`) |
| `unresolved` | bekannte Zeilen, aber ausschließlich partielle Teilsummen (`partial`) |
| `blocked` oder `unsupported` | keine Zeilen und keine Summen (`unavailable`) |

Vorhandene GE werden erst nach der vollständigen Fahrzeugsumme abgezogen. Bei Teilkosten werden sie
nicht angewandt, damit das Ergebnis nicht als vollständiger Bedarf missverstanden wird.

## Nicht enthalten

Europreise, regionale Shoppreise, dynamische GE-Pakete, Premiumfahrzeug-Kaufpreise und Crewkosten sind
kein Bestandteil der aktuellen Solver-Summe.

## Verhältnis zur Graphpipeline

`GraphPrerequisiteResolver` bestimmt ausschließlich Voraussetzungen und enthält weiterhin keine
Kosten. Erst `GraphCostEngine` liest das fertige Ergebnis und erzeugt im Shadow Mode Kostenzeilen. Der
Legacy Compatibility Mode darf ausschließlich die bestehende Fahrzeugauswahl delegieren; er ist
keine neue Optimizer-Semantik. Der produktive Pfad bleibt unverändert `ResearchSolver`. Vollständiger
Contract und Matrizen stehen in [Graph Cost Engine](25_GRAPH_COST_ENGINE.md).

## Dual-Engine-Orchestrierung

`GraphCalculationPipeline` führt Evaluation, Resolution und Cost in dieser Reihenfolge aus. Der
nachgelagerte `DualEngineRunner` vergleicht Kostenzeilen und Summen mit Legacy, gibt produktiv aber
weiterhin ausschließlich das Legacy-Ergebnis frei. Zusätzliche Legacy-Rabatte außerhalb 0/30/50 und
striktere Fortschrittsregeln heißen `input_contract_difference`, nicht Match oder Mismatch. Details
und aktuelle Zahlen stehen in [Dual Engine Orchestration](27_DUAL_ENGINE_ORCHESTRATION.md).

## Unabhängige Accuracy-Referenzen

Accuracy 7 friert erwartete VehicleCostLines und Summen unabhängig vom laufenden Testresultat ein.
Die Golden-Prüfung liest RP und SL nochmals direkt aus der Datamine und berechnet Rest-RP,
individuell aufgerundete GE, Rabatt-SL, vorhandene GE und Convertible-RP-Shortfall erneut aus diesem
Dokument. Fixtures besitzen keinen automatischen Update-Modus.

Zusätzlich gelten 16 metamorphische Invarianten, darunter Monotonie von Fortschritt, vorhandenen GE,
Convertible RP und SL-Rabatten sowie die strikten `partial`-/`unavailable`-Grenzen. Details und
aktuelle Herkunftsverteilung stehen in [Accuracy Confidence](28_ACCURACY_CONFIDENCE.md).
