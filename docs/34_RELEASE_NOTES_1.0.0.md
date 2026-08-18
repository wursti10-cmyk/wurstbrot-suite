# Wurstbrot Suite 1.0.0

## Zweck

Die Wurstbrot Suite berechnet für War Thunder einen Forschungsweg von Fahrzeug A zu Fahrzeug B
einschließlich RP-, GE- und SL-Kosten. Datamine-Konvertierung, Validierung, Desktop-CLI/-GUI und eine
lokal arbeitende Browser-App gehören zum Produktumfang.

## Stable-Basis

Version 1.0.0 übernimmt den von Mario als Nutzer abgenommenen Release Candidate
`v1.0.0-rc.2`. Gegenüber diesem Kandidaten wurden ausschließlich Produktversion, Stable-Cache,
Packaging-, Build-, Readiness- und Release-Metadaten geändert.

Solver, Graph, Legacy-Verhalten, interne IDs und Datamine-Semantik bleiben unverändert.

## Ausführungsverträge

- Legacy bleibt die standardmäßige und empfohlene Benutzerquelle.
- `shadow` vergleicht die Graphpipeline, zeigt Benutzern aber weiterhin das Legacy-Ergebnis.
- `graph_experimental` ist nur explizit aktivierbar und darf Graph ausschließlich bei
  `complete` und `exact_match` als Benutzerquelle verwenden.
- Browser und Desktop bleiben Legacy-only.
- `ready_for_default_use=false` bleibt für Graph bestehen und ist von der Stable-Freigabe getrennt.

## Stable-Prüfstand

- 61/61 unabhängige reale A→B-Abnahmen
- 60/60 Golden References
- 8/8 Accuracy-9-Kernreferenzen
- 16/16 metamorphische Verträge
- 32/32 Boundary-Fälle
- Python-, Graph-Mirror- und Browser-Regression jeweils 1.977/1.977
- Browser Hardening 44/44
- Validator 42/42 Regeln bei 100 Prozent Coverage
- Health Report, Release Build, Clean Install und Release-Build-Acceptance bestanden

## Bekannte Einschränkungen und Nicht-Blocker

- 14 Hidden-Folder-Fälle bleiben mangels autoritativer Evidenz bewusst `partial`. Der sichtbare
  Legacy-Fallback bleibt erhalten; es werden keine Graph-Gesamtsummen erfunden.
- Graph Experimental bleibt opt-in und ist nicht für die Default-Nutzung freigegeben.
- Eine dokumentierte Input-Repräsentationsdifferenz für einen leeren optionalen Start bleibt
  bestehen.
- Eine GE-Euro-Anzeige und automatische Online-Aktualisierung der Datamine-Daten sind ausdrücklich
  Post-1.0-Themen und nicht Bestandteil dieses Releases.

Stable 1.0.0 bezeichnet den vollständig geprüften Stand, ist aber keine Garantie vollständiger
Fehlerfreiheit.
