"""
Bookmarks and History Manager for AdBlock Browser.
Stores bookmarks and history in JSON format.
"""

import os
import json
import time
from datetime import datetime

class BookmarksHistoryManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.bookmarks_file = os.path.join(data_dir, "bookmarks.json")
        self.history_file = os.path.join(data_dir, "history.json")
        os.makedirs(data_dir, exist_ok=True)
        
        self.bookmarks = self._load_json(self.bookmarks_file, default=[
            {"title": "YouTube", "url": "https://www.youtube.com"},
            {"title": "Wikipedia", "url": "https://de.wikipedia.org"},
            {"title": "GitHub", "url": "https://github.com"},
            {"title": "Spiegel", "url": "https://www.spiegel.de"},
            {"title": "Heise Online", "url": "https://www.heise.de"}
        ])
        self.history = self._load_json(self.history_file, default=[])

    def _load_json(self, path: str, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return default
        return default

    def _save_json(self, path: str, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # --- Bookmarks ---
    def is_bookmarked(self, url: str) -> bool:
        norm = url.rstrip("/")
        return any(b["url"].rstrip("/") == norm for b in self.bookmarks)

    def add_bookmark(self, title: str, url: str):
        if not self.is_bookmarked(url):
            self.bookmarks.append({
                "title": title or url,
                "url": url,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            self._save_json(self.bookmarks_file, self.bookmarks)

    def remove_bookmark(self, url: str):
        norm = url.rstrip("/")
        self.bookmarks = [b for b in self.bookmarks if b["url"].rstrip("/") != norm]
        self._save_json(self.bookmarks_file, self.bookmarks)

    def toggle_bookmark(self, title: str, url: str) -> bool:
        if self.is_bookmarked(url):
            self.remove_bookmark(url)
            return False
        else:
            self.add_bookmark(title, url)
            return True

    def get_bookmarks(self):
        return list(self.bookmarks)

    # --- History ---
    def add_history(self, title: str, url: str):
        if not url or url.startswith(("about:", "data:", "qrc:")):
            return
        
        # Avoid duplicate consecutive entries
        if self.history and self.history[0].get("url") == url:
            self.history[0]["title"] = title or self.history[0].get("title", url)
            self.history[0]["time"] = datetime.now().strftime("%d.%m.%Y %H:%M")
            self._save_json(self.history_file, self.history)
            return

        self.history.insert(0, {
            "title": title or url,
            "url": url,
            "time": datetime.now().strftime("%d.%m.%Y %H:%M")
        })
        # Keep maximum 1000 history items
        if len(self.history) > 1000:
            self.history = self.history[:1000]
        self._save_json(self.history_file, self.history)

    def get_history(self, query: str = ""):
        if not query:
            return list(self.history)
        q = query.lower()
        return [
            h for h in self.history
            if q in h.get("title", "").lower() or q in h.get("url", "").lower()
        ]

    def clear_history(self):
        self.history = []
        self._save_json(self.history_file, self.history)
