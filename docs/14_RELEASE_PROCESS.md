# Release Process

## Versionierung

Semantische Versionierung mit Vorabkennzeichen verwenden: `MAJOR.MINOR.PATCH[-label]`. Die lesbare
Version `1.0.0-rc.2` wird in Python-Paketmetadaten PEP-440-konform als `1.0.0rc2` dargestellt.

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

## Release-Candidate-Gate

Vor einem RC-Review muss der versionierte Accuracy-10-Bericht folgende Fakten belegen:

- mindestens 50 unabhängige reale A→B-Abnahmen; aktuell 61/61;
- Golden-, Kernreferenz-, Metamorphic- und Boundary-Suite vollständig grün;
- Python 3.10/3.12/3.13 mit identischem fachlichem Fingerprint;
- Browser-Legacy-Harness grün, ohne Graphaktivierung;
- 0 Mismatches, 0 Internal Errors, 0 Health Errors und keine offene Contract Decision;
- exakt 14 dokumentierte Hidden-Folder-Fälle bleiben partial;
- Legacy bleibt Default und `ready_for_default_use=false`.

`ready_for_rc_review=true` ist eine Prüfempfehlung, keine Engine-Umschaltung und keine
Veröffentlichung. Ein RC braucht weiterhin einen eigenen freigegebenen Branch/PR und vollständige
CI. Details und Befehle stehen in [Release Hardening](31_RELEASE_HARDENING.md).

## Veröffentlichung

- annotierter Git-Tag auf dem freigegebenen Commit
- Release Notes aus dem Changelog, nicht nur Commit-Liste
- Windows- und Web-Artefakte eindeutig versionieren
- Sample-Datenbank mit Spielversion kennzeichnen
- Rollback: Tag behalten, fehlerhaftes Artefakt als zurückgezogen markieren und Patchrelease erstellen

## Nachlauf

Installationsweg, Start, Beispielrechnung und Datenimport aus Nutzersicht testen. Neue bekannte Fehler in
`docs/16_KNOWN_BUGS.md` eintragen.
