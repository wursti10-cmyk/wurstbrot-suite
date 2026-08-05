# Browser-Version

Die Browser-App verarbeitet alle Daten lokal und benötigt keinen Server-Backend.

```bash
python -m http.server 8000
```

Danach `http://localhost:8000/apps/web/` öffnen. Ein direktes Öffnen der HTML-Datei
funktioniert ebenfalls, dann muss die Datenbank wegen Browser-Sicherheitsregeln manuell
ausgewählt werden.
