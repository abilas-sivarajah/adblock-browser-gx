# 🛡️ AdBlock Browser GX (Claude-Variante)

![Startseite](assets/screenshots/gx_startseite.png)

Desktop-Browser für Windows: **PyQt6**-Oberfläche, **Microsoft Edge WebView2** als Web-Engine
(per pythonnet eingebettet) und die **Brave AdBlock Rust-Engine** (`adblock`) als Werbeblocker.

Projektordner: `C:\AdBlockBrowser`. Diese Variante basiert auf dem Antigravity-Projekt
`adblock-browser` und lässt das Original unverändert.
Sie hat ein **eigenes Profil** (`browser_data\`), Cookies/Verlauf werden nicht geteilt.

---

## 🌟 Funktionen

- **Netzwerk-Blocker** – jede Anfrage läuft durch die Brave-Engine mit
  EasyList, EasyPrivacy, EasyList Germany und Peter Lowe's Liste (~120.000 Regeln)
  plus den mitgelieferten **Seiten-Fixes** (`site_fixes.txt`).
- **South Park ohne Werbung** – auf southpark.de wird die Werbung von Google DAI
  serverseitig in den Videostream geschnitten. Der Browser blockiert die DAI-Stream-Anfrage,
  der Player fällt dann auf den Original-Stream ohne Werbung zurück
  (Details: Kommentare in `site_fixes.txt`).
- **Kosmetische Filterung** – die Seite meldet ihre CSS-Klassen/IDs an den Browser, der
  antwortet mit den passenden Ausblende-Regeln (seitenspezifisch **und** die generischen
  `##.klasse`-Regeln der Listen). Eingefügt als Constructable Stylesheet, funktioniert
  dadurch auch auf Seiten mit strenger Content-Security-Policy.
- **Popup-Blocker** – Fenster, die eine Seite ohne Klick öffnen will, werden verworfen.
  Links mit `target=_blank` öffnen weiter als neuer Tab.
- **Twitch ohne Video-Werbung** – Twitch schneidet Werbung in den Live-Stream
  (`scripts/twitch_*.js`, Techniken nach [TTV-AB](https://github.com/GosuDRM/TTV-AB)). Der Browser
  hängt sich in den Video-Worker des Players:
  - Werbung nur in *deiner* Sitzung (z. B. beim Öffnen eines Kanals): derselbe Stream kommt sofort
    über den 360p-Zugang „autoplay“ (Hinweis „Werbung übersprungen – kurz in 360p“), nach einer
    zweiten Prüfung in voller Qualität über einen anderen Player-Zugang (popout → frontpage →
    mobile_web → site). Ist die eigene Sitzung wieder werbefrei, geht es dorthin zurück – ohne
    Hänger: alle Quellen laufen auf einer durchgehenden Segment-Zählung, zeitlich passend
    aneinandergesetzt (nichts doppelt, nichts übersprungen).
  - Werbepause des Streamers (gilt für alle Zugänge gleichzeitig, meist 30–60 s): die Werbung wird
    herausgeschnitten und durch schwarzes, stummes Bild ersetzt, mit Hinweis „Twitch-Werbepause …
    seit 0:08“. Danach läuft der Stream live weiter. (Streams in fMP4/HEVC/AV1: Werbung abgedeckt und
    stumm.)
  - Außerdem: Twitchs eigene Kopfzeilen für die Ersatz-Anfragen (Anmeldung nur, wenn ein Stream
    anonym nicht geht), Neustart-Hilfe bei hängendem Video, Werbebanner/„Stream Display Ads“
    ausgeblendet, VOD-Werbung (VAST) blockiert.
- **YouTube ohne Werbung** – die Werbe-Daten (`adPlacements`, `playerAds`, `adSlots`) werden
  aus den Player-Antworten entfernt, bevor der Player sie sieht (`scripts/youtube.js`).
  Werbeblöcke in Startseite/Sidebar und der „Werbeblocker“-Hinweis werden ausgeblendet.
- **Netflix ohne Werbung** (Abo mit Werbung, `scripts/netflix.js`) – der Player erfährt aus seinen
  Abspieldaten, wo Werbepausen kommen (`adverts.adBreaks`). Diese Liste wird geleert, bevor der
  Player sie sieht: Die Sendung startet direkt.
  - Läuft trotzdem ein Spot („Werbung 1 von 2 • 33“), wird der Player abgedeckt und stumm
    geschaltet, mit Hinweis und Restzeit.
  - Absicherung: Bleibt ein Titel nach dem Entfernen länger als 15 s bei 0:00 stehen, lädt der
    Browser ihn einmal ohne Entfernen neu. Die Werbung läuft dann abgedeckt und stumm, die
    Sendung startet sicher.
  - **Pausen-Werbung:** Beim Pausieren holt der Player ein Werbebild (GraphQL `PauseAdsArtwork`).
    Die Anzeige wird aus der Antwort entfernt – wie wenn keine gebucht wäre. Man sieht den normalen
    Pausenbildschirm („Sie sehen gerade …“). Kommt doch eine durch, wird der Werbe-Dialog
    unsichtbar gemacht (Leertaste spielt weiter) und ein Vorfall angelegt.
- **Discord-Streaming / Screen-Sharing (Netflix Fix)** – Wenn man Netflix, Prime Video
  oder Disney+ über Discord überträgt, bleibt das Videobild für Freunde normalerweise schwarz
  (DRM-Schutz über Hardware-Overlays). Der Browser bietet einen **Discord-Stream-Modus**:
  - Hardware-Beschleunigung kann in **GX Control** oder im **Hauptmenü** mit 1 Klick deaktiviert werden.
  - Alternativ per **`start_browser_discord.bat`** oder Parameter `python main.py --discord` starten
    (gilt nur für diese Sitzung, die gespeicherte Einstellung bleibt unverändert).
  - Das Video wird ohne geschütztes DirectComposition-Overlay gerendert und ist im Discord-Stream
    für alle Freunde sichtbar. Ohne Hardware-DRM liefern die Dienste evtl. eine geringere Auflösung.
  - Nach dem Umschalten startet der Browser neu und öffnet die aktuelle Seite wieder.
- **Shield-Dashboard** (Klick auf `🛡️ 14`): Statistik, Ausnahmeliste pro Seite,
  globaler Schalter, Live-Monitor, Filterlisten-Update. Änderungen laden die Seite neu.
- **Video-Vollbild** – drückt man im Player auf Vollbild, verschwinden Tab-, Adress- und
  Lesezeichenleiste und das Fenster geht in den Vollbildmodus.
- Tabs, Startseite mit eigenen Schnellzugriffen (werden gespeichert), Lesezeichen, Verlauf,
  Suche auf der Seite, Zoom, Entwicklertools.

## 🎮 Design (GX)

Gamer-Look im Stil von Opera GX – dunkle Flächen, eine Neon-Akzentfarbe, Schrift Bahnschrift.

- **Eigene Titelleiste** mit den Tabs, ohne sichtbaren Rahmen – intern ein echtes Windows-Fenster
  (`native_frame.py`): Fenster **nach oben an den Bildschirmrand ziehen = maximieren**, an die Seite =
  Bildschirmhälfte (Aero Snap), aus dem maximierten Zustand wegziehen = wiederherstellen,
  Doppelklick auf die leere Titelleiste = maximieren, Rechtsklick = Systemmenü. Größe ändern an allen
  Rändern (über Webseiten per unsichtbarem Streifen, `scripts/window_edges.js`).
- **Tabs** mit Favicon, **Lautsprecher-Symbol** wenn ein Tab Ton abspielt (Klick = stumm),
  Mittelklick schließt, Rechtsklick: neu laden, duplizieren, stummschalten, andere schließen.
- **Seitenleiste:** Startseite, Twitch, YouTube, Discord (öffnet oder springt zum vorhandenen Tab),
  Lesezeichen, Verlauf, Werbe-Protokoll, GX Control, Shield.
- **GX Control** (Paletten-Symbol unten in der Seitenleiste): 8 Akzentfarben – GX Rot, Neon Pink,
  Ultra Violett, Cyber Cyan, Toxic Grün, Lava Orange, Eis Blau, Gold Rush – sowie Seitenleiste,
  Lesezeichenleiste und animierter Hintergrund an/aus. Wirkt sofort.
- **Startseite:** Neon-Nebel + Synthwave-Gitter in der Akzentfarbe, Uhr, Suche (`/`),
  Schnellzugriff-Kacheln (eigene hinzufügen/entfernen), Shield-Statistik inkl. abgefangener
  Video-Werbung pro Seite.

| Twitch | GX Control | Shield |
|---|---|---|
| ![Twitch](assets/screenshots/gx_twitch.png) | ![GX Control](assets/screenshots/gx_control.png) | ![Shield](assets/screenshots/gx_shield.png) |

## 🚀 Starten

Doppelklick auf **`start_browser.bat`** (oder **`start_browser_discord.bat`** für Discord-Stream) oder:

```powershell
python main.py
python main.py --discord           # Discord-Streaming-Modus (Netflix ohne schwarzen Bildschirm)
python main.py https://www.southpark.de
```

Desktop-Verknüpfung „AdBlock Browser“ anlegen: `python create_shortcut.py`

## ⌨️ Tastenkombinationen

Funktionieren auch, während die Webseite den Fokus hat.

| Taste | Aktion |
|---|---|
| `Strg + T` / `Strg + W` | Neuer Tab / Tab schließen |
| `Strg + Tab` / `Strg + Shift + Tab` | Nächster / vorheriger Tab |
| `Strg + L` / `Alt + D` | Adressleiste |
| `F5` / `Strg + R` / `Strg + F5` | Neu laden / ohne Cache neu laden |
| `Alt + ←` / `Alt + →` / `Alt + Pos1` | Zurück / Vor / Startseite |
| `Strg + D` / `Strg + B` / `Strg + H` | Lesezeichen / Lesezeichenleiste / Verlauf |
| `Strg + F` | Suchen auf der Seite |
| `F11` / `Esc` | Vollbild an/aus / Vollbild verlassen bzw. Laden abbrechen |
| `F12` | Entwicklertools |
| `Strg + +` / `Strg + -` / `Strg + 0` | Zoom |

Downloads laufen über den eingebauten WebView2-Downloaddialog.

## 📝 Werbe-Protokoll (wenn doch Werbung kommt)

Der Browser schreibt mit, was bei Video-Werbung passiert – zu sehen im Shield-Dialog unter
**„Werbe-Protokoll“** (rot = Problem, grün = Blocker hat gegriffen).

- **Automatisch:** Läuft auf YouTube, Twitch, Netflix oder South Park trotz Blocker eine Werbung,
  legt der Browser einen Vorfall an – ebenso, wenn der Netflix-Player nach dem Entfernen hängen
  blieb („Player hing nach dem Entfernen der Werbung“).
- **Von Hand:** Menü ☰ → **„⚠️ Werbung auf dieser Seite melden“** (auch im Shield-Dialog) – für
  jede Seite, auf der dir Werbung auffällt.

Ein Vorfall liegt in `browser_data\logs\vorfaelle\<Zeit>_<Seite>_<Art>\`:

| Datei | Inhalt |
|---|---|
| `info.json` | was passiert ist, Zustand der Blocker-Skripte, Filterlisten-Stand, WebView2-Version |
| `anfragen.tsv` | die letzten ~500 Netzwerk-Anfragen des Tabs (erlaubt / BLOCK, Typ, URL) |
| `screenshot.png` | was der Tab in dem Moment gezeigt hat |
| `playlist.m3u8` | (Twitch) die Werbe-Playlist, wie Twitch sie geschickt hat |
| `seite.json` | (von Hand gemeldet) Video-Zustand und eingebettete Frames der Seite |

Die Übersicht steht in `browser_data\logs\werbung.log` (eine Zeile pro Ereignis). Es werden
höchstens 50 Vorfälle aufgehoben. Alles bleibt lokal auf dem Rechner.

## 🧩 Eigene Filterregeln

Optional `browser_data\filters\user_rules.txt` anlegen (normale Adblock-Syntax, z. B.
`||werbung.example^` oder `@@||wird-faelschlich-geblockt.example^`). Wird beim Start und nach
jedem Filterlisten-Update mitgeladen.

## 🔧 Debug / Tests (Umgebungsvariablen)

| Variable | Wirkung |
|---|---|
| `ADBLOCK_REMOTE_DEBUG_PORT=9333` | Chrome-DevTools-Protokoll auf diesem Port (Steuerung/Inspektion von außen) |
| `ADBLOCK_REQUEST_LOG=pfad.log` | jede Anfrage mit `allow`/`BLOCK` und Typ protokollieren |
| `ADBLOCK_HIDDEN_WINDOW=1` | Testmodus: Fenster außerhalb des Bildschirms, ohne Fokus, stumm |
| `ADBLOCK_DATA_DIR=ordner` | anderes Profil/Daten-Verzeichnis (z. B. für Tests neben dem normalen Browser) |

## 📁 Projektstruktur

```
AdBlockBrowser/
├── main.py               # Einstiegspunkt
├── main_window.py        # Hauptfenster (rahmenlos), Tabs, Navigation, Vollbild, Tastenkürzel
├── gx_widgets.py         # Titelleiste mit Tabs, Fensterknöpfe, Seitenleiste
├── native_frame.py       # Windows-Rahmen: Aero Snap, Schatten, runde Ecken, Treffer-Test
├── theme.py              # GX-Farben, Akzentfarben, Stylesheet, Design-Einstellungen
├── icons.py              # Linien-Icons (SVG) in beliebiger Farbe
├── design_dialog.py      # GX Control (Akzentfarbe, Seitenleiste, Animation)
├── browser_tab.py        # Tab mit WebView2: Blocker, kosmetische Filter, Popups, Startseite
├── filter_engine.py      # Brave-Engine, Filterlisten, Ausnahmeliste, Anfrage-Typen
├── site_fixes.txt        # Seiten-Fixes (u. a. South Park) in Adblock-Syntax
├── cosmetic_filter.py    # Seiten-Skript für kosmetische Filter (Klassen/IDs melden, CSS)
├── site_scripts.py       # lädt scripts/*.js und setzt Schutz-Einstellungen ein
├── ad_logger.py          # Werbe-Protokoll und Vorfälle
├── scripts/
│   ├── twitch_main.js    # Twitch: hängt sich in den Video-Worker des Players
│   ├── twitch_worker.js  # Twitch: Werbe-Playlists erkennen, werbefreien Stream einsetzen
│   ├── twitch_hold.ts    # Twitch: 1 s schwarzes Bild statt Werbung (MPEG-TS)
│   ├── youtube.js        # YouTube: Werbe-Daten entfernen, Fallback, Werbeblöcke ausblenden
│   ├── netflix.js        # Netflix: Werbepausen + Pausen-Werbung entfernen, Abdecken, Hänger-Absicherung
│   ├── ad_watch.js       # erkennt durchgerutschte Werbung und meldet sie ans Protokoll
│   └── window_edges.js   # Größe ändern am rechten/unteren Rand über Webseiten
├── start_page.py         # GX-Startseite (virtueller Host start.adblockbrowser.example)
├── bookmarks_history.py  # Lesezeichen & Verlauf (JSON)
├── adblock_dialog.py     # Shield-Dashboard
├── history_dialog.py     # Verlaufsdialog
├── create_shortcut.py    # Desktop-Verknüpfung
├── dev_tests/            # Testskripte (unsichtbarer Browser, Offline-Tests) – siehe dev_tests/README.md
├── assets/screenshots/   # Vorschaubilder für diese README
└── browser_data/         # Profil, Filterlisten, Einstellungen, ui_settings.json (automatisch angelegt)
```

## ⚠️ Grenzen

- Die South-Park-Lösung hängt davon ab, dass Paramount den Rückfall auf den werbefreien
  Stream beibehält. Ändern sie den Player, kann wieder Werbung kommen oder das Video
  schwarz bleiben – dann `site_fixes.txt` anpassen (Request-Log hilft beim Finden).
- **YouTube** lässt sich die Werbezeit serverseitig „bezahlen“: Bei manchen Videos schickt
  der Server die Videodaten erst nach ungefähr der Länge der Werbung. Statt Werbung sieht man
  dann einige Sekunden Ladekreis (gemessen 0–21 s; ohne Blocker liefen 12–23 s Werbung).
  Das lässt sich vom Browser aus nicht zuverlässig umgehen.
- **Twitch:** Während einer Werbepause des Streamers bekommt jeder Player-Zugang Werbung – es gibt
  dann keine werbefreie Quelle. Der Browser ersetzt sie durch schwarzes Bild, die Wartezeit bleibt
  aber (gemessen 35–45 s). Twitch ändert seinen Player regelmäßig; wenn wieder etwas nicht stimmt:
  Werbe-Protokoll ansehen oder F12 → Konsole → `window.__abTwitch` (`adBreaks`, `replaced`,
  `bridges`, `holds`, `masked`, `nativeReturns`, `stallFixes`, `backupTrail`, `errors`). Die
  Ersatz-Zugänge stehen in `site_scripts.py` (`TWITCH_BACKUP_TYPES`).
- **Netflix** zeigt nicht bei jedem Start Werbung, getestet wurde vor allem die Werbung vor
  dem Titel. Werbung mitten im Film war in den Tests nicht zu sehen (auch nach Vorspulen auf
  20/45/75 min nicht). Falls doch: Werbe-Protokoll ansehen oder F12 → Konsole →
  `window.__abNetflix` (`breaksRemoved`, `seen` mit den Positionen der Pausen, `adsShown`,
  `pauseAdsRemoved` / `pauseAdsHidden` für die Pausen-Werbung).
- Scriptlets (`##+js(...)`) aus den Listen werden nicht ausgeführt.

## 🙏 Danksagung

Die Twitch-Techniken (360p-Brücke über „autoplay“/android, zweite Prüfung vor voller Qualität,
Codec-Abgleich, Rückkehr zur eigenen Sitzung auf durchgehender Zeitachse, schwarzes Halte-Segment mit
fortlaufenden Zeitstempeln, Kopfzeilen und GQL-Weiterleitung über die Seite, Hänger-Hilfe,
Display-Ads, VOD-Werbung) sind nachgebaut nach **[TTV-AB](https://github.com/GosuDRM/TTV-AB) von
GosuDRM** (MIT-Lizenz mit Namensnennung). Der Code hier ist eine eigene, kleinere Umsetzung; das
Halte-Segment ist selbst erzeugt (Befehl in `site_scripts.py`). Nicht übernommen: das Vortäuschen
gesehener Werbung an Twitch (`ClientSideAdEventHandling_RecordAdEvent`).
