# Visual Tech Tree Foundation 1.1

## Ergebnis der Discovery

Die normalisierte Datenbank 2.57.1.67 reicht aus, um die regulären Forschungsbäume aller Nationen
deterministisch und ohne neue Forschungssemantik darzustellen. Belastbar sind Baumtyp, Rang,
Quellspalte, Reihenfolge, Folder-Mitgliedschaft, Vorgänger, daraus umgekehrte Nachfolger sowie
Hidden- und Unlock-Markierungen. Nicht belastbar sind pixelgenaue In-Game-Positionen, die Positionen
der vom bestehenden Konverter herausgefilterten Premium-/Sonderfahrzeuge und die Erwerbssemantik
historischer Hidden-Folder.

Die Foundation führt deshalb keine Solver-, Graph-, Legacy-, Folder- oder Datamine-Regel ein. Sie
projiziert ausschließlich vorhandene Daten. Der maschinenlesbare Vertrag steht in
[`specs/VISUAL_TECH_TREE_LAYOUT_CONTRACT.json`](../specs/VISUAL_TECH_TREE_LAYOUT_CONTRACT.json).

## Untersuchte Quellen im Repository

- `data/samples/WT_Database_2.57.1.67.json`: normalisierte Fahrzeuge, Vorgänger, Folder,
  Rangfreischaltungen und Source-Manifest mit Dateigrößen und SHA-256-Werten.
- `apps/datamine-manager/wurstbrot_converter.py`: Herleitung von Spalte, Reihenfolge,
  Folder-Index und Vorgängern aus `shop`; Zusammenführung von Rang-, Kosten- und Unit-Metadaten.
- `packages/core/wurstbrot_core/database.py`: geladener 1.0-Datenvertrag, Sortierung und
  Zyklusvalidierung.
- `packages/core/wurstbrot_core/research_graph.py`: vorhandene Fahrzeug-, Vorgänger-, Folder-,
  Unlock- und Rangknoten; keine zusätzlichen visuellen Positionsregeln.
- `packages/core/wurstbrot_core/solver.py`: autoritative Legacy-Benutzerausgabe für A→B.
- `accuracy/research/partial_folder_cases_2.57.1.67.json`: die 14 bekannten partiellen
  Hidden-Folder-Fälle.

Die im Source-Manifest genannten Rohdateien wie `shop(2).blkx`, `wpcost.blkx`, `rank.blkx` und
`unlocks.blkx` liegen nicht zusätzlich als Rohkopie im Repository. Die Discovery konnte ihre
normalisierte Struktur und die deterministische Konverterabbildung prüfen, aber keine nicht
gespeicherte Rohinformation nachträglich untersuchen.

## Vollständige Bestandsaufnahme

| Merkmal | Ergebnis |
|---|---:|
| Fahrzeuge | 2.232 |
| Nationen | 10 |
| reale Nation/Typ-Bäume | 44 |
| Panzer | 839 |
| Flugzeuge | 915 |
| Hubschrauber | 81 |
| Küstenschiffe | 174 |
| Hochseeschiffe | 223 |
| nichtleere Vorgänger | 1.993 |
| Wurzeln ohne Vorgänger | 239 |
| maximale direkte Nachfolger | 3 |
| Fahrzeuge mit mehreren Nachfolgern | 364 |
| deklarierte Folder | 395 |
| im Bestand gruppierte Fahrzeuge | 821 |
| fehlende deklarierte Folder-Mitglieder | 28 in 13 Foldern |
| `groupIndex`-Abweichungen von der deklarierten Reihenfolge | 0 |
| `hiddenResearch` | 18 |
| `reqUnlock` | 31 mit 21 unterschiedlichen Tokens |
| `rankPosXY` | 79, ausschließlich Hubschrauber |
| `fakeReqUnitPosXY` | 10, ausschließlich Hubschrauber |
| Premium-/Sonderfahrzeuge im normalisierten Bestand | 0 |

Alle 44 Bäume besitzen zusammenhängende Quellspalten von `0` bis zu ihrer jeweiligen Maximalspalte.
Deutschland/Panzer und Deutschland/Flugzeuge sind mit den Spalten `0…6` die breitesten Bäume. Die
Ränge sind baumabhängig: Panzer reichen regulär bis Rang VIII, Flugzeuge bis Rang IX,
Hubschrauber beginnen in Rang V, Küstenschiffe reichen bis Rang V und Hochseeschiffe bis Rang VII.

Von den 28 fehlenden Folder-Mitgliedern gehören 10 zu sieben teilweise vorhandenen Foldern. Weitere
18 bilden sechs vollständig herausgefilterte Event-/Kit-Folder, denen im normalisierten Bestand weder
Nation noch Baumtyp autoritativ zugeordnet werden kann. Die Foundation führt dafür keine Ersatzknoten
ein. Jeder teilweise vorhandene Folder nennt seine fehlenden IDs ausdrücklich.

## Bedeutung von `branchId`

`branchId` ist im untersuchten `shop`-Vertrag die Dimension des gesamten Fahrzeugtyps. Es existieren
genau fünf Werte:

| `branchId` | Anzeige | Bedeutung |
|---|---|---|
| `army` | Panzer | Landfahrzeugbaum |
| `aviation` | Flugzeuge | Flugzeugbaum |
| `helicopters` | Hubschrauber | Hubschrauberbaum |
| `boats` | Küstenschiffe | Coastal-Baum |
| `ships` | Hochseeschiffe | Bluewater-Baum |

`branchId` ist keine sichtbare Linie innerhalb eines Baums und darf nicht als Spaltennummer
interpretiert werden. Die sichtbare Quellspalte entsteht aus dem Index eines Elements in
`shop[country][branch].range`. Innerhalb dieser Spalte wird die Quellreihenfolge als `order`
übernommen. Folder-Kinder erhalten eine deterministische Zwischenreihenfolge; `groupIndex` bleibt
ihre exakte Reihenfolge im Folder.

## Evidenzklassifikation

Die Klassen bedeuten: A = direkte Datamine-/Normalisierungsangabe, B = deterministische Ableitung,
C = Heuristik und D = mit den vorhandenen Daten nicht bestimmbar. C wird im autoritativen Layout
nicht verwendet; D bleibt sichtbar unresolved.

| Layoutaussage | Klasse | Begründung |
|---|---|---|
| Fahrzeug-ID, Nation, Baumtyp | A | direkte Unit- bzw. `shop`-Containeridentität |
| Rang | A | normalisierte Rangmetadaten |
| RP und SL | A | bestehende normalisierte Kosten; vom Layout nur angezeigt, nie berechnet |
| Premium-, Reserve-, Special-, Hidden-Flags | A | direkte Metadaten; Premium/Special werden vor Ausgabe gefiltert |
| Quellspalte | B | nullbasierter Index des `shop.range`-Elements |
| Reihenfolge | B | deterministische `shop`-Iteration; Folder-Zwischenschritte sind fest definiert |
| Folder-Mitglieder | A | direkt deklarierter Folderinhalt |
| `groupIndex` | B | Index in der deklarierten Mitgliederliste; keine Erwerbsregel |
| Vorgänger | B | konservativ: explizites `reqAir` oder deterministische vorherige Quellposition; die normalisierte Datei bewahrt die Herkunft nicht getrennt |
| Nachfolger | B | exakte Umkehrung der Vorgängerkanten |
| `reqUnlock`-Token | A | direkt vorhanden; das Token beweist keine Fahrzeugkante |
| allgemeine X/Y-Position aus `rankPosXY` | D | nur 79 Hubschrauberwerte, nicht im Core-Modell und keine allgemeine Semantik belegt |
| allgemeine X/Y-Position aus `fakeReqUnitPosXY` | D | nur 10 Hubschrauberwerte und keine allgemeine Semantik belegt |
| Rangband + Spalte + lokaler Slot | B | stabile Sortierung aus Rang, Spalte, Reihenfolge und ID |
| pixelidentische Position zum Spiel | D | keine vollständigen Koordinaten oder autoritative Renderregeln |
| Hidden-Folder-Erwerbsregel | D | Mitgliedschaft beweist weder Forschung, Kauf noch Rangzählung |

Die Vorgängerstruktur enthält ausschließlich einzelne IDs oder `null`: 1.993 skalare Vorgänger und
239 Wurzeln, keine Arrays. Mehrfachvorgänger- oder OR/AND-Semantik ist damit nicht belegt und wird
nicht erfunden.

## Vergleich mit offiziellen Strukturen

Der Vergleich dient nur der Struktur- und Familiarity-Prüfung. Es wurden keine Screenshots,
Texturen, Icons oder sonstigen War-Thunder-Assets übernommen. Die offiziellen Seiten zeigen den
aktuellen Live-Stand und können zeitlich neuer als die Sample-Datamine 2.57.1.67 sein; einzelne
Fahrzeuge oder Verschiebungen sind deshalb keine Gegenreferenz für einen Byte-genauen Inhaltsvergleich.

| Repräsentativer Baum | Normalisierte Foundation | Offizielle Strukturbeobachtung |
|---|---|---|
| Deutschland/Panzer | 114 reguläre Fahrzeuge, Ränge I–VIII, Spalten 0–6, 64 gruppierte Fahrzeuge | [Offizielle Ground-Vehicle-Übersicht](https://wiki.warthunder.com/ground?t_c=germany&v=t) trennt Ränge, reguläre und Premiumfahrzeuge und zeigt mehrere vertikale Linien sowie Gruppen. |
| Deutschland/Flugzeuge | 130 reguläre Fahrzeuge, Ränge I–IX, Spalten 0–6, 81 gruppierte Fahrzeuge | [Offizielle Aviation-Übersicht](https://wiki.warthunder.com/aviation?t_c=germany&v=t) zeigt Rangbänder, Linien, Gruppen und eine getrennte Premiumspalte. |
| Deutschland/Hubschrauber | 8 reguläre Fahrzeuge, Ränge V–VII, Spalten 0–1 | [Offizielle Helicopter-Übersicht](https://wiki.warthunder.com/helicopters?t_c=germany&v=t) bestätigt die kleineren Baumformen, Rang V–VII sowie die Trennung regulärer und Premiumfahrzeuge. |
| Japan/Küstenschiffe | 25 reguläre Fahrzeuge, Ränge I–V, Spalten 0–1 | [Offizielle Coastal-Übersicht](https://wiki.warthunder.com/boats?t_c=japan&v=t) führt Coastal als eigenen Baum mit Rängen und Linien. |
| Deutschland/Hochseeschiffe | 31 reguläre Fahrzeuge, Ränge I–VII, Spalten 0–1 | [Offizielle Bluewater-Übersicht](https://wiki.warthunder.com/ships?t_c=germany&v=t) führt Bluewater getrennt von Coastal und zeigt Ränge, Gruppen und Premiumfahrzeuge. |

Die offizielle Beschreibung der
[Forschungsboni](https://warthunder.com/en/news/9020-development-roadmap-research-bonuses-for-new-nations-now-released-for-testing-en)
nennt dieselben fünf Typen Army, Helicopters, Aviation, Bluewater und Coastal. Sie unterscheidet
reguläre von Premium-, Squadron-, Event-, Pack-, Markt- und Hidden-Fahrzeugen und beschreibt das
erste Mitglied einer endständigen Gruppe als Gruppenrepräsentant für genau diese Bonusregel. Daraus
folgt keine allgemeine Folder-Erwerbsregel. Die offizielle
[Roadmap-Gruppierung](https://warthunder.com/en/news/8414-development-roadmap-following-the-roadmap-grouping-vehicles-changes-to-rank-i-and-ii-and-additional-improvements-to-premium-vehicles-en?page=4)
bestätigt, dass Ränge, vertikale Linien und Gruppen die vertraute Forschungsbaumstruktur prägen und
inhaltlich verschoben werden können.

## Familiarity Contract

Eine vertraute, aber eigenständige Wurstbrot-Darstellung erfüllt folgende Mindestmerkmale:

- Auswahl nach Nation und einem der fünf getrennten Baumtypen;
- horizontale Rangbänder und stabile vertikale Quellspalten;
- Forschungsfluss von oben nach unten;
- sichtbare exakte Vorgänger-/Nachfolgerverbindungen;
- zusammen erkennbare Folder-Mitglieder in `groupIndex`-Reihenfolge;
- A, B, Pflichtpfad, Rangkandidaten und nicht benötigte Fahrzeuge klar unterscheidbar;
- Hidden-, Partial-, unresolved- und Legacy-Fallback-Zustände nicht verbergen;
- originale HTML-/CSS-Darstellung ohne kopierte Spielassets.

Familiarity bedeutet ausdrücklich nicht Pixelgleichheit. Premium-/Sonderpositionen werden erst
darstellbar, wenn der Produktdatenvertrag diese Fahrzeuge samt belastbarer Position erhält.

## A/B Highlight Contract

Die Visualisierung nimmt ein bereits berechnetes, benutzersichtbares `SolveResult` entgegen. Sie
berechnet weder Pfad noch Kosten neu.

- A und B entsprechen exakt `start_vehicle_id` und `target_vehicle_id`.
- Pflichtfahrzeuge entsprechen exakt den `vehicle_lines`; ihr Zustand bewahrt den Solvergrund
  `direct_path`, `rank_unlock` oder `start_vehicle`.
- Eine Pflichtverbindung wird nur markiert, wenn sie eine vorhandene Vorgängerkante zwischen A bzw.
  einem direkten Solver-Pfadknoten und dem nächsten direkten Solver-Pfadknoten ist.
- Alle anderen Fahrzeuge sind ausdrücklich `not_required`; Folder- und Hidden-Zustände können
  zusätzlich sichtbar sein.
- `user_result_source`, Berechnungsstatus und Fallback-Grund werden unverändert übernommen.
- Fallback, partial oder unresolved erzwingen `complete=false`; die Visualisierung darf einen
  partiellen Graphbefund nicht als vollständigen Pfad ausgeben.
- RP, GE und SL bleiben unveränderte Solverwerte und werden vom Layoutmodul nicht berechnet.

## Die 14 bekannten Partial-Fälle

Alle 14 Hidden-Folder-Fälle bleiben Knoten ihres jeweiligen Baums und erhalten bei einer partiellen
Ausgabe den sichtbaren Zustand `partial_unresolved`. Ihre vier Folder bleiben vollständig in der
bekannten Mitgliederreihenfolge sichtbar. Es gibt keine neue Folderheuristik, keine Hochstufung auf
`complete` und keine erfundene Gesamtsumme. Der bestehende sichtbare Legacy-Fallback bleibt
unverändert.

## Isolierter Prototyp

[`apps/visual-tech-tree-prototype/`](../apps/visual-tech-tree-prototype/README.md) zeigt genau den
realen Baum Deutschland/Panzer. Der Beispielpfad reicht von Tiger H1 (A) zu Leopard 2A7V (B). Der
committete JSON-Payload wird deterministisch mit dem bestehenden Legacy-Solver erzeugt; JavaScript
rendert nur Layout und Highlight. Der Prototyp ersetzt `apps/web` nicht und wird nicht in das
produktive Browser-Artefakt aufgenommen.

## Implementierungsgrenzen nach der Foundation

Auf Basis der geprüften Daten ist die nächste visuelle Implementierungsstufe für reguläre Fahrzeuge
möglich. Vor einer produktiven Vollansicht bleiben folgende Punkte explizit offen:

- Produktentscheidung, ob Premium-/Sonderfahrzeuge in den normalisierten Vertrag aufgenommen werden;
- belastbare Positions-/Kategoriedaten für diese herausgefilterten Fahrzeuge;
- keine Auflösung der 14 Hidden-Folder-Fälle ohne neue autoritative Evidenz;
- keine Annahme pixelgenauer In-Game-Geometrie;
- separate spätere UX-Abnahme für responsive Darstellung und Bedienbarkeit.

PlayerProgress-UI, Planner, Empfehlungen, Accounts, Cloud/API/AI, Monetarisierung, Online-Datamine-
Updates, GE-Euro-Anzeige und jede neue Solver-/Folder-/Research-Semantik sind nicht Teil dieser
Foundation.
