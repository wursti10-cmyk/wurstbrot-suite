# UI Guidelines

## Ziele

Die Oberfläche soll eine komplexe Berechnung in drei Schritten führen: Datenbank wählen, A/B und
Fortschritt angeben, Ergebnis verstehen. Fachbegriffe dürfen verwendet werden, müssen aber eindeutig
sein.

## Pflichtfelder und Reihenfolge

1. Datenbank und Spielversion
2. Nation und Fahrzeugart
3. Startfahrzeug A oder „Baumstart“
4. Zielfahrzeug B
5. angeforschte RP, vorhandene GE, Convertible RP, SL-Rabatt
6. Optimierungsziel

## Ergebnis

- zuerst Summen: fehlende RP, GE nach Abzug, SL
- danach jede Fahrzeugzeile mit Grund (`direct_path`, `rank_unlock`, `start_vehicle`)
- Rangfreischaltungen separat sichtbar machen
- Warnungen nie nur in Logs verstecken
- Zahlen lokal lesbar formatieren, intern aber als Integer behalten

## Zustände

- Laden, leer, gültig, Fehler und Berechnung müssen unterscheidbar sein.
- Ungültige Eingaben erhalten konkrete Hinweise; negative Werte sind verboten.
- Ausgeblendete Fahrzeuge sind standardmäßig nicht auswählbar.
- lange Berechnungen blockieren die GUI nicht; der Converter nutzt dafür bereits einen Worker-Thread.

## Barrierefreiheit

- Tastaturbedienung, sichtbarer Fokus, ausreichender Kontrast
- Labels statt Platzhalter als einzige Beschreibung
- Status- und Fehlermeldungen auch textlich ausdrücken
- responsive Browser-Ansicht ab 320 Pixel Breite als Ziel
