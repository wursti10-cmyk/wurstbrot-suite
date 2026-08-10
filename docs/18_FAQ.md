# FAQ

## Lädt die Suite meine Spieldaten hoch?

Nein. Der aktuelle Converter und Calculator arbeiten lokal und kennen keinen Account-Login.

## Welche Python-Version wird benötigt?

Python 3.10 oder neuer laut `pyproject.toml` und README.

## Kann die Suite BLKX direkt aus War Thunder entpacken?

Nein. Sie erwartet bereits entpackte, JSON-lesbare BLKX-Dateien.

## Warum stimmt Summe-RP geteilt durch 45 nicht immer mit GE überein?

Weil jedes Fahrzeug einzeln aufgerundet wird. Erst danach werden die GE addiert.

## Zählt ein erforschtes, aber nicht gekauftes Fahrzeug als vorhanden?

Nein. `owned` erfordert erforscht und gekauft.

## Darf A in einer anderen Linie als B liegen?

Ja, solange Nation und Fahrzeugart gleich sind. Die Pflichtkette von B wird weiterhin berechnet.

## Ist die Browser-Version bereits veröffentlicht?

Sie ist Bestandteil von `1.0.0-rc.1`. Lokal startet sie über `python -m http.server 8000` unter
`http://localhost:8000/apps/web/`; das öffentliche Pages-Deployment wird durch GitHub Actions erzeugt.

## Was bedeuten die 49 übersprungenen Regressionen?

Es sind ausgeblendete oder besonders freizuschaltende Ziele. Sie werden nicht als Fehler gezählt, sind
aber durch die Matrix auch nicht bestätigt.

## Wo beginne ich als Entwickler?

Mit `00_PROJECT_CONTEXT`, `02_ARCHITECTURE`, der passenden Spezifikation und `04_DEVELOPMENT_GUIDE`.
