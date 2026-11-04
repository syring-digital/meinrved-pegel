# Pegelarchiv

Archiviert die Pegelwerte der WSV (PEGELONLINE, Lizenz DL-DE->Zero-2.0, 15-Minuten-Raster) und den Abgabeplan der Edertalsperre (WSA Weser) und erzeugt `tageswerte.json` für die App.
PEGELONLINE liefert über die Schnittstelle nur 31 Tage; das Archiv hält deshalb alles ab dem Start fest. Die Edertalsperre (W) ist ab 2000 vollständig.

- Ablage: `daten/<Pegelnummer>-<Größe>/<Jahr>.csv`, Zeilen `Zeitstempel (UTC);Wert`. Edertalsperre: m + PNP (= m ü. NN), Weserpegel und Affoldern: cm, Abfluss: m³/s.
- `daten/wsa/abgabe.csv`: geplante Abgabe der Edertalsperre je Tag (`Tag;m³/s;Stand der Vorhersage`).
- `python pegel.py seed <csv> <Pegelnummer> <W|Q>` liest einen Download von pegelonline.wsv.de (Ortszeit) ein, `update`, `wsa`, `build` laufen täglich im Workflow.
- App-Datei: https://syring-digital.github.io/meinrved-pegel/tageswerte.json
- Spiegel von `Tools/Pegel` im App-Projekt: `veroeffentlichen.sh` überträgt Code, `daten/` entsteht nur hier.
