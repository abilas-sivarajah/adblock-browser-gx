"""
Ad logger: records what happens with video ads, so ads that still get through can be analysed.

- browser_data/logs/werbung.log        one JSON line per event (blocked ad breaks, ads that got
                                       through, manual reports)
- browser_data/logs/vorfaelle/<zeit>_<seite>_<art>/
      info.json       event details, page, blocker statistics, browser/filter versions
      anfragen.tsv    the tab's last network requests (erlaubt/BLOCK, type, URL)
      playlist.m3u8   (Twitch) the ad playlist as Twitch sent it
      screenshot.png  what the tab showed at that moment
"""

import json
import logging
import os
import re
import shutil
import time

logger = logging.getLogger("AdLogger")

MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_INCIDENTS = 50
MAX_DETAILS_CHARS = 200_000

# event kinds that get their own incident folder (everything else is only a log line)
INCIDENT_KINDS = {"ad-visible", "manual", "stripped", "masked", "adblock-warning"}

KIND_TEXT = {
    "ad-visible": "Werbung lief trotz Blocker",
    "manual": "Von Hand gemeldet",
    "stripped": "Kein werbefreier Ersatz-Stream – Werbung herausgeschnitten (Stream pausiert)",
    "masked": "Werbung abgedeckt und stumm geschaltet",
    "adblock-warning": "Werbeblocker-Hinweis der Seite entfernt",
    "ad-blocked": "Werbepause abgefangen",
    "ads-removed": "Werbe-Daten entfernt",
    "dai-blocked": "Werbe-Stream (Google DAI) blockiert",
    "backup-failed": "Ersatz-Stream fehlgeschlagen",
    "ad-visible-end": "Werbung vorbei",
}


def _safe(text: str, limit: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text))[:limit].strip("-") or "x"


class AdLogger:
    def __init__(self, data_dir: str):
        self.dir = os.path.join(data_dir, "logs")
        self.incident_dir = os.path.join(self.dir, "vorfaelle")
        self.log_file = os.path.join(self.dir, "werbung.log")
        os.makedirs(self.incident_dir, exist_ok=True)
        self.environment = {}  # filled by the browser (versions)

    # --- writing ---
    def event(self, site: str, kind: str, page_url: str, details: dict | None = None,
              requests=None, extra: dict | None = None, with_incident: bool = True) -> str | None:
        """Logs an event. For INCIDENT_KINDS (unless with_incident=False) an incident folder is
        written; its path is returned."""
        details = details or {}
        summary = KIND_TEXT.get(kind, kind)
        if details.get("summary"):
            summary += " – " + str(details["summary"])[:200]
        incident = None
        if kind in INCIDENT_KINDS and with_incident:
            try:
                incident = self._write_incident(site, kind, page_url, details, requests, extra)
            except OSError as e:
                logger.warning(f"Could not write incident: {e}")
        entry = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "site": site,
            "kind": kind,
            "url": page_url,
            "summary": summary,
            "incident": os.path.basename(incident) if incident else None,
        }
        self._append(entry)
        logger.info(f"[{site}] {summary}")
        return incident

    def _append(self, entry: dict):
        try:
            if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > MAX_LOG_BYTES:
                os.replace(self.log_file, self.log_file + ".1")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning(f"Could not write ad log: {e}")

    def _write_incident(self, site, kind, page_url, details, requests, extra) -> str:
        name = f"{time.strftime('%Y-%m-%d_%H-%M-%S')}_{_safe(site, 20)}_{_safe(kind, 20)}"
        folder = os.path.join(self.incident_dir, name)
        n = 2
        while os.path.exists(folder):
            folder = os.path.join(self.incident_dir, f"{name}_{n}")
            n += 1
        os.makedirs(folder)

        details = dict(details)
        playlist = details.pop("playlist", None)
        info = {
            "zeit": time.strftime("%Y-%m-%d %H:%M:%S"),
            "seite": site,
            "art": kind,
            "beschreibung": KIND_TEXT.get(kind, kind),
            "url": page_url,
            "details": details,
            "umgebung": self.environment,
        }
        if extra:
            info.update(extra)
        text = json.dumps(info, ensure_ascii=False, indent=2)
        if len(text) > MAX_DETAILS_CHARS:
            text = text[:MAX_DETAILS_CHARS] + "\n... (gekürzt)"
        with open(os.path.join(folder, "info.json"), "w", encoding="utf-8") as f:
            f.write(text)
        if playlist:
            with open(os.path.join(folder, "playlist.m3u8"), "w", encoding="utf-8") as f:
                f.write(str(playlist)[:MAX_DETAILS_CHARS])
        if requests:
            with open(os.path.join(folder, "anfragen.tsv"), "w", encoding="utf-8") as f:
                f.write("zeit\tergebnis\ttyp\turl\n")
                for r in requests:
                    f.write("\t".join(r) + "\n")
        self._prune_incidents()
        return folder

    def _prune_incidents(self):
        folders = sorted(os.listdir(self.incident_dir))
        for old in folders[:-MAX_INCIDENTS]:
            shutil.rmtree(os.path.join(self.incident_dir, old), ignore_errors=True)

    # --- reading (start page, shield dialog) ---
    def counts(self) -> dict:
        """How often video ads were handled, per site (start page statistics)."""
        result = {"twitch": 0, "youtube": 0, "southpark": 0, "netflix": 0}
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return result
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("kind") not in ("ad-blocked", "ads-removed", "dai-blocked", "masked"):
                continue
            site = str(e.get("site", ""))
            for key in result:
                if key in site:
                    result[key] += 1
        return result

    def recent_entries(self, limit: int = 200) -> list[dict]:
        if not os.path.exists(self.log_file):
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()[-limit:]
        except OSError:
            return []
        entries = []
        for line in reversed(lines):
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
        return entries
