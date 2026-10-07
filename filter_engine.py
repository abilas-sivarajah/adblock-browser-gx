"""
Filter Engine for AdBlock Browser.
Uses the high-performance Rust-based 'adblock' engine by Brave.
Manages downloading, updating, caching, and querying filter rules (EasyList, EasyPrivacy, German lists)
plus the bundled site fixes (site_fixes.txt).
"""

import os
import json
import time
import logging
import threading
import urllib.request
import adblock

logger = logging.getLogger("FilterEngine")

SITE_FIXES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_fixes.txt")

DEFAULT_FILTER_SOURCES = [
    {
        "name": "EasyList",
        "url": "https://easylist.to/easylist/easylist.txt",
        "filename": "easylist.txt",
        "enabled": True
    },
    {
        "name": "EasyPrivacy",
        "url": "https://easylist.to/easylist/easyprivacy.txt",
        "filename": "easyprivacy.txt",
        "enabled": True
    },
    {
        "name": "EasyList Germany",
        "url": "https://easylist-downloads.adblockplus.org/easylistgermany.txt",
        "filename": "easylistgermany.txt",
        "enabled": True
    },
    {
        "name": "Peter Lowe Adservers",
        "url": "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=adblockplus&mimetype=plaintext",
        "filename": "peter_lowe.txt",
        "enabled": True
    }
]

# Fallback basic rules in case internet is down on initial launch
FALLBACK_RULES = """
! Basic built-in rules
||doubleclick.net^
||googlesyndication.com^
||google-analytics.com^
||adnxs.com^
||amazon-adsystem.com^
||outbrain.com^
||taboola.com^
||scorecardresearch.com^
||criteo.com^
||adservice.google.com^
||pagead2.googlesyndication.com^
||adcolony.com^
||chartbeat.com^
||facebook.com/tr/*
||quantserve.com^
||advertising.com^
||rubiconproject.com^
||pubmatic.com^
||moatads.com^
||smartadserver.com^
||hotjar.com^
||mouseflow.com^
||openx.net^
||casalemedia.com^
||adroll.com^
||adtechus.com^
||zedo.com^
||yieldmo.com^
||teads.tv^
||gemini.yahoo.com^
||exponential.com^
||conversantmedia.com^
##.adsbygoogle
##.ad-banner
##.ad_box
##.advertisement
##[id^="google_ads"]
##[class*="ad-container"]
"""

# WebView2 CoreWebView2WebResourceContext names (lower-cased) -> adblock-rust request types.
# Main-frame documents are handled separately (they are never blocked).
REQUEST_TYPE_MAP = {
    "document": "sub_frame",
    "stylesheet": "stylesheet",
    "image": "image",
    "media": "media",
    "font": "font",
    "script": "script",
    "xmlhttprequest": "xmlhttprequest",
    "fetch": "xmlhttprequest",
    "eventsource": "xmlhttprequest",
    "websocket": "websocket",
    "ping": "ping",
    "cspviolationreport": "csp_report",
    "texttrack": "other",
    "manifest": "other",
    "signedexchange": "other",
    "other": "other",
}

EMPTY_COSMETICS = {"hide_selectors": [], "style_selectors": {}, "exceptions": [], "generichide": True}


def host_of(url: str) -> str:
    clean = (url or "").lower()
    if "://" in clean:
        clean = clean.split("://", 1)[1]
    return clean.split("/", 1)[0].split(":", 1)[0]


class FilterEngine:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.filters_dir = os.path.join(data_dir, "filters")
        self.config_file = os.path.join(data_dir, "adblock_config.json")
        os.makedirs(self.filters_dir, exist_ok=True)

        self.lock = threading.Lock()
        self.engine: adblock.Engine = None
        self.is_loaded = False
        self.is_enabled = True
        self.ad_spoofing = False  # Twitch: report blocked ads as watched (site_scripts.py)

        # Whitelist and settings
        self.whitelist = set()
        self.total_blocked = 0
        self.recent_blocks = []  # list of dicts: {url, domain, type, time}
        self.max_recent_blocks = 200

        self._load_config()
        self.init_engine()

    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.whitelist = set(data.get("whitelist", []))
                    self.total_blocked = data.get("total_blocked", 0)
                    self.is_enabled = data.get("is_enabled", True)
                    self.ad_spoofing = bool(data.get("ad_spoofing", False))
            except Exception as e:
                logger.error(f"Error loading adblock config: {e}")

    def save_config(self):
        with self.lock:
            data = {
                "whitelist": sorted(self.whitelist),
                "total_blocked": self.total_blocked,
                "is_enabled": self.is_enabled,
                "ad_spoofing": self.ad_spoofing
            }
            try:
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving adblock config: {e}")

    def _read_site_fixes(self) -> str:
        """Bundled site fixes plus the optional personal rules file (browser_data/filters/user_rules.txt)."""
        texts = []
        for path in (SITE_FIXES_FILE, os.path.join(self.filters_dir, "user_rules.txt")):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    texts.append(f.read())
            except OSError as e:
                logger.warning(f"Could not read rules file {path}: {e}")
        return "\n".join(texts)

    def init_engine(self):
        """Initializes the adblock engine from cached files or fallback rules."""
        filter_texts = []
        for src in DEFAULT_FILTER_SOURCES:
            fpath = os.path.join(self.filters_dir, src["filename"])
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        filter_texts.append(f.read())
                except Exception as e:
                    logger.error(f"Error reading filter file {fpath}: {e}")

        if not filter_texts:
            filter_texts.append(FALLBACK_RULES)
            # Spawn background download if no cached files exist yet
            threading.Thread(target=self.update_filter_lists, daemon=True).start()

        self._compile_engine(filter_texts)

    def _compile_engine(self, filter_texts: list[str]):
        try:
            t0 = time.time()
            fs = adblock.FilterSet()
            for text in filter_texts + [self._read_site_fixes()]:
                if text.strip():
                    fs.add_filter_list(text)
            new_engine = adblock.Engine(filter_set=fs)
            with self.lock:
                self.engine = new_engine
                self.is_loaded = True
            logger.info(f"Adblock engine compiled in {time.time()-t0:.2f}s with {len(filter_texts)} lists + site fixes/user rules.")
        except Exception as e:
            logger.error(f"Failed to compile adblock engine: {e}")

    def update_filter_lists(self) -> bool:
        """Downloads/updates filter lists from sources and recompiles the engine.
        Returns True if at least one list could be downloaded."""
        logger.info("Starting filter lists update...")
        texts = []
        downloaded = 0
        for src in DEFAULT_FILTER_SOURCES:
            if not src.get("enabled", True):
                continue
            fpath = os.path.join(self.filters_dir, src["filename"])
            url = src["url"]
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 AdBlockBrowser/2.1"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    content = resp.read().decode("utf-8", errors="ignore")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                texts.append(content)
                downloaded += 1
                logger.info(f"Updated {src['name']} ({len(content)//1024} KB)")
            except Exception as e:
                logger.warning(f"Could not update {src['name']} from {url}: {e}")
                # Fallback to existing file if present
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            texts.append(f.read())
                    except Exception:
                        pass

        if texts:
            self._compile_engine(texts)
        return downloaded > 0

    def is_domain_whitelisted(self, domain_or_url: str) -> bool:
        clean = host_of(domain_or_url)
        if not clean:
            return False
        for w in self.whitelist:
            if clean == w or clean.endswith("." + w):
                return True
        return False

    def toggle_whitelist(self, domain_or_url: str) -> bool:
        clean = host_of(domain_or_url)
        if clean in self.whitelist:
            self.whitelist.remove(clean)
            is_now_whitelisted = False
        else:
            self.whitelist.add(clean)
            is_now_whitelisted = True
        self.save_config()
        return is_now_whitelisted

    def check_network(self, url: str, source_url: str, request_type: str) -> bool:
        """Returns True if request should be BLOCKED.
        request_type is an adblock-rust request type (see REQUEST_TYPE_MAP)."""
        if not self.is_enabled:
            return False
        engine = self.engine
        if not engine or not self.is_loaded:
            return False
        if not url.startswith(("http://", "https://", "ws://", "wss://")):
            return False

        # Check source domain whitelist
        if source_url and self.is_domain_whitelisted(source_url):
            return False

        try:
            res = engine.check_network_urls(url, source_url or url, request_type)
        except Exception as e:
            logger.debug(f"check_network error for {url}: {e}")
            return False
        if not res.matched:
            return False

        with self.lock:
            self.total_blocked += 1
            self.recent_blocks.append({
                "url": url,
                "domain": host_of(url),
                "type": request_type,
                "time": time.strftime("%H:%M:%S")
            })
            if len(self.recent_blocks) > self.max_recent_blocks:
                self.recent_blocks.pop(0)
        return True

    # --- Cosmetic filtering (element hiding) ---
    def get_cosmetic_rules(self, url: str) -> dict:
        """Site-specific hide rules for the given page URL plus the data needed
        to resolve generic class/id rules later (see get_generic_selectors)."""
        engine = self.engine
        if not self.is_enabled or not engine or not self.is_loaded:
            return dict(EMPTY_COSMETICS)
        if self.is_domain_whitelisted(url):
            return dict(EMPTY_COSMETICS)

        try:
            cr = engine.url_cosmetic_resources(url)
            return {
                "hide_selectors": list(cr.hide_selectors),
                "style_selectors": {k: list(v) for k, v in dict(cr.style_selectors).items()},
                "exceptions": list(cr.exceptions),
                "generichide": bool(cr.generichide),
            }
        except Exception as e:
            logger.debug(f"get_cosmetic_rules error for {url}: {e}")
            return dict(EMPTY_COSMETICS)

    def get_generic_selectors(self, classes: list[str], ids: list[str], exceptions: list[str]) -> list[str]:
        """Generic hide rules (e.g. '##.adsbygoogle') that apply to the given classes/ids."""
        engine = self.engine
        if not self.is_enabled or not engine or not self.is_loaded:
            return []
        try:
            return list(engine.hidden_class_id_selectors(classes, ids, set(exceptions)))
        except Exception as e:
            logger.debug(f"get_generic_selectors error: {e}")
            return []
