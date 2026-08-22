# Wurstbrot Suite 1.1.0-rc.1

## Zweck

Die Wurstbrot Suite berechnet für War Thunder einen Forschungsweg von Fahrzeug A zu Fahrzeug B
einschließlich RP-, GE- und SL-Kosten. Der 1.1-Release-Candidate ergänzt dazu den visuellen
Forschungsbaum in der lokalen Browser-App. Datamine-Konvertierung, Validierung, CLI, Desktop-GUI und
der bestehende Rechner bleiben Bestandteil des vorhandenen Produktumfangs.

## Visueller Forschungsbaum

- 44 reale Forschungsbäume mit 2.232 regulären Fahrzeugen und 1.993 autoritativen Vorgängerkanten
- deutsche Nation-/Fahrzeugart-Anzeigen, Suche und Cross-Tree-Sprung
- Kartenwahl per Pointer und Tastatur, Fahrzeugdetails, Zoom, Pan und responsive Darstellung
- A/B-Auswahl im Baum mit unveränderter produktiver Legacy-Berechnung
- Direct Path, zusätzliche Rang-Pflichtfahrzeuge und ausschließlich vorhandene Research-Kanten
- 395 Folder mit 821 realen Mitgliedern; `groupIndex` bleibt reines Darstellungsmetadatum
- sichtbare Hidden-, Partial- und unresolved-Zustände ohne erfundene Karten, Kanten oder Summen

## Fachverträge

- Legacy bleibt die standardmäßige und empfohlene Benutzerquelle.
- `shadow` zeigt weiterhin das Legacy-Ergebnis.
- `graph_experimental` bleibt ausdrücklich opt-in und darf Graph nur bei `complete` und
  `exact_match` als Benutzerquelle verwenden.
- Browser und Desktop bleiben Legacy-only; `ready_for_default_use=false`.
- PlayerProgress wird ausschließlich im bestehenden 1.0-Vertrag berücksichtigt; VT.8 ergänzt keine
  neue PlayerProgress-Oberfläche oder Semantik.

## Verifizierter RC-Stand

- 61/61 Acceptance, 60/60 Golden, 8/8 Core, 16/16 Metamorphic und 32/32 Boundary
- Python-, Graph-Mirror- und Browser-Regression jeweils 1.977/1.977
- Browser Hardening 44/44 und Validator 42/42 bei 100 Prozent Coverage
- VT.7: 44/44 Trees, 2.232/2.232 IDs, A→B 159/159, Node-Highlights 159/159 und
  Edge-Highlights 159/159
- 0 Mismatches, 0 Internal Errors, 0 Health Errors und 0 Release Blocker

## Bekannte Einschränkungen

- Exakt 14 Hidden-Folder-Fälle bleiben mangels autoritativer Evidenz `partial`; der sichtbare
  Legacy-Fallback bleibt erhalten.
- 28 deklarierte Mitglieder fehlen in 13 Foldern. Sechs vollständig herausgefilterte
  Kit-/Event-only-Folder werden nicht als leere oder erfundene UI-Elemente dargestellt.
- Der All-Tree-Report trennt Produktlogik mit DOM-Test-Doubles, synthetische Geometrie und separate
  Browser-Evidenz. Er behauptet keine 2.232 manuell geprüften Browser-DOM-Sprünge.
- Reale Mobile-Hardware, virtuelles Keyboard und eine historische harte Performance-Baseline sind
  nicht vollständig abgedeckt.

Dies ist ein Release Candidate für Mario Acceptance, kein Stable Release und keine Garantie
vollständiger Fehlerfreiheit. GE-Euro-Anzeige, automatische Online-Datamine-Aktualisierung,
PlayerProgress-UI, Planner, Mini-Map, Referral, API, Cloud und AI bleiben außerhalb dieses RC.
