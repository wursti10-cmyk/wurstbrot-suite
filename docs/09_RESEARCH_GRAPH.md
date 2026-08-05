# Research Graph

## Modell

Der normalisierte Graph ist eine Menge von Fahrzeugen und eine Map
`predecessors[vehicle_id] -> predecessor_id | null`. Damit besitzt jedes Fahrzeug höchstens einen
direkten Vorgänger; mehrere Nachfolger sind möglich. Der Graph wird pro Nation und Fahrzeugart
betrachtet.

## Pfadabschluss

`VehicleDatabase.closure(target)` läuft vom Ziel rückwärts bis zur Wurzel, erkennt Zyklen und gibt den
Pfad anschließend in Forschungsreihenfolge zurück. Das Ziel ist immer das letzte Element.

## Startfahrzeug A

Ein Startfahrzeug muss im selben `countryId` und `branchId` wie B liegen. A darf in einer anderen Linie
desselben Baums stehen. Sein eigener Vorgängerabschluss gilt als bereits überwunden. Standardmäßig wird
A selbst ebenfalls als vorhanden behandelt; mit `include_start_vehicle` kann A als Kostenzeile erscheinen.

## Besitz

Ein `VehicleProgress` gilt nur dann als `owned`, wenn `researched` und `purchased` wahr sind. Besitz
impliziert die Pflichtvorgänger dieses Fahrzeugs. Reservefahrzeuge werden für die Solverberechnung als
vorhanden behandelt.

## Rangschranken

Für jeden relevanten Rang vor dem Ziel liest der Solver die erforderliche Fahrzeugzahl aus
`rankUnlock`. Fehlen Fahrzeuge, sucht der Optimierer zusätzliche Kandidaten samt deren Vorgängern.
