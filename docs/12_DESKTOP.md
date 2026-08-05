# Desktop

## Anwendungen

### Datamine Converter

`wurstbrot_converter.py` startet ohne CLI-Pfade standardmäßig die Tkinter-GUI. Sie wählt Quellordner,
Ausgabeordner und optionale vorherige Datenbank. Die Konvertierung läuft in einem Daemon-Thread;
Meldungen gelangen über eine Queue zurück in den UI-Thread.

### GE Calculator

`ge_calculator_gui.py` lädt standardmäßig die Beispieldatenbank und bietet Nation, Fahrzeugart, A, B,
Fortschritt, Convertible RP, vorhandene GE, Optimierungsziel und SL-Rabatt. Das Ergebnis wird über
`explain_result` angezeigt.

## Windows-Starter

- `apps/datamine-manager/Wurstbrot_Converter_starten.bat`
- `apps/ge-calculator/Wurstbrot_GE_Calculator_starten.bat`
- `apps/ge-calculator/Wurstbrot_GE_Calculator_CLI_starten.bat`

Die Skripte bevorzugen `py -3` und fallen auf `python` zurück. Zwei Starter auf aktuellem `main`
enthalten eine überflüssige erste Backslash-Zeile; siehe bekannte Fehler.

## Regeln für Änderungen

- keine Fachlogik in Event-Handler kopieren
- lang laufende Arbeit außerhalb des UI-Threads
- Widgets nur aus dem UI-Thread verändern
- Parserfehler mit konkreter Datei oder Eingabe anzeigen
- Standardpfade über `Path`, nicht über fest codierte Laufwerksbuchstaben
