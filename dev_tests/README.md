# Testskripte

Entwickler-Tests für den Browser. Alle Fenster starten **unsichtbar** (außerhalb des Bildschirms,
ohne Fokus, stumm) und werden über das Chrome-DevTools-Protokoll (Port 9333) gesteuert.

- Testprofil: `dev_tests\testdata\` – wird beim ersten Lauf automatisch angelegt (Filterlisten-Download).
- Ausgaben (Logs, Screenshots, JSON): `dev_tests\out\`. Beides ist nicht in Git.
- Vor einem Lauf dürfen keine alten Testinstanzen (`python.exe … main.py`) laufen – die Skripte
  beenden sie selbst. Der normale Browser (`pythonw.exe`) wird nie beendet.

## Offline (ohne Browser, Node)

| Datei | Prüft |
|---|---|
| `node nf_unit.js` | `scripts/netflix.js`: Werbepausen, Abdecken, Hänger-Absicherung, Pausen-Werbung (29 Tests) |
| `node tw_unit.js` | `scripts/twitch_worker.js` mit echten Twitch-Playlists (`tw_ad_*.m3u8`, 18 Tests) |

## Mit Testprofil

| Datei | Prüft |
|---|---|
| `features_test.py` | 10 Grundfunktionen: Startseite, kosmetische Filter, Popups, Vollbild, App-Log |
| `trial.py <name> [regeln] [--url URL]` | Browser mit eigenen Filterregeln starten, Player-Zustand melden (South Park) |
| `tw_mask_test.py <name> <kanal> <typen>` | Twitch: Stream startet mit Werbung, Abdecken/Ersatz-Stream |
| `tw_matrix.py <kanäle>` | Twitch: welche Player-Typen gerade Werbung haben |
| `yt_start.py` / `yt_probe2.py` | YouTube: Zeit bis zum ersten Bild, Navigation in der Seite |
| `logger_test.py` | Werbe-Protokoll (patcht Dateien kurz und stellt sie wieder her – nur bei geschlossenem Browser) |
| `frame_test.py` | Fensterrahmen: Stile, Treffer-Test (WM_NCHITTEST), Rand-Streifen |
| `gx_snapshot.py` | Screenshots von Oberfläche + Dialogen nach `out\gx_shots\` |
| `midroll_watch.py` | Twitch-Werbepausen großer Kanäle beobachten, ohne Browser (`twlib.py`) |

## Netflix (mit dem echten Profil `browser_data\`)

Netflix braucht den eingeloggten Zugang – diese Tests starten das **normale Profil**, also nur wenn
der normale Browser geschlossen ist. Sie verschieben „Weiterschauen“ beim Testtitel.

| Datei | Prüft |
|---|---|
| `nf_start.py <name> <titel-id>` | Titel ab Anfang: Werbung sichtbar? Was hat der Blocker entfernt? |
| `nf_seek.py` | Vorspulen auf 20/45/75 min, Werbung/Fehler danach |
| `nf_pause_final.py normal\|netz` | Pausen-Werbung: `normal` = wie ausgeliefert, `netz` = Entfernen aus, nur Sicherheitsnetz |
| `nf_pause_probe2.py` | Mitschnitt beim Pausieren: GraphQL-Abfragen, DOM, Screenshot |

Hinweise: Direkt aufgerufene Titel starten wegen der Autoplay-Sperre oft nicht von selbst – die
Skripte klicken dann per CDP auf Play. Die Pausen-Werbung kommt nur bei echtem Pausieren
(Leertaste per CDP) und nicht nach jeder Pause. Läufe im Modus `netz` erzeugen absichtlich
Vorfälle im Werbe-Protokoll – danach aus `browser_data\logs` entfernen.

`cdp.py` ist ein kleines Werkzeug für Hand-Abfragen an den laufenden Testbrowser
(`python cdp.py eval "<js>"`, `shot bild.png`, `net 10 filter`).
