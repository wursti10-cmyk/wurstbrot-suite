# Optimizer

## Aufgabe

Der Optimierer ergänzt den direkten Zielpfad um möglichst günstige Fahrzeuge, bis jede erforderliche
Rangschranke erfüllt ist. Kandidaten stammen aus demselben Land, derselben Fahrzeugart und dem gerade
geprüften Rang.

## Suchverfahren

`_find_minimum_rank_additions` verwendet Uniform-Cost Search über Mengen von zusätzlichen
Vorgängerabschlüssen. Der leere Zustand startet im Heap; jeder Kandidat erweitert den Zustand um seinen
noch fehlenden Abschluss. Bereits besuchte Mengen werden nicht erneut verarbeitet.

## Zielfunktionen

| `optimize_for` | Primärwert |
|---|---|
| `ge` | Summe individuell gerundeter GE |
| `rp` | Summe fehlender RP |
| `sl` | rabattierte SL-Summe |
| `vehicles` | Anzahl neuer Fahrzeug-IDs |

Tie-Breaker sind GE, SL und die lexikografisch sortierten IDs. Dadurch bleiben Ergebnisse deterministisch.

## Filter

- bereits vorhandene IDs werden nicht erneut gewählt
- ausgeblendete Fahrzeuge nur mit `include_hidden_legacy`
- `reqUnlock`-Kandidaten erst, wenn durch Start oder Besitz Baumzugang angenommen werden kann
- Reservefahrzeuge erzeugen keine Kosten

## Sicherheitsgrenze

Nach 75.000 verarbeiteten Zuständen bricht die Suche mit `SolveError` ab. Diese Grenze schützt vor
kombinatorischer Explosion; sie ist kein Beweis globaler Optimalität für beliebig große künstliche Bäume.
