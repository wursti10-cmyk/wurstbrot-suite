# Technical Roadmap

## Erledigt auf `main`

- `0.1.0`: Converter, Export, Validierung und Patchvergleich
- `0.2.0-alpha`: Core-Solver, Fortschritt, GE/SL, Explain Mode und Unit Tests
- `0.3.0-milestone1`: Desktop-GUI, indirekte Starts und breite Regression

## Nächste Schritte

### Accuracy

- [x] strukturierte Datamine-Health-Reports als Veröffentlichungs-Gate
- [x] typisiertes ResearchGraph und deterministische Rule Evaluation parallel aufbauen
- [x] Voraussetzungen im Graph Shadow Mode auflösen und gegen 1.977 Legacy-Fälle spiegeln
- [x] 49 Sonderfälle mit expliziter Hidden-/Unlock-Evidenz vor/nach der Resolution klassifizieren
- [x] RP-, GE- und SL-Kosten aus Graph-Resolution im Shadow Mode berechnen und breit spiegeln
- [x] vollständige, partielle und nicht verfügbare Cost Contracts deterministisch absichern
- [x] Evaluation, Resolution und Cost als einheitliche GraphCalculationPipeline orchestrieren
- [x] vollständigen Dual-Engine-Shadow-Report mit Options-/Input-Coverage und Readiness erzeugen
- [x] kanonische Pipeline- und Vergleichsfingerprints für Regressionen versionieren
- [ ] Accuracy-Baseline, 60 unabhängige Golden References und 16 metamorphische Verträge betreiben
  (Accuracy 7: in diesem Branch implementiert, noch nicht ausgeliefert)
- [ ] Cross-Python- und kanonische Browser-Fixture-Prüfung als Confidence Gate betreiben
  (Accuracy 7: in diesem Branch implementiert, noch nicht ausgeliefert)
- [ ] drei deferred Contract-Entscheidungen vor einer produktiven Migration abschließen
- [ ] verbleibende 14 Hidden-Folder-Fälle mit zusätzlicher Quelldatenevidenz absichern
- [ ] eigenständigen Graph Optimizer in einem getrennten Sprint spezifizieren
- Explain Engine und Regressionen anhand exakter Datamine-Felder erweitern

### Dokumentation und Verträge

- Developer Bible als verbindlichen Einstieg pflegen
- Schema und Berechnung durch Golden Fixtures absichern
- aktuelle Einschränkungen in Release Notes übernehmen

### Beta

- Browser-Oberfläche und CI betreiben
- Browser- und Python-Ergebnisse über gemeinsame Fixtures gegeneinander testen
- Such- und kompakte Pfadansicht ergänzen
- portable Windows-Pakete erzeugen

### 1.0

- öffentliche Schema-Stabilität garantieren
- Sonderfreischaltungen systematisch modellieren
- reproduzierbare Releases mit Prüfsummen
- vollständige Benutzer- und Entwicklerdokumentation

## Priorisierungsregel

Korrektheit des Graphen und der Kosten hat Vorrang vor visuellen Funktionen. Neue Oberflächen dürfen
keine eigenen, ungetesteten Fachregeln einführen.
