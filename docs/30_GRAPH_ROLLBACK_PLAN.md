# Graph Experimental Switch and Rollback Plan

## Status

Der CLI-Experimentalmodus ist implementiert. Es existiert weiterhin keine Default-Umschaltung:
`legacy` bleibt Standard und Empfehlung. Graph muss pro Aufruf ausdrücklich mit
`--engine graph-experimental` aktiviert werden; die Auswahl wird weder gespeichert noch aus
Confidence-Werten abgeleitet.

Maschinenlesbarer Vertrag:
[`accuracy/rollback/experimental_switch_plan.json`](../accuracy/rollback/experimental_switch_plan.json).
Plan-Version 2 ersetzt das frühere mehrdeutige Feld `productiveSwitchImplemented` durch getrennte
Fakten für den implementierten CLI-Experimentalmodus und die weiterhin fehlende Default-Umschaltung.

## Ausführungsmodi

- `legacy`: Nur Legacy läuft und liefert das Benutzerergebnis.
- `shadow`: Legacy liefert das Benutzerergebnis, Graph wird parallel verglichen.
- `graph_experimental`: Graph darf bei `complete` + `exact_match` das Benutzerergebnis liefern;
  Legacy läuft parallel als Vergleich und Fallback.

Desktop und Browser bleiben Legacy-only. Es gibt keinen GUI-Schalter und keine Browser-Graph-Runtime.

## Fallback

Graph Experimental verwirft das Graph-Benutzerergebnis bei `internal_error`, `unavailable`,
`partial`, `blocked`, nicht exaktem Vergleich oder Adapter-Contract-Verletzung. Ein vorhandenes
Legacy-Ergebnis wird verwendet. Bei deaktiviertem Feature Flag geschieht dies ohne Graph-Ausführung.
`invalid_input` ist die bewusste Ausnahme: Es wird unabhängig von der Fehlerrepräsentation kein
Benutzerergebnis ausgegeben. Ergebnisquelle, Fallback-Grund, Graphstatus und Vergleichsstatus
bleiben in der CLI sichtbar.

`partial` besitzt keine verbindlichen Graph-Gesamtsummen. Der Graphstatus wird diagnostiziert, aber
die Benutzerwerte stammen vollständig aus Legacy. Fehlt auch Legacy, ist das Ergebnis
`unavailable`; es werden keine Kosten erfunden.

## Rollback

Rollback besteht aus dem Weglassen der Option oder `--engine legacy`. Da Aktivierung pro Prozess
erfolgt, ist weder Neustart noch Datenmigration erforderlich. Gespeicherter Fortschritt und
Datenbankschema werden nicht verändert.

Lokale und CI-Artefakte bleiben verfügbar:

- `Graph_Shadow_<gameVersion>.json/.txt`;
- `Graph_Experimental_<gameVersion>.json/.txt`;
- `Accuracy_Confidence_<gameVersion>.json/.txt`.

## Daten und Datenschutz

Reports bleiben lokal oder werden als CI-Artefakte erzeugt. Benutzertelemetrie ist ausgeschlossen,
bis eine spätere ausdrückliche Produkt- und Datenschutzentscheidung sie erlaubt.

## Grenzen

- `ready_for_default_use` bleibt false.
- Legacy ist in 1.0 die einzige empfohlene Quelle.
- Die 14 Partial-Folder-Fälle verwenden Legacy-Fallback; es wurde keine Heuristik ergänzt.
- Die v1-Input-Verträge sind angenommen: Rabatt 0/30/50, strikte Progress-Grenzen und Ablehnung
  inkonsistenter Forschungsstatus-/RP-Zustände. Das ändert weder Default noch Rollback.
- Der Produktumfang bleibt auf Forschungsweg A → B und RP-/GE-/SL-Kosten begrenzt.
