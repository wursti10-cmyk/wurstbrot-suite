# Research Graph Specification

## Begriffe

- **Baum:** alle Fahrzeuge mit gleichem `countryId` und `branchId`
- **Vorgänger:** `predecessors[id]`
- **Closure:** geordnete Pflichtkette von Wurzel bis einschließlich Ziel
- **Owned:** erforscht und gekauft
- **Required:** Fahrzeug, dessen Kosten im Ergebnis betrachtet werden

## Gültigkeit

1. Jede Fahrzeug-ID ist eindeutig.
2. Jeder nichtleere Vorgänger verweist auf eine bekannte ID.
3. Vorgängerkanten bilden keinen Zyklus.
4. Kanten dürfen nicht Nation oder Fahrzeugart wechseln.
5. Der Vorgängerrang darf nicht über dem Nachfolgerrang liegen.

Der Loader erzwingt 1 bis 3. Der Converter-Validator prüft zusätzlich 4 und 5.

## Solve(A, B)

1. B laden und verstecktes B standardmäßig ablehnen.
2. Falls A gesetzt: gleicher Baum wie B, sonst Fehler.
3. Owned um Closures explizit vorhandener Fahrzeuge erweitern.
4. Falls A gesetzt: Closure(A) als überwunden behandeln; A nur mit Option berechnen.
5. Closure(B) minus Owned bildet den direkten Pflichtpfad.
6. Reservefahrzeuge als vorhanden zählen.
7. Für relevante Ränge die `rankUnlock`-Anzahl prüfen.
8. Fehlende Rangfahrzeuge kostenoptimiert samt Closure ergänzen.
9. Required deterministisch nach Rang, Spalte, Reihenfolge und ID sortieren.

## Fehler

Unbekannte IDs, Zyklen, Baumwechsel, nicht erfüllbare Rangschranken und überschrittenes Suchlimit sind
keine Teilresultate, sondern Fehler.
