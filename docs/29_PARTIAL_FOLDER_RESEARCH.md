# Partial Folder Research Dossier

## Ergebnis

Die 14 partiellen Accuracy-6-Sonderfälle gehören zu genau vier Hidden-Legacy-Foldern. Für alle Ziele
sind ID, Folder, Mitgliederreihenfolge, `hiddenResearch`, Vorgänger, Rang, RP und SL in der Datamine
vorhanden. Nicht vorhanden ist eine autoritative Regel, wie Hidden-Folder-Mitgliedschaft Forschung,
Kauf, Rangzählung oder Kosten-Eligibility beeinflusst.

Maschinenlesbare Akte:
[`accuracy/research/partial_folder_cases_2.57.1.67.json`](../accuracy/research/partial_folder_cases_2.57.1.67.json).

## Ursachengruppen

| Folder | Mitglieder in Datamine-Reihenfolge | Anzahl |
|---|---|---:|
| `fiat_group` | `fiat_cr42`, `fiat_g50_seria2`, `fiat_g50_seria7as` | 3 |
| `mc200_group` | `mc200_serie3`, `mc200_serie7`, `mc-202` | 3 |
| `r2y2_group` | `r2y2_v1`, `r2y2_v2`, `r2y2_kai` | 3 |
| `sm_79_group` | `sm_79_1936`, `sm_79_1939`, `sm_79_1941`, `sm_79_1943`, `sm_79_iar`, `sm_79_1937`, `sm_79_1942` | 5 partielle Ziele in 7 Mitgliedern |

Alle 14 Ergebnisse bleiben `partial` mit `FOLDER_MEMBERSHIP`. Bekannte Fahrzeugkosten werden als
diagnostische Teilzeilen gezeigt; vollständige Summen, vorhandene GE und Convertible-RP-Shortfall
bleiben `null`.

## Warum `complete` nicht beweisbar ist

Die normalisierte Datamine beweist Struktur, nicht Erwerbssemantik. Insbesondere beweist
`groupIndex` weder „erstes Mitglied genügt“ noch „alle vorherigen Mitglieder sind Pflicht“. Auch eine
historische Anzeige im Baum beweist ohne überprüfte Quelle nicht, ob Forschung, Kauf und Rangzählung
dieselbe Regel verwenden. Jede automatische Auswahl wäre daher eine neue Folder-Heuristik.

## Benötigte Evidenz

Mindestens erforderlich sind:

- eine Gaijin-Regel oder ein Datamine-Feld für Hidden-Folder-Erwerb;
- manuell überprüfte In-Game-A→B-Referenzen für jede der vier Folderformen;
- eine angenommene Produktentscheidung zu Research-, Purchase- und Rank-Count-Auswirkung;
- Regressionen, die jede danach belegte Regel positiv und negativ absichern.

Bis dahin gilt: Klassifikation ist erlaubt, Auflösung nicht. Accuracy 7 verändert keine Folderregel.
