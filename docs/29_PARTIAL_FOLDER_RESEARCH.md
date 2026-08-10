# Partial Folder Research Dossier

## Ergebnis

Die 14 partiellen Sonderfälle gehören zu genau vier Hidden-Legacy-Foldern. Für alle Ziele
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

## Accuracy-9-Einzelfallprüfung

Alle Werte der folgenden Tabelle werden bei jedem Testlauf gegen die Sample-Datenbank sowie aktuelle
Legacy- und Graphausgaben geprüft. `Legacy-Pfad` ist die direkte Vorgänger-Closure; die Zahl in
Klammern nennt die vollständige Legacy-Required-Menge einschließlich Rangergänzungen. Die vollständigen
Listen, lokalisierten Namen und Graph-Required-IDs stehen je Ziel in `caseEvidence` der JSON-Akte.

| Ziel | Nation | Rang | Folder / Index | Vorgänger → Nachfolger | Hidden / Unlock | RP / SL | Rank Gate | Graph | Legacy-Pfad (Required) |
|---|---|---:|---|---|---|---:|---|---|---|
| `fiat_cr42` | Deutschland | 1 | `fiat_group` / 0 | — → `fiat_g50_seria2` | ja / — | 2.900 / 700 | — | partial | `fiat_cr42` (1) |
| `fiat_g50_seria2` | Deutschland | 1 | `fiat_group` / 1 | `fiat_cr42` → `fiat_g50_seria7as` | ja / — | 2.000 / 2.100 | — | partial | `fiat_cr42` → `fiat_g50_seria2` (2) |
| `fiat_g50_seria7as` | Deutschland | 1 | `fiat_group` / 2 | `fiat_g50_seria2` → — | ja / — | 2.000 / 2.100 | — | partial | `fiat_cr42` → `fiat_g50_seria2` → Ziel (3) |
| `mc200_serie3` | Deutschland | 1 | `mc200_group` / 0 | — → `mc200_serie7` | ja / — | 5.900 / 6.300 | — | partial | `mc200_serie3` (1) |
| `mc200_serie7` | Deutschland | 1 | `mc200_group` / 1 | `mc200_serie3` → `mc-202` | ja / — | 3.000 / 6.300 | — | partial | `mc200_serie3` → `mc200_serie7` (2) |
| `mc-202` | Deutschland | 1 | `mc200_group` / 2 | `mc200_serie7` → — | ja / — | 4.000 / 10.000 | — | partial | `mc200_serie3` → `mc200_serie7` → Ziel (3) |
| `r2y2_v1` | Japan | 5 | `r2y2_group` / 0 | `b7a2` → `r2y2_v2` | ja / — | 95.000 / 270.000 | R1–R4: je 6 | partial | `b6n2` → `d4y1` → `d4y3` → `p1y1_mod11` → `b7a2` → Ziel (23) |
| `r2y2_v2` | Japan | 5 | `r2y2_group` / 1 | `r2y2_v1` → `r2y2_kai` | ja / — | 53.000 / 300.000 | R1–R4: je 6 | partial | Pfad zu V1 → Ziel (24) |
| `r2y2_kai` | Japan | 5 | `r2y2_group` / 2 | `r2y2_v2` → — | ja / — | 61.000 / 340.000 | R1–R4: je 6 | partial | Pfad zu V2 → Ziel (25) |
| `sm_79_1936` | Deutschland | 2 | `sm_79_group` / 0 | — → `sm_79_1939` | ja / — | 9.200 / 16.000 | R1→R2: 6 | partial | `sm_79_1936` (4) |
| `sm_79_1939` | Deutschland | 2 | `sm_79_group` / 1 | `sm_79_1936` → `sm_79_1941` | ja / — | 4.600 / 16.000 | R1→R2: 6 | partial | Pfad ab 1936 → Ziel (5) |
| `sm_79_1941` | Deutschland | 2 | `sm_79_group` / 2 | `sm_79_1939` → `sm_79_1943` | ja / — | 5.600 / 22.000 | R1→R2: 6 | partial | Pfad ab 1936 → Ziel (6) |
| `sm_79_1943` | Deutschland | 2 | `sm_79_group` / 3 | `sm_79_1941` → `sm_79_iar` | ja / — | 5.600 / 22.000 | R1→R2: 6 | partial | Pfad ab 1936 → Ziel (7) |
| `sm_79_iar` | Deutschland | 2 | `sm_79_group` / 4 | `sm_79_1943` → — | ja / — | 6.900 / 32.000 | R1→R2: 6 | partial | Pfad ab 1936 → Ziel (8) |

Die konkrete Partial-Ursache ist in allen 14 Fällen gleich: Struktur, Reihenfolge, Vorgänger und
Kosten sind bekannt, aber Hidden-Legacy-Folder-Mitgliedschaft beweist weder Forschungs- noch Kauf-
oder Rangzählungs-Eligibility. `sm_79_group` referenziert im Rohordner außerdem `sm_79_1937` und
`sm_79_1942`, die im normalisierten Fahrzeugbestand fehlen.

## Belegbare Folder-Fakten

Drei offizielle Quellen wurden gegen die benötigten Kernverträge geprüft:

- [Roadmap: Gruppierung und RP-Reduktion (24.08.2023)](https://warthunder.com/en/news/8414-development-roadmap-following-the-roadmap-grouping-vehicles-rank-changes-and-improvements-to-premium-vehicle-en)
  unterscheidet das erste Gruppenmitglied und nachgelagerte Mitglieder.
- [Bluewater-Gruppenänderung (28.08.2025)](https://forum.warthunder.com/t/economy-changes-for-bluewater-fleet-trees/261217)
  erklärt, dass gruppierte Folgefahrzeuge für den weiteren Bluewater-Baum nicht erforscht oder
  gekauft werden müssen.
- [Forschungsbonus-Regel (29.08.2024)](https://forum.warthunder.com/t/following-the-roadmap-vehicle-research-bonuses/161267/1)
  verwendet bei einer endständigen Gruppe das erste Mitglied als Repräsentant und nimmt Hidden-Ziele
  aus der dort beschriebenen Top-Fahrzeugregel aus.

Keine dieser Quellen definiert die Forschungs-, Kauf- oder Rangzählungsreihenfolge historischer,
versteckter Folder-Mitglieder. Daraus folgt keine implementierbare Hidden-Folder-Regel.

## Unlocks und Mehrfachvorgänger

Die Sample-Daten enthalten 31 `reqUnlock`-Fahrzeuge. Alle Tokens entsprechen den bekannten externen
Mustern; interne Fahrzeugtokens und unbekannte Tokens sind jeweils null. Ein Unlock ist ausschließlich
durch den exakten `PlayerProgress.fulfilled_unlocks`-Token oder die explizite External-Unlock-Option
erfüllt. Ohne diese Evidenz bleibt er unresolved und wird nie zu einer Vorgängerkante.

Von 2.232 normalisierten Vorgängereinträgen sind 239 `null` und 1.993 skalare IDs; Arrays kommen nicht
vor. Die Sample-Daten belegen daher weder AND- noch OR-Semantik. Synthetische Mehrfachkanten bleiben
mit allen Kanten als Evidence unresolved.

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

Bis dahin gilt: Klassifikation ist erlaubt, Auflösung nicht. Accuracy 9 verändert keine Folderregel.
