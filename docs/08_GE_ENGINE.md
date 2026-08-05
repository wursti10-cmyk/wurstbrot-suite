# GE Engine

## Grundregel

Die Datenbank liefert `rpPerGE`, aktuell 45 in der Beispieldatenbank. Für jedes noch zu erforschende
Fahrzeug gilt separat:

$$
GE_i = \left\lceil\frac{\max(RP_i - Fortschritt_i, 0)}{RPProGE}\right\rceil
$$

Danach werden die einzelnen `GE_i` summiert. Erst von dieser Summe werden vorhandene GE abgezogen:

$$
GE_{benötigt}=\max\left(\sum_i GE_i-GE_{vorhanden},0\right)
$$

## Wichtige Konsequenzen

- Zwei Fahrzeuge mit je 1 fehlendem RP kosten zusammen 2 GE, nicht 1 GE.
- Fortschritt wird auf den Bereich 0 bis Fahrzeug-RP begrenzt.
- Bereits erforschte und gekaufte Fahrzeuge kosten 0 RP, GE und SL.
- `convertible_rp` begrenzt die Konvertierbarkeit nicht, sondern erzeugt aktuell nur den ausgewiesenen
  `convertible_rp_shortfall`.

## SL

SL werden pro nicht vorhandenem Fahrzeug angesetzt. `apply_discount` akzeptiert 0 bis 100 Prozent und
verwendet Python-`round` auf `value * (1 - discount/100)`.

## Nicht enthalten

Europreise, regionale Shoppreise, dynamische GE-Pakete, Premiumfahrzeug-Kaufpreise und Crewkosten sind
kein Bestandteil der aktuellen Solver-Summe.
