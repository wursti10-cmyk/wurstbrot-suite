# Release Process

## Versionierung

Semantische Versionierung mit Vorabkennzeichen verwenden: `MAJOR.MINOR.PATCH[-label]`. Die lesbare
Version `0.9.0-beta` wird in Python-Paketmetadaten PEP-440-konform als `0.9.0b0` dargestellt.

## Vorbereitung

1. Zielumfang einfrieren und offene Blocker klassifizieren.
2. `VERSION`, Paketmetadaten, UI-Titel, Changelog und Dokumentation angleichen.
3. Unit Tests und Regression ausführen.
4. Converter mit einer aktuellen entpackten Datamine prüfen.
5. Artefakte in sauberer Umgebung bauen.
6. Prüfsummen erzeugen und Smoke Test auf Zielsystem durchführen.

## Pull Request

Der Release-PR dokumentiert Änderungen, Migrationen, bekannte Einschränkungen und Prüfergebnisse. Kein
Release direkt aus einem ungeprüften Arbeitsbranch.

## Veröffentlichung

- annotierter Git-Tag auf dem freigegebenen Commit
- Release Notes aus dem Changelog, nicht nur Commit-Liste
- Windows- und Web-Artefakte eindeutig versionieren
- Sample-Datenbank mit Spielversion kennzeichnen
- Rollback: Tag behalten, fehlerhaftes Artefakt als zurückgezogen markieren und Patchrelease erstellen

## Nachlauf

Installationsweg, Start, Beispielrechnung und Datenimport aus Nutzersicht testen. Neue bekannte Fehler in
`docs/16_KNOWN_BUGS.md` eintragen.
