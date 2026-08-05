# Known Bugs and Limitations

## Bestätigt auf `main`

| Bereich | Problem | Auswirkung | Status |
|---|---|---|---|
| Versionierung | `VERSION` ist `0.3.0-milestone1`, `pyproject.toml` ist `0.1.0` | Paket und App können verschiedene Versionen melden | offen |
| Windows | `Tests_starten.bat` beginnt mit `\` | unnötige Fehlermeldung beim Start möglich | Fix in Draft-PR #1 vorgeschlagen |
| Windows | CLI-Starter beginnt mit `\` | unnötige Fehlermeldung beim Start möglich | Fix in Draft-PR #1 vorgeschlagen |
| CI | keine Workflows auf `main` | Prüfungen laufen nicht automatisch | in Draft-PR #1 vorgeschlagen |
| Browser | keine Browser-App auf `main` | nur CLI/Tkinter nutzbar | in Draft-PR #1 vorgeschlagen |

## Modellgrenzen

- 49 Ziele mit `hiddenResearch` oder `reqUnlock` werden von der breiten Regression übersprungen.
- Sonderfreischaltungen werden als Warnung beschrieben, aber nicht allgemein als zusätzliche Bedingung gelöst.
- Der Optimierer bricht nach 75.000 Zuständen ab.
- `convertible_rp_shortfall` ist Information; verfügbare Convertible RP verteilen die Fahrzeugzeilen nicht.
- Eurokosten und GE-Paketpreise werden nicht berechnet.
- Der Graph kann nur einen direkten Vorgänger pro Fahrzeug darstellen.

## Pflege

Ein Eintrag wird erst entfernt, wenn Fix und Regressionstest in `main` liegen. Offene PRs dürfen nur in
der Statusspalte erwähnt werden.
