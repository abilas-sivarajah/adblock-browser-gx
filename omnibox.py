"""
Address bar suggestions like in Chrome/Firefox: visited pages, bookmarks and earlier searches from the
history, inline completion of known sites ("net" -> "netflix.com") and live Google suggestions
(search terms and websites).
"""

import json
import re
import urllib.parse

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QPainter
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (QFrame, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate, QVBoxLayout,
                             QWidget)

import icons
import theme

SEARCH_URL = "https://www.google.com/search?q="
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
MAX_PAGES = 4          # visited pages / bookmarks
MAX_SEARCHES = 2       # earlier searches
MAX_ROWS = 8
ROW_HEIGHT = 34
ROW_ROLE = Qt.ItemDataRole.UserRole

# search result pages in the history become "earlier search" rows instead of page rows
SEARCH_HOSTS = re.compile(r"^(www\.)?(google\.[a-z.]+|duckduckgo\.com|bing\.com)$")


def search_url(query: str) -> str:
    return SEARCH_URL + urllib.parse.quote_plus(query)


def resolve(text: str) -> str:
    """What the address bar opens for the typed text: the address itself or a Google search."""
    text = text.strip()
    if text.startswith(("http://", "https://", "about:", "file://", "edge://")):
        return text
    if re.match(r"^(localhost|\d{1,3}(\.\d{1,3}){3})(:\d+)?(/.*)?$", text):
        return "http://" + text
    if "." in text and " " not in text:
        return "https://" + text
    return search_url(text)


def bare_url(url: str) -> str:
    """'https://www.netflix.com/browse/' -> 'netflix.com/browse' (how Chrome shows addresses)."""
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", url, flags=re.I)
    return re.sub(r"^www\.", "", s, flags=re.I).rstrip("/")


def search_query_of(url: str) -> str | None:
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if not SEARCH_HOSTS.match(p.hostname or "") or p.path not in ("/", "/search"):
        return None
    q = urllib.parse.parse_qs(p.query).get("q")
    return q[0].strip() if q and q[0].strip() else None


def collect_history(history: list, bookmarks: list):
    """History (newest first) -> {url: page}, {query: search} with visit counts and recency."""
    pages, searches = {}, {}
    for rank, h in enumerate(history):
        url = h.get("url", "")
        if not url.startswith(("http://", "https://")):
            continue
        query = search_query_of(url)
        if query:
            s = searches.setdefault(query.lower(), {"query": query, "count": 0, "rank": rank})
            s["count"] += 1
            continue
        p = pages.setdefault(url, {"url": url, "title": h.get("title") or "", "count": 0, "rank": rank,
                                   "bookmark": False})
        p["count"] += 1
    for b in bookmarks:
        url = b.get("url", "")
        if url.startswith(("http://", "https://")):
            p = pages.setdefault(url, {"url": url, "title": b.get("title") or "", "count": 0,
                                       "rank": len(history), "bookmark": False})
            p["bookmark"] = True
    return pages, searches


def _weight(page: dict) -> int:
    return page["count"] + (5 if page["bookmark"] else 0)


def match_pages(pages: dict, text: str) -> list:
    words = text.lower().split()
    if not words:
        return []
    scored = []
    for p in pages.values():
        bare = bare_url(p["url"]).lower()
        hay = bare + " " + p["title"].lower()
        if not all(w in hay for w in words):
            continue
        if bare.startswith(words[0]):
            score = 3
        elif any(tok.startswith(words[0]) for tok in re.split(r"[\W_]+", hay)):
            score = 2
        else:
            score = 1
        scored.append((-score, -_weight(p), p["rank"], p["url"], p))
    scored.sort(key=lambda s: s[:4])
    return [s[4] for s in scored]


def match_searches(searches: dict, text: str) -> list:
    t = text.lower().strip()
    hits = [s for s in searches.values() if s["query"].lower().startswith(t) and s["query"].lower() != t]
    hits.sort(key=lambda s: (-s["count"], s["rank"]))
    return hits


def inline_completion(pages: dict, typed: str):
    """Known site that starts with the typed text -> (completed text, url to open, title) or None."""
    t = typed.lower()
    if not t or any(c in t for c in " /:?#"):
        return None
    hosts = {}
    for p in pages.values():
        parts = urllib.parse.urlsplit(p["url"])
        netloc = parts.netloc.lower()
        shown = netloc if t.startswith("www.") else re.sub(r"^www\.", "", netloc)
        if not shown.startswith(t) or shown == t:
            continue
        h = hosts.setdefault(shown, {"weight": 0, "rank": p["rank"], "best": p, "title": ""})
        h["weight"] += _weight(p)
        h["rank"] = min(h["rank"], p["rank"])
        if _weight(p) > _weight(h["best"]):
            h["best"] = p
        if parts.path in ("", "/") and p["title"]:
            h["title"] = p["title"]    # title of the site's front page
    if not hosts:
        return None
    shown, h = min(hosts.items(), key=lambda kv: (-kv[1]["weight"], kv[1]["rank"], len(kv[0])))
    parts = urllib.parse.urlsplit(h["best"]["url"])
    return typed + shown[len(typed):], f"{parts.scheme}://{parts.netloc}/", h["title"]


def google_rows(data, text: str) -> list:
    """Rows from the Google suggest answer (client=chrome: queries and NAVIGATION = websites)."""
    try:
        suggestions, descriptions = data[1], data[2]
        types = data[4].get("google:suggesttype", []) if len(data) > 4 else []
    except (IndexError, KeyError, TypeError, AttributeError):
        return []
    rows = []
    for i, s in enumerate(suggestions):
        if not isinstance(s, str) or s.strip().lower() == text.strip().lower():
            continue
        desc = descriptions[i] if i < len(descriptions) and isinstance(descriptions[i], str) else ""
        if i < len(types) and types[i] == "NAVIGATION":
            rows.append(_row("globe", bare_url(s), desc, s, s))
        else:
            rows.append(_row("search", s, "Google-Suche", search_url(s), s))
    return rows


def _row(icon, main, sub, target, fill, sub_is_url=False, select_from=None):
    return {"icon": icon, "main": main, "sub": sub, "target": target, "fill": fill,
            "sub_is_url": sub_is_url, "select_from": select_from}


class _RowDelegate(QStyledItemDelegate):
    def __init__(self, omnibox):
        super().__init__(omnibox.popup)
        self.ob = omnibox
        self._pixmaps = {}

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), ROW_HEIGHT)

    def _pixmap(self, name, color):
        key = (name, color)
        if key not in self._pixmaps:
            self._pixmaps[key] = icons.pixmap(name, color, 16)
        return self._pixmaps[key]

    def paint(self, p, option, index):
        row = index.data(ROW_ROLE)
        if not row:
            return
        accent = self.ob.accent
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = option.rect.adjusted(2, 1, -2, -1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected or option.state & QStyle.StateFlag.State_MouseOver:
            bg = QColor(accent)
            bg.setAlphaF(0.24 if selected else 0.10)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(r, 8, 8)
        p.drawPixmap(r.left() + 10, r.center().y() - 7, self._pixmap(row["icon"], accent if selected else theme.MUTED))

        fm = option.fontMetrics
        x, right = r.left() + 36, r.right() - 12
        avail = right - x
        main = fm.elidedText(row["main"], Qt.TextElideMode.ElideRight, int(avail * 0.62) if row["sub"] else avail)
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRect(x, r.top(), avail, r.height()), Qt.AlignmentFlag.AlignVCenter, main)
        if row["sub"]:
            x += fm.horizontalAdvance(main)
            sub = fm.elidedText(" – " + row["sub"], Qt.TextElideMode.ElideRight, right - x)
            p.setPen(QColor(accent if row["sub_is_url"] else theme.MUTED))
            p.drawText(QRect(x, r.top(), right - x, r.height()), Qt.AlignmentFlag.AlignVCenter, sub)
        p.restore()


class _Popup(QWidget):
    """Top-level window: WebView2 pages are native windows and would cover a normal child widget."""

    def __init__(self, window):
        super().__init__(window, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QFrame(self)
        box.setObjectName("omniBox")
        outer.addWidget(box)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 6, 6, 6)
        self.list = QListWidget(box)
        self.list.setObjectName("omniList")
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setMouseTracking(True)
        self.list.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(self.list)


class Omnibox(QObject):
    """Suggestion list for the address bar. Enter/click on a row emits open_url."""
    open_url = pyqtSignal(str)

    def __init__(self, line_edit, bm_manager, window):
        super().__init__(line_edit)
        self.edit = line_edit
        self.bm = bm_manager
        self.window = window
        self.accent = theme.ACCENTS[0][1]
        self.popup = _Popup(window)
        self.popup.list.setItemDelegate(_RowDelegate(self))
        self.popup.list.itemClicked.connect(lambda item: self._open(item.data(ROW_ROLE)))
        self._typed = ""        # what the user typed, without the inline completion
        self._deleting = False  # last key was Backspace/Delete/Cut
        self._history = None    # (pages, searches), collected once per editing session
        self._local = []        # default row + history rows
        self._google = []
        self._reply = None
        self.net = QNetworkAccessManager(self)
        self._fetch_timer = QTimer(self)
        self._fetch_timer.setSingleShot(True)
        self._fetch_timer.setInterval(120)
        self._fetch_timer.timeout.connect(self._fetch)
        line_edit.textEdited.connect(self._on_text_edited)
        line_edit.installEventFilter(self)
        window.installEventFilter(self)

    def set_accent(self, accent: str):
        self.accent = accent
        self.popup.list.viewport().update()

    # ------------------------------------------------------------------ typing
    def _on_text_edited(self, text: str):
        self._typed = text
        if not text.strip():
            self.hide()
            return
        if self._history is None:
            self._history = collect_history(self.bm.history, self.bm.bookmarks)
        pages, searches = self._history

        completion = None
        # like Chrome: no completion right after deleting, otherwise Backspace could never remove it
        if not self._deleting and self.edit.cursorPosition() == len(text):
            completion = inline_completion(pages, text)
        if completion:
            full, target, title = completion
            self.edit.setText(full)
            self.edit.setSelection(len(text), len(full) - len(text))
            self.edit.setModified(True)   # setText() resets it; MainWindow keeps edited text
            default = _row("history", full, title, target, full, select_from=len(text))
        else:
            target = resolve(text)
            if target.startswith(SEARCH_URL):
                default = _row("search", text.strip(), "Google-Suche", target, text)
            else:
                default = _row("globe", text.strip(), "", target, text)

        rows = [default]
        pages_left = MAX_PAGES
        for p in match_pages(pages, text):
            if pages_left == 0:
                break
            if p["url"].rstrip("/") == default["target"].rstrip("/"):
                continue
            pages_left -= 1
            icon = "bookmark" if p["bookmark"] else "history"
            title = p["title"].strip()
            shown = bare_url(p["url"])
            if title and title.lower() != shown.lower():
                rows.append(_row(icon, title, shown, p["url"], p["url"], sub_is_url=True))
            else:
                rows.append(_row(icon, shown, "", p["url"], p["url"]))
        for s in match_searches(searches, text)[:MAX_SEARCHES]:
            rows.append(_row("history", s["query"], "Frühere Suche", search_url(s["query"]), s["query"]))
        self._local = rows

        # keep earlier Google rows that still fit until the new answer arrives
        t = text.strip().lower()
        self._google = [g for g in self._google if g["fill"].lower().startswith(t) and g["fill"].lower() != t]
        self._show(select_target=None)
        self._fetch_timer.start()

    def _rows(self) -> list:
        rows = list(self._local)
        seen = {r["target"] for r in rows} | {r["fill"].strip().lower() for r in rows}
        for g in self._google:
            if g["target"] not in seen and g["fill"].strip().lower() not in seen:
                rows.append(g)
        return rows[:MAX_ROWS]

    def _show(self, select_target):
        lst = self.popup.list
        rows = self._rows()
        lst.clear()
        select = 0
        for i, row in enumerate(rows):
            item = QListWidgetItem()
            item.setData(ROW_ROLE, row)
            lst.addItem(item)
            if select_target and row["target"] == select_target:
                select = i
        lst.setCurrentRow(select)
        pos = self.edit.mapToGlobal(QPoint(0, self.edit.height() + 5))
        self.popup.setGeometry(pos.x(), pos.y(), self.edit.width(), len(rows) * ROW_HEIGHT + 14)
        self.popup.show()
        self.popup.raise_()

    def hide(self):
        self.popup.hide()
        self._fetch_timer.stop()
        if self._reply is not None:
            reply, self._reply = self._reply, None
            reply.abort()
        self._history = None
        self._google = []

    # ------------------------------------------------------------------ Google suggestions
    def _fetch(self):
        text = self._typed.strip()
        # full addresses are not sent to Google (e.g. when editing the current URL)
        if not text or len(text) > 120 or re.match(r"^[a-z][a-z0-9+.-]*:", text, flags=re.I):
            return
        if self._reply is not None:
            reply, self._reply = self._reply, None
            reply.abort()
        query = urllib.parse.urlencode({"client": "chrome", "hl": "de", "q": text})
        req = QNetworkRequest(QUrl(f"{SUGGEST_URL}?{query}"))
        req.setTransferTimeout(3000)
        reply = self.net.get(req)
        self._reply = reply
        reply.finished.connect(lambda r=reply, t=text: self._on_reply(r, t))

    def _on_reply(self, reply, text: str):
        reply.deleteLater()
        if reply is not self._reply:
            return
        self._reply = None
        if reply.error() != QNetworkReply.NetworkError.NoError or not self.popup.isVisible():
            return
        if self._typed.strip() != text:
            return
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except ValueError:
            return
        current = self.popup.list.currentItem()
        selected = current.data(ROW_ROLE)["target"] if current else None
        self._google = google_rows(data, text)
        self._show(select_target=selected)

    # ------------------------------------------------------------------ keys, clicks, closing
    def _move(self, delta: int):
        lst = self.popup.list
        i = max(0, min(lst.count() - 1, lst.currentRow() + delta))
        lst.setCurrentRow(i)
        row = lst.item(i).data(ROW_ROLE)
        self.edit.setText(row["fill"])
        if row["select_from"] is not None:
            self.edit.setSelection(row["select_from"], len(row["fill"]) - row["select_from"])
        self.edit.setModified(True)

    def _open(self, row):
        if not row:
            return
        self.hide()
        self.edit.setText(row["fill"])
        self.open_url.emit(row["target"])

    def eventFilter(self, obj, ev):
        t = ev.type()
        if obj is self.edit:
            visible = self.popup.isVisible()
            if t == QEvent.Type.KeyPress:
                self._deleting = (ev.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)
                                  or ev.matches(QKeySequence.StandardKey.Cut))
            if t == QEvent.Type.ShortcutOverride and visible and ev.key() == Qt.Key.Key_Escape:
                ev.accept()      # Esc closes the list instead of the window-wide Esc shortcut
                return True
            if t == QEvent.Type.KeyPress and visible:
                key = ev.key()
                if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    self._move(1 if key == Qt.Key.Key_Down else -1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    item = self.popup.list.currentItem()
                    if item is not None:
                        self._open(item.data(ROW_ROLE))
                        return True
                if key == Qt.Key.Key_Escape:
                    self.hide()
                    self.edit.setText(self._typed)
                    self.edit.setModified(True)
                    return True
            if t == QEvent.Type.FocusOut and not self.popup.underMouse():
                self.hide()
        elif obj is self.window and t in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowDeactivate,
                                          QEvent.Type.Hide):
            self.hide()
        return False
