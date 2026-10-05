# Prompt für Claude Code: AdBlock GX als Browser-Erweiterung (Chrome + Opera GX)

> Diesen ganzen Text in ein lokales Claude Code im Projektordner `C:\AdBlockBrowser` geben
> (oder: „Lies EXTENSION_PROMPT.md und setze es um“).

---

## Aufgabe

Baue eine **Browser-Erweiterung (Manifest V3)** für **Chrome und Opera GX**, die die
Werbeblock-Funktionen meines Desktop-Browsers „AdBlock Browser GX“ übernimmt. Dazu gehört ein
**Discord-Stream-Modus**, damit Netflix im Discord-Bildschirm-Teilen nicht schwarz bleibt.

Der Desktop-Browser in diesem Repo muss **unverändert weiter funktionieren**.

Arbeite auf einem eigenen Branch (z. B. `browser-extension`) und committe in sinnvollen Schritten.
Prüfe Chrome-API-Details und Limits (Regelanzahl usw.) in der **aktuellen** Doku von
developer.chrome.com, statt dich auf Erinnerung zu verlassen. Diese Werte ändern sich.

Ich habe hier alles zum Testen: Windows, Chrome, Opera GX, Netflix-Abo (mit Werbung),
Twitch, YouTube und Discord. Sag mir genau, was ich klicken bzw. prüfen soll, wenn du einen
Test von mir brauchst.

---

## Was es schon gibt (Desktop-Browser)

PyQt6-Oberfläche + Microsoft Edge **WebView2** + **Brave AdBlock Rust-Engine** (`adblock`, Python).

| Datei | Inhalt |
|---|---|
| `scripts/youtube.js` | Entfernt `adPlacements`, `playerAds`, `adSlots` aus Player-Antworten (`ytInitialPlayerResponse`, `JSON.parse`, `fetch().json()`), überspringt Reste, blendet Werbeblöcke aus |
| `scripts/netflix.js` | Leert `adverts.adBreaks` und die Pausen-Werbung (GraphQL `PauseAdsArtwork`), deckt durchgerutschte Spots ab, Absicherung per `sessionStorage` + `location.reload()` |
| `scripts/twitch_main.js` | Ersetzt `window.Worker`, hängt `twitch_worker.js` vor den Video-Worker des Players |
| `scripts/twitch_worker.js` | Läuft im Worker: holt bei Werbung den Stream über andere Player-Typen (popout/frontpage/autoplay), sonst Abdecken + Stumm |
| `scripts/ad_watch.js` | Meldet durchgerutschte Werbung an den Desktop-Browser (Werbe-Protokoll) – **nur Desktop** |
| `scripts/window_edges.js` | Fensterrand-Streifen – **nur Desktop** |
| `site_scripts.py` | `build_site_scripts(enabled, whitelist)` setzt die Platzhalter ein und gibt `[twitch, youtube, netflix, ad_watch]` als fertigen JS-Code zurück. Importiert nur `json`/`os` |
| `filter_engine.py` | Filterlisten (`DEFAULT_FILTER_SOURCES`: EasyList, EasyPrivacy, EasyList Germany, Peter Lowe) + `site_fixes.txt`, Netzwerk-Check, kosmetische Regeln (`url_cosmetic_resources`, `hidden_class_id_selectors`) |
| `cosmetic_filter.py` | `COSMETIC_BRIDGE_SCRIPT`: Seite meldet ihre CSS-Klassen/IDs (`adblock-init`, `adblock-classes`), der Browser antwortet mit CSS. `build_cosmetic_css()` erzeugt eine Regel pro Selektor |
| `site_fixes.txt` | Eigene Regeln, u. a. South Park: `||dai.google.com/ondemand/hls/content/*/streams$domain=southpark.de` + Ausnahmen (`@@`), damit der Player startet |
| `browser_tab.py` (ca. Zeile 127) | Discord-Stream-Modus = WebView2 startet mit `--disable-gpu --disable-gpu-compositing --disable-accelerated-video-decode --disable-direct-composition-video-overlays` |
| `theme.py` | GX-Farben: `BG0 #0b0910`, `BG1 #13111b`, `BG2 #1b1826`, `LINE #2d2839`, `TEXT #f2eff8`, `MUTED #a7a0b8`, Akzent `#fa1e4e` (GX Rot), `OK #2ee88a` |
| `assets/icon.png` | App-Icon (Neon-Schild) |
| `dev_tests/nf_unit.js`, `dev_tests/tw_unit.js` | Offline-Tests der Scripts mit Node (`node dev_tests/nf_unit.js` → 29 Tests, `node dev_tests/tw_unit.js` → 18 Tests) |

Wichtige Details der Scripts:
- Platzhalter: `__AB_CONFIG__` (JSON `{enabled, whitelist, twitchBackupTypes}`) und in
  `twitch_main.js` `__AB_WORKER_HOOK__` (der Code von `twitch_worker.js` als JSON-String).
  `__AB_WORKER_INIT__` füllt `twitch_main.js` selbst zur Laufzeit.
- Meldungen an den Desktop-Browser laufen über `window.chrome.webview.postMessage(...)` in
  `try/catch`. In Chrome/Opera gibt es `chrome.webview` nicht, der Aufruf wird still ignoriert.
  Die Scripts funktionieren also ohne Änderung.
- Die Scripts prüfen selbst `location.hostname` und laufen nur auf ihrer Seite.

---

## Grundregeln

1. **`scripts/*.js` bleiben die einzige Quelle.** Nicht in die Erweiterung kopieren, sondern
   per Build-Script erzeugen. Musst du an einem Script etwas ändern, muss es für den
   Desktop-Browser kompatibel bleiben. Danach müssen beide Node-Tests grün sein.
2. Keine Python-Dateien des Desktop-Browsers umbauen. Ein neues Build-Script darf
   `site_scripts.py` importieren.
3. **`window.chrome.webview` nicht in Webseiten nachbauen.** Seiten könnten das erkennen.
4. `ad_watch.js`, `window_edges.js` und das Werbe-Protokoll gehören **nicht** in die Erweiterung.
5. Keine Fremd-Abhängigkeiten, wenn es ohne geht. Python 3 (Standardbibliothek) für den Build
   ist ok, Node ist auch installiert.

---

## Aufbau

```
extension/
  manifest.json
  background.js          Service Worker (Regeln, Scripts registrieren, Kosmetik-Antworten)
  popup.html / popup.js / popup.css
  content/cosmetic.js    Isolated World: Klassen/IDs sammeln, an background.js schicken
  icons/                 16/32/48/128 px aus assets/icon.png
  generated/             vom Build erzeugt -> in .gitignore
    twitch.js youtube.js netflix.js
    rules_site_fixes.json rules_easylist.json rules_easylist_germany.json
    rules_peter_lowe.json rules_easyprivacy.json
    cosmetic.json
tools/build_extension.py
start_opera_discord.bat  (siehe Discord-Teil)
```

`tools/build_extension.py`:
- ruft `site_scripts.build_site_scripts(True, [])` auf und schreibt die ersten drei Ergebnisse
  (twitch, youtube, netflix) nach `extension/generated/`. So bleiben Platzhalter und
  `TWITCH_BACKUP_TYPES` an einer Stelle.
- lädt die Filterlisten von den URLs aus `filter_engine.DEFAULT_FILTER_SOURCES` (Cache in einem
  gitignorierten Ordner, offline Fallback auf den Cache), wandelt sie um (siehe unten) und gibt
  eine Zusammenfassung aus: Regeln pro Liste, übersprungene Regeln nach Grund.
- erzeugt die Icons (Pillow ist ok, falls vorhanden, sonst einmalig erzeugen und committen).

---

## 1. Seiten-Scripts (Twitch, YouTube, Netflix)

- **Dynamisch** registrieren mit `chrome.scripting.registerContentScripts`:
  `world: "MAIN"`, `runAt: "document_start"`, `allFrames: true`, Matches
  `*://*.twitch.tv/*`, `*://*.youtube.com/*`, `*://*.netflix.com/*`.
- Abschalten und Ausnahmeliste laufen über das Registrieren selbst:
  - Blocker aus → Scripts abmelden.
  - Ausnahmen → `excludeMatches` (`*://*.<domain>/*`).
  - Die Config in den erzeugten Dateien ist darum fest `enabled: true, whitelist: []`.
- Beim Start (`runtime.onInstalled`, `runtime.onStartup`) und bei jeder Einstellungsänderung
  mit `chrome.storage` abgleichen, idempotent: `getRegisteredContentScripts` → update/unregister/register.
- Prüfen: Twitchs Worker-Hook (`blob:`-URLs, synchrones XHR auf die Blob-URL, `importScripts`)
  muss im MAIN World von Chrome genauso laufen wie in WebView2. Zum Testen dienen
  `window.__abTwitch`, `window.__abYouTube` und `window.__abNetflix` in der Konsole.

## 2. Netzwerk-Blocker (declarativeNetRequest)

MV3 hat kein blockierendes `webRequest`. Darum: Filterlisten beim Build in **statische
DNR-Regelsätze** umwandeln, ein Regelsatz pro Liste, `site_fixes` immer an.

Umwandlung (eigener Konverter in Python, die DNR-`urlFilter`-Syntax kennt `||`, `|`, `*`, `^`
schon selbst):
- `@@` → `allow`; `@@…$document` → `allowAllRequests`.
- Optionen: Ressourcentypen (`script`, `image`, `stylesheet`, `xmlhttprequest`, `subdocument`,
  `media`, `font`, `websocket`, `ping`, `object`, `other`), `third-party`/`~third-party` →
  `domainType`, `domain=a|~b` → `initiatorDomains`/`excludedInitiatorDomains`, `match-case`,
  `important` → höhere Priorität.
- Überspringen und zählen: `redirect`, `removeparam`, `csp`, `rewrite`, `popup`, `genericblock`,
  `elemhide`/`generichide` (die gehören in die Kosmetik), unbekannte Optionen, nicht-ASCII,
  ungültige Muster. Regex-Regeln nur, wenn sie ins Regex-Limit passen.
- **Platz sparen:** Reine Domain-Regeln mit gleichen Optionen (`||domain.tld^`) in **eine** Regel
  mit `requestDomains: [...]` zusammenfassen. Peter Lowe (~3.500 Domains) wird so zu einer
  einzigen Regel, EasyList/EasyPrivacy schrumpfen stark.
- Prioritäten: Ausnahmeliste (dynamisch) > `site_fixes`-Ausnahmen > Ausnahmen > `important` > Block.
- Die Limits (garantierte statische Regeln, aktivierte Regelsätze, Regex-Regeln, dynamische
  Regeln) in der aktuellen Doku nachschlagen. Im Build warnen, wenn es zu viel wird. In der
  Erweiterung `getAvailableStaticRuleCount()` beachten. Standardmäßig an: site_fixes,
  EasyList, EasyList Germany, Peter Lowe. EasyPrivacy, wenn es noch reinpasst, sonst im Popup
  zuschaltbar.
- Regeln vor dem Schreiben selbst prüfen (Pflichtfelder, gültige Typen, eindeutige IDs). Nach
  dem Laden in `chrome://extensions` auf Fehler/Warnungen der Regelsätze achten.
- Ausnahmeliste: dynamische Regel `allowAllRequests` mit `requestDomains: [domain]` für
  `main_frame`/`sub_frame` und höchster Priorität.
- Blocker aus: `updateEnabledRulesets` (alle aus) + Seiten-Scripts + Kosmetik aus.
- Zähler im Symbol: `declarativeNetRequest.setExtensionActionOptions({displayActionCountAsBadgeText: true})`.
- South Park muss weiter laufen (Folge startet ohne Werbung, Player bleibt nicht schwarz).

## 3. Kosmetische Filter (Elemente ausblenden)

Gleiches Prinzip wie im Desktop (`cosmetic_filter.py`):
- Build: `##`-Regeln der Listen nach `generated/cosmetic.json`:
  - seitenspezifisch: `host → [selektoren]`
  - generisch: nach Klasse/ID verschlüsselt, z. B. `##.adsbygoogle` unter Klasse `adsbygoogle`
  - übrige generische Selektoren
  - Ausnahmen (`#@#`) pro Host
  - Hosts mit `$generichide`/`$elemhide`
- Erweiterte Syntax überspringen und zählen: `#?#`, `#$#`, `#%#`, `##+js(...)`, `:-abp-…`,
  `:has-text(...)`.
- `content/cosmetic.js` (Isolated World, `document_start`, `all_frames`, alle Seiten): wie
  `COSMETIC_BRIDGE_SCRIPT`. Zuerst `init` (seitenspezifische Regeln), dann neu auftauchende
  Klassen/IDs gebündelt per `MutationObserver` an `background.js` schicken.
- `background.js` lädt `cosmetic.json` einmal (nachladen, falls der Service Worker beendet wurde)
  und fügt das CSS mit `chrome.scripting.insertCSS({target: {tabId, frameIds: [frameId]}, css, origin: "USER"})`
  ein. Das wirkt auch bei strenger Content-Security-Policy. Eine Regel pro Selektor wie
  `build_cosmetic_css()`, damit ein ungültiger Selektor nur sich selbst kaputt macht.
- Nichts auf Seiten der Ausnahmeliste oder bei ausgeschaltetem Blocker.

## 4. Popup (GX-Look)

Dunkel, Farben aus `theme.py`, Schrift `Bahnschrift, Segoe UI`, Neon-Akzent.
- Großer Schalter **Schutz an/aus**.
- Aktuelle Seite: **Ausnahme an/aus**, danach Tab neu laden.
- Blockiert auf diesem Tab (Zahl).
- Falls Twitch/YouTube/Netflix offen ist: kurzer Status aus `window.__abTwitch` /
  `__abYouTube` / `__abNetflix` (per `chrome.scripting.executeScript` mit `world: "MAIN"`),
  z. B. „YouTube: Werbedaten 3× entfernt“.
- Filterlisten: welche Regelsätze aktiv sind (EasyPrivacy zuschaltbar, falls nicht Standard).
- Bereich **Discord-Stream-Modus** (siehe unten).
- Einstellungen in `chrome.storage.local`.

## 5. Discord-Stream-Modus

Hintergrund: Mit Hardware-Beschleunigung wird DRM-Video (Netflix, Prime, Disney+) über ein
geschütztes Hardware-Overlay gezeigt. Discord nimmt dann nur Schwarz auf. Eine Erweiterung kann
die Hardware-Beschleunigung **nicht** selbst abschalten und den Browser nicht mit Parametern neu
starten.

**Schritt 0 – Diagnose zuerst:** Lass mich in Opera GX und in Chrome mit eingeschalteter
Hardware-Beschleunigung Netflix in Discord streamen und melden, ob das Bild schwarz ist. Bleibt es
sichtbar, ist für diesen Browser nichts zu tun.

**a) Hinweis + Knopf (Hauptlösung):**
- Auf netflix.com, primevideo.com/amazon.*/gp/video und disneyplus.com im Popup und als kleines,
  wegklickbares Banner (einmal pro Sitzung, abschaltbar) anzeigen: „Discord-Stream-Modus: Bild
  bleibt für Freunde schwarz? → Hardware-Beschleunigung aus“.
- Der Knopf öffnet die passende Einstellungsseite per `chrome.tabs.create`:
  - Chrome: `chrome://settings/system`
  - Opera/Opera GX (User-Agent enthält `OPR/`): die passende `opera://settings/…`-Seite
- **Ausprobieren**, welche URL in Opera GX wirklich direkt zur Option „Hardwarebeschleunigung
  verwenden“ führt. Falls keine direkt hinführt: Einstellungen öffnen und im Popup kurz
  beschreiben, wo die Option steht.
- Kurze Anleitung im Popup: Schalter aus → „Neu starten“ → nach dem Streamen wieder einschalten
  (sonst laufen Videos ohne GPU und Netflix evtl. in geringerer Auflösung).

**b) `start_opera_discord.bat` (Ergänzung, 1 Klick):**
- Startet Opera GX (zuerst den Standardpfad suchen, z. B. `%LOCALAPPDATA%\Programs\Opera GX\`,
  sonst Chrome) mit denselben Parametern wie der Desktop-Browser:
  `--disable-gpu --disable-gpu-compositing --disable-accelerated-video-decode --disable-direct-composition-video-overlays`.
- Dazu ein **eigenes Profil** (`--user-data-dir=...`), sonst werden die Parameter ignoriert,
  wenn der Browser schon läuft.
- Klären, wie die Erweiterung in dieses Profil kommt: `--load-extension` (in neuem
  Chrome-Stable nicht mehr erlaubt, bei Opera prüfen) oder einmalig per Hand laden. In der
  README beschreiben.
- Optional eine Verknüpfung „Opera GX (Discord)“ mit `assets/icon.ico`, wie `create_shortcut.py`.

**c) Experimentell, Standard AUS, nur wenn a) zu umständlich ist und Schritt 0 schwarz ergab:**
- Ein zusätzliches MAIN-World-Script nur für netflix.com (im Popup zuschaltbar), das bei
  `navigator.requestMediaKeySystemAccess` nur die Software-Schutzstufe anfragt. Das ist dasselbe,
  was ohne Hardware-Beschleunigung passiert, also kein Neustart nötig.
- Erst nur **protokollieren**, was Netflix anfragt (Key-Systeme, `robustness`-Werte), und mir
  zeigen. Danach testen, ob das Bild in Discord sichtbar wird und Netflix normal abspielt.
- Wenn es nicht zuverlässig klappt: wieder entfernen, a) und b) reichen.

---

## 6. Tests und Abnahme

Automatisch / vor jedem Commit:
- `node dev_tests/nf_unit.js` und `node dev_tests/tw_unit.js` grün (Scripts unverändert kompatibel).
- `python tools/build_extension.py` läuft durch, Zusammenfassung plausibel, JSON gültig.
- Wenn möglich ein kleiner Node-Test für den Regel-Konverter (Beispielregeln rein → erwartete
  DNR-Regeln raus), z. B. `dev_tests/dnr_unit.js` oder ein Python-Test.

Manuell (sag mir Schritt für Schritt, was ich tun soll):
1. `chrome://extensions` bzw. `opera://extensions` → Entwicklermodus → „Entpackte Erweiterung
   laden“ → `extension/`. Keine Fehler/Warnungen.
2. YouTube: Video ohne Pre-Roll, Startseite ohne Werbeblöcke, kein Adblock-Hinweis.
3. Twitch: Kanal öffnen, keine Werbung bzw. Abdeckung mit Hinweis während einer Werbepause.
4. Netflix (Abo mit Werbung): Titel startet ohne Werbung, Pausen-Werbung kommt nicht.
5. South Park: Folge startet ohne Werbung.
6. Nachrichtenseite (z. B. spiegel.de, chip.de): Werbeflächen ausgeblendet, Badge zählt.
7. Ausnahme für eine Seite setzen → dort wird nichts mehr blockiert, Scripts laufen nicht.
   Schutz aus → überall aus.
8. Browser neu starten → Einstellungen und Registrierungen bleiben.
9. Discord-Stream-Modus wie oben (Schritt 0, dann a/b).
10. Alles in **Chrome und Opera GX**.

## 7. Doku

- Abschnitt „Browser-Erweiterung (Chrome / Opera GX)“ in `README.md`: Bauen
  (`python tools/build_extension.py`), Laden, Funktionen, was **nicht** geht (Fensterrahmen,
  Tabs, eigene Startseite, Werbe-Protokoll, direkter GPU-Schalter) und Discord-Modus.
- `extension/generated/` und den Listen-Cache in `.gitignore`.
- Optional am Ende: `tools/pack_extension.py` erzeugt eine ZIP für Chrome Web Store / Opera
  Add-ons. Veröffentlichen erst, wenn ich es sage.

## Reihenfolge

1. Build-Script + Seiten-Scripts + Manifest + minimales Popup (an/aus) → in Chrome laden, YouTube/Twitch/Netflix testen lassen.
2. Netzwerk-Regeln + Ausnahmeliste + Badge.
3. Kosmetische Filter.
4. Popup fertig (GX-Look, Status).
5. Discord-Stream-Modus (Schritt 0 → a → b → evtl. c).
6. README, Aufräumen, Abschluss-Test in Chrome und Opera GX.

Nach jedem Schritt kurz zusammenfassen, was geht, was nicht, und was ich testen soll.
