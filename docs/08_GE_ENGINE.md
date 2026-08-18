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
- Legacy-, Graph- und Browser-Grenzen lehnen negative, nicht ganzzahlige oder zu hohe
  Fortschritts-RP ab; kein Pfad klemmt sie still.
- Vollständig erforschte Fahrzeuge kosten 0 RP/GE, können bis zum Kauf aber weiterhin SL kosten.
- Gekaufte und Reservefahrzeuge kosten 0 RP, GE und SL.
- `convertible_rp` begrenzt die Konvertierbarkeit nicht, sondern erzeugt aktuell nur den ausgewiesenen
  `convertible_rp_shortfall`. Bei partiellem Cost-Status wird kein vollständiger Shortfall behauptet.

## SL

SL werden pro nicht gekauftem, nicht als Reserve verfügbaren Fahrzeug angesetzt. Der gemeinsame
v1-Vertrag akzeptiert nur die belegten Stufen 0 %, 30 % und 50 %. Beide Engines verwenden pro Fahrzeug das deterministische
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
Kosten. Erst `GraphCostEngine` liest das fertige Ergebnis und erzeugt im Shadow- oder ausdrücklich
experimentellen Pipeline-Aufruf Kostenzeilen. Der
Legacy Compatibility Mode darf ausschließlich die bestehende Fahrzeugauswahl delegieren; er ist
keine neue Optimizer-Semantik. Vollständiger Contract und Matrizen stehen in
[Graph Cost Engine](25_GRAPH_COST_ENGINE.md).

## Dual-Engine-Orchestrierung

`GraphCalculationPipeline` führt Evaluation, Resolution und Cost in dieser Reihenfolge aus. Der
nachgelagerte `DualEngineRunner` vergleicht Kostenzeilen und Summen mit Legacy. Zusätzliche
Ungültige Inputs können wegen strukturierter Graph- gegenüber Legacy-Fehlerrepräsentation
`input_contract_difference` heißen; das ist kein Match oder Mismatch. Die fachlichen Rabatt- und
Progress-Grenzen sind seit Accuracy 9 gleich. Details und aktuelle Zahlen stehen in
[Dual Engine Orchestration](27_DUAL_ENGINE_ORCHESTRATION.md).

## Execution Modes

`CalculationEngine` liegt oberhalb des Dual-Runners und definiert genau drei Ausführungsmodi:

| Modus | Benutzer-Ergebnis | Graph-Ausführung |
|---|---|---|
| `legacy` | Legacy | nein |
| `shadow` | Legacy | ja, nur Vergleich |
| `graph_experimental` | Graph nur bei `complete` + `exact_match`, sonst Legacy | ja |

Standard und Empfehlung bleiben `legacy`. Die Python-CLI aktiviert den dritten Modus nur durch den
expliziten Parameter `--engine graph-experimental`. Das interne Feature Flag ist standardmäßig
deaktiviert, gilt nur im aktuellen Prozess, wird nicht gespeichert und reagiert nicht auf
Confidence-Werte.

`GraphCalculationResultAdapter` überträgt ausschließlich die bereits existierenden Kernwerte in
`SolveResult`: Required Vehicles, Rest-RP, GE und SL je Fahrzeug, Gesamtsummen, vorhandene GE und
Convertible-RP-Shortfall. Er fügt weder Fachregeln noch neue Produktfelder hinzu. Abweichende
Required-/Cost-Line-Reihenfolge, fehlende vollständige Summen oder unbekannte Cost-Reasons verletzen
den Adaptervertrag und erzwingen Legacy-Fallback.

Die bestehenden benutzerseitigen Warntexte werden aus dem parallel geprüften Legacy-Ergebnis
bewahrt. Accuracy 8 führt damit keine neue Explain- oder Warntext-Semantik ein.

`partial` wird nicht als vollständiges Graph-Ergebnis angezeigt. Der Graphstatus und der
Fallback-Grund bleiben sichtbar, aber das bestehende Legacy-Ergebnis liefert die Benutzerwerte.
Dasselbe gilt bei `internal_error`, `unavailable`, nicht exaktem Vergleich oder nicht darstellbarem
Adapter-Ergebnis. `invalid_input` ist ausdrücklich kein Fallback-Fall: Das Ergebnis bleibt
`unavailable`; unterschiedliche Fehlerrepräsentationen dürfen keine erfolgreiche Berechnung
erzeugen. Fehlt bei einem zulässigen Fallback auch ein
Legacy-Ergebnis, lautet der Ausführungsstatus ebenfalls `unavailable`.

Die Accuracy-8-Matrix verarbeitet 2.090 eindeutig gezählte Requests: 1.988 verwenden Graph, 80
verwenden diagnostizierten Legacy-Fallback und 22 besitzen kein darstellbares Ergebnis. Davon sind
20 ausdrücklich abgelehnte Input-Contract-Differenzen und zwei blockierte Fälle. Es gibt
0 Mismatches und 0 Internal Errors. Neun reale A→B-Referenzen bestehen vollständig; von 49
Sonderfällen verwenden 35 Graph und 14 wegen `partial` Legacy-Fallback.

Desktop und Browser besitzen keine Graph-Runtime-Integration und bleiben vollständig auf Legacy.
Graph Experimental ist in 1.0 ausdrücklich nicht die empfohlene Rechenquelle.

## Unabhängige Accuracy-Referenzen

Accuracy 7 friert erwartete VehicleCostLines und Summen unabhängig vom laufenden Testresultat ein.
Die Golden-Prüfung liest RP und SL nochmals direkt aus der Datamine und berechnet Rest-RP,
individuell aufgerundete GE, Rabatt-SL, vorhandene GE und Convertible-RP-Shortfall erneut aus diesem
Dokument. Fixtures besitzen keinen automatischen Update-Modus.

Zusätzlich gelten 16 metamorphische Invarianten, darunter Monotonie von Fortschritt, vorhandenen GE,
Convertible RP und SL-Rabatten sowie die strikten `partial`-/`unavailable`-Grenzen. Details und
aktuelle Herkunftsverteilung stehen in [Accuracy Confidence](28_ACCURACY_CONFIDENCE.md).
