# UI Specification

## Funktionsvertrag

Jede vollständige Calculator-Oberfläche muss mindestens Folgendes unterstützen:

- Datenbank laden und Spielversion/Fahrzeugzahl anzeigen
- Nation und Fahrzeugart wählen
- optionales Startfahrzeug A und verpflichtendes Ziel B wählen
- Fortschritt auf A/B, vorhandene GE, Convertible RP und SL-Rabatt erfassen
- Optimierungsziel `ge`, `rp`, `sl` oder `vehicles` wählen
- Berechnung starten, Fehler verständlich anzeigen
- Summen, Fahrzeugzeilen, Gründe, Rangschranken und Warnungen ausgeben

## Validierung

- Zahlen sind nichtnegativ; Rabatt liegt bei 0..100.
- A/B-Auswahl wird auf denselben Baum beschränkt.
- versteckte Fahrzeuge erscheinen nur in einem expliziten Legacy-Modus.
- leere optionale Werte werden von 0 unterschieden, wenn die Fachlogik dies verlangt.

## Präsentation

- Anzeigename plus stabile ID verfügbar machen
- Ränge und Gründe nicht nur durch Farbe kodieren
- lange Ergebnisse scrollbar und kopierbar darstellen
- Berechnungsergebnis nennt die verwendete Spielversion
- Warnungen stehen im Ergebnisbereich

## Plattformen

Desktop nutzt den Python-Core direkt. Ein Browser-Client muss die gleichen Contract Fixtures bestehen.
Unterschiede der Plattform dürfen Layout und Dateiauswahl, nicht aber Berechnungsergebnisse betreffen.
