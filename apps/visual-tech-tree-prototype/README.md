# Visual Tech Tree Foundation Prototype

Dieser isolierte, nicht produktive Prototyp zeigt genau einen realen Baum:
Deutschland / Panzer aus der normalisierten Sample-Datenbank 2.57.1.67.

Er ersetzt weder `apps/web` noch den bestehenden Rechner. Der Payload wird mit dem bestehenden
Legacy-Solver erzeugt; JavaScript berechnet keine Forschungslogik. Neu erzeugen oder prüfen:

```text
python scripts/build_visual_tree_prototype.py
python scripts/build_visual_tree_prototype.py --check
```

Zum lokalen Ansehen das Repository als statische Site bereitstellen und
`/apps/visual-tech-tree-prototype/` öffnen. Es werden keine War-Thunder-Assets verwendet.
