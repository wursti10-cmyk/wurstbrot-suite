# Wurstbrot Suite 1.0.0-rc.2

## Zweck

Die Wurstbrot Suite berechnet für War Thunder einen Forschungsweg von Fahrzeug A zu Fahrzeug B
einschließlich RP-, GE- und SL-Kosten. Datamine-Konvertierung, Validierung, Desktop-CLI/-GUI und eine
lokal arbeitende Browser-App gehören zum vorhandenen Produktumfang.

## Änderungen gegenüber RC.1

- Nationen werden in Browser und Desktop mit lesbaren deutschen Namen angezeigt.
- Fahrzeugarten heißen Panzer, Flugzeuge und Hubschrauber.
- Die Marine-Forschungsbäume sind als Küstenschiffe und Hochseeschiffe unterscheidbar.
- Die leere Startauswahl bei Fahrzeug A heißt Forschungsbaum.
- Der RC.2-Service-Worker-Cache liefert die aktualisierten Browser-Bezeichnungen aus.

Die internen IDs und alle Solver-, Graph-, Legacy- und Datamine-Verträge bleiben unverändert.

## Release-Candidate-Stand

- Legacy bleibt die standardmäßige und empfohlene Benutzerquelle.
- `shadow` vergleicht die Graphpipeline, zeigt Benutzern aber weiterhin das Legacy-Ergebnis.
- `graph_experimental` ist nur explizit aktivierbar und darf Graph ausschließlich bei
  `complete` und `exact_match` als Benutzerquelle verwenden.
- Die freigegebenen Accuracy-Gates umfassen 61 unabhängige reale A→B-Abnahmen, 60 Golden
  References, 8 Accuracy-9-Kernreferenzen, 16 metamorphische Verträge und 32 Boundary-Fälle.
- Python-, Graph-Mirror- und Browser-Regression umfassen jeweils 1.977 Fälle; Browser Hardening
  umfasst 44 direkte Fälle. Der Validator weist 42/42 Regeln und 100 Prozent Coverage nach.

## Bekannte Einschränkungen und Nicht-Blocker

- 14 Hidden-Folder-Fälle bleiben mangels autoritativer Evidenz bewusst `partial`. Der sichtbare
  Legacy-Fallback bleibt erhalten; es werden keine Gesamtsummen erfunden.
- Browser und Desktop besitzen keine Graph-Runtime und bleiben Legacy-only.
- Graph Experimental bleibt opt-in und ist nicht für die Default-Nutzung freigegeben.
- Eine dokumentierte Input-Repräsentationsdifferenz für einen leeren optionalen Start bleibt
  bestehen.

Dies ist ein Release Candidate zur fachlichen Prüfung, kein Stable Release. Die Bezeichnung stellt
keine Garantie vollständiger Fehlerfreiheit dar.
