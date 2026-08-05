# Validator

`wurstbrot_validator` prüft normalisierte `WT_Database_*.json`-Dateien unabhängig vom Solver.
Es erzeugt deterministisch sortierte Findings mit `error`, `warning` oder `info` sowie JSON- und
Text-Health-Reports. Der Converter importiert dieses Paket; der Calculator-Core bleibt unverändert.

Direktprüfung der Sample-Datenbank:

```bash
python apps/datamine-manager/wurstbrot_converter.py \
  --validate-database data/samples/WT_Database_2.57.1.67.json \
  --output build/health
```

Ein `error` liefert Exitcode 1. Ignorierte Regeln sind nur über die Python-API möglich und werden im
Report unter `ignoredRules` offengelegt.
