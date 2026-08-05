# Datamine Reference

## Eingaben

| Schlüssel | Datei | Pflicht | Verwendung |
|---|---|---:|---|
| `shop` | `shop.blkx` | ja | Forschungsbaum, Reihenfolge, Gruppen, Freischaltungen |
| `wpcost` | `wpcost.blkx` | ja | RP-, SL-, GE- und Crewkosten |
| `rank` | `rank.blkx` | ja | Käufe zum Öffnen des nächsten Rangs |
| `warpoints` | `warpoints.blkx` | ja | Umrechnungsrate `playerExpToCountryFor1Gold` |
| `unlocks` | `unlocks.blkx` | ja | Beschreibung spezieller Freischaltungen |
| `units` | `units.csv` | ja | deutsche bzw. englische Anzeigenamen |
| `version` | `version.txt` | nein | Spielversion |
| weitere | `unittags.blkx`, CSVs | nein | werden gefunden und im Manifest erfasst |

## Dateisuche

Der Converter durchsucht rekursiv. Duplikatsuffixe wie `shop(3).blkx` werden normalisiert. Bevorzugt
werden bekannte Datamine-Pfade, exakte Dateinamen und flachere Treffer. Fehlt eine Pflichtdatei,
bricht die Konvertierung mit `ConversionError` ab.

## Normalisierung

- unterstützt: `army`, `aviation`, `helicopters`, `ships`, `boats`
- Premium- und Spezialfahrzeuge werden aus der regulären Calculator-Datenbank entfernt.
- Ungültige Vorgänger auf entfernte Fahrzeuge werden abgeschnitten und als `cutReferences` gemeldet.
- Gruppen werden in ihrer Reihenfolge verkettet.
- Quelldateien erhalten relativen Pfad, Größe und SHA-256 im Manifest.

## Parsergrenze

BLKX muss als JSON lesbar sein. Binäre VROMFS-Dateien werden nicht selbst entpackt. Änderungen an
Gaijins Strukturen müssen zuerst mit einer kleinen Fixture und danach mit einer realen Datamine geprüft
werden.
