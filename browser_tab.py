"""
BrowserTab component for AdBlock Browser using Microsoft Edge WebView2.
Supports Widevine DRM, PlayReady, H.264, AAC, 4K hardware acceleration,
and Brave Rust-based request & cosmetic ad blocking.
"""

import os
import json
import time
import ctypes
import logging
from collections import deque
import clr
import webview
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QFrame
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QWindow, QKeySequence, QShortcut

# The WebView2 .NET assemblies ship with pywebview.
WV2_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(webview.__file__)), "lib")

clr.AddReference("System.Windows.Forms")
clr.AddReference(os.path.join(WV2_LIB_DIR, "Microsoft.Web.WebView2.WinForms.dll"))
clr.AddReference(os.path.join(WV2_LIB_DIR, "Microsoft.Web.WebView2.Core.dll"))

import System
from System.Reflection import BindingFlags
import Microsoft.Web.WebView2.WinForms as WV2
import Microsoft.Web.WebView2.Core as WVC
from filter_engine import REQUEST_TYPE_MAP, host_of
from cosmetic_filter import COSMETIC_BRIDGE_SCRIPT, build_cosmetic_css
from site_scripts import build_site_scripts
from start_page import START_HOST, START_URL, is_start_page, write_start_page

logger = logging.getLogger("BrowserTab")

VK_TAB, VK_SHIFT, VK_CONTROL, VK_MENU, VK_HOME, VK_F11 = 0x09, 0x10, 0x11, 0x12, 0x24, 0x7A

# Browser shortcuts that WebView2 would otherwise swallow while the page has keyboard focus.
# (virtual key, ctrl, shift, alt) -> action name handled by MainWindow.handle_shortcut
PAGE_SHORTCUTS = {
    (ord("T"), True, False, False): "new_tab",
    (ord("W"), True, False, False): "close_tab",
    (VK_TAB, True, False, False): "next_tab",
    (VK_TAB, True, True, False): "prev_tab",
    (ord("L"), True, False, False): "focus_address",
    (ord("D"), False, False, True): "focus_address",
    (ord("D"), True, False, False): "bookmark",
    (ord("H"), True, False, False): "history",
    (ord("B"), True, False, False): "toggle_bookmarks_bar",
    (VK_HOME, False, False, True): "home",
    (VK_F11, False, False, False): "fullscreen",
}


def _key_down(vk: int) -> bool:
    return bool(ctypes.windll.user32.GetKeyState(vk) & 0x8000)


class BrowserTab(QWidget):
    title_changed = pyqtSignal(str)
    url_changed = pyqtSignal(str)
    load_progress = pyqtSignal(int)
    blocked_count_changed = pyqtSignal(int)
    new_tab_requested = pyqtSignal(str)
    shortcut_pressed = pyqtSignal(str)
    fullscreen_requested = pyqtSignal(bool)
    close_requested = pyqtSignal()

    def __init__(self, filter_engine, parent=None, ad_logger=None):
        super().__init__(parent)
        self.filter_engine = filter_engine
        self.ad_logger = ad_logger
        # last network requests of this tab, written into ad-log incidents
        self.recent_requests = deque(maxlen=500)
        self._ad_log_times = deque()     # rate limit: pages can post ad events themselves
        self._last_incident = 0.0
        self._manual_incident = None     # (folder, time) waiting for the page's details
        self._dai_logged_for = None
        self.blocked_count = 0
        self.is_ready = False
        self.pending_url = None
        self.current_url_str = ""
        self.current_title_str = "Neuer Tab"
        self._nav_uri = None
        self._cosmetic = None
        self._site_script_tasks = []
        self._request_log = os.environ.get("ADBLOCK_REQUEST_LOG")
        self.start_page_dir = os.path.join(filter_engine.data_dir, "startpage")

        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 1. Find Bar (hidden by default)
        self.find_bar = self.create_find_bar()
        self.find_bar.hide()
        self.layout.addWidget(self.find_bar)

        # 2. Native WinForms WebView2 Control
        props = WV2.CoreWebView2CreationProperties()
        props.UserDataFolder = os.path.join(self.filter_engine.data_dir, "wv2_profile")
        browser_args = []
        debug_port = os.environ.get("ADBLOCK_REMOTE_DEBUG_PORT")
        if debug_port:
            browser_args.append(f"--remote-debugging-port={debug_port}")
        if os.environ.get("ADBLOCK_HIDDEN_WINDOW"):
            # keep rendering although the window is off-screen, and stay silent
            browser_args += ["--mute-audio", "--disable-renderer-backgrounding",
                             "--disable-backgrounding-occluded-windows",
                             "--disable-features=CalculateNativeWinOcclusion"]
        if browser_args:
            props.AdditionalBrowserArguments = " ".join(browser_args)

        self.wv = WV2.WebView2()
        self.wv.CreationProperties = props
        self.wv.CreateControl()
        hwnd = int(self.wv.Handle.ToInt64())
        self.qwin = QWindow.fromWinId(hwnd)
        self.container = QWidget.createWindowContainer(self.qwin, self)
        self.layout.addWidget(self.container)

        # 3. Setup CoreWebView2 Initialization
        self.wv.CoreWebView2InitializationCompleted += self.on_core_init_completed
        self.wv.EnsureCoreWebView2Async(None)

    def create_find_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet("""
            QFrame {
                background: #1e293b;
                border-bottom: 1px solid #334155;
                padding: 6px 12px;
            }
            QLineEdit {
                background: #0f172a;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton {
                background: #334155;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: #475569;
            }
            QLabel {
                color: #94a3b8;
            }
        """)
        h_layout = QHBoxLayout(bar)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(8)

        lbl = QLabel("Suchen:")
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Auf der Seite suchen...")
        self.find_input.returnPressed.connect(self.find_next)

        btn_prev = QPushButton("▲")
        btn_prev.setToolTip("Vorheriges Vorkommnis")
        btn_prev.clicked.connect(self.find_prev)

        btn_next = QPushButton("▼")
        btn_next.setToolTip("Nächstes Vorkommnis")
        btn_next.clicked.connect(self.find_next)

        btn_close = QPushButton("✕")
        btn_close.setToolTip("Suchleiste schließen (Esc)")
        btn_close.clicked.connect(self.hide_find_bar)

        esc = QShortcut(QKeySequence("Escape"), bar, self.hide_find_bar)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        h_layout.addWidget(lbl)
        h_layout.addWidget(self.find_input)
        h_layout.addWidget(btn_prev)
        h_layout.addWidget(btn_next)
        h_layout.addWidget(btn_close)

        return bar

    def on_core_init_completed(self, sender, args):
        if not args.IsSuccess:
            logger.error(f"WebView2 initialization failed: {args.InitializationException}")
            return
        self.is_ready = True
        core = self.wv.CoreWebView2
        if self.ad_logger is not None:
            self.ad_logger.environment.setdefault("webview2", core.Environment.BrowserVersionString)

        # Configure settings
        core.Settings.IsStatusBarEnabled = False
        core.Settings.AreDevToolsEnabled = True

        # Start page with a real origin (see start_page.START_HOST)
        os.makedirs(self.start_page_dir, exist_ok=True)
        core.SetVirtualHostNameToFolderMapping(
            START_HOST, self.start_page_dir, WVC.CoreWebView2HostResourceAccessKind.Deny)

        # Hook resource requested for ad-blocking
        core.AddWebResourceRequestedFilter("*", WVC.CoreWebView2WebResourceContext.All)
        core.WebResourceRequested += self.on_resource_requested

        # Hook navigation and title events
        core.SourceChanged += self.on_source_changed
        core.DocumentTitleChanged += self.on_title_changed
        core.NavigationStarting += self.on_nav_starting
        core.NavigationCompleted += self.on_nav_completed
        core.NewWindowRequested += self.on_new_window
        core.ContainsFullScreenElementChanged += self.on_fullscreen_element_changed
        core.WindowCloseRequested += self.on_window_close_requested
        core.ProcessFailed += self.on_process_failed

        # Element hiding: page reports its classes/ids, we answer with CSS
        core.WebMessageReceived += self.on_web_message
        core.AddScriptToExecuteOnDocumentCreatedAsync(COSMETIC_BRIDGE_SCRIPT)
        # Twitch / YouTube video-ad scripts
        self.refresh_site_scripts()

        self._hook_accelerator_keys()

        # Handle initial pending load
        if self.pending_url:
            u = self.pending_url
            self.pending_url = None
            self.load(u)

    def refresh_site_scripts(self):
        """(Re)registers the Twitch/YouTube scripts with the current shield settings.
        Takes effect for documents loaded afterwards."""
        if not self.is_ready:
            return
        core = self.wv.CoreWebView2
        for task in self._site_script_tasks:
            # registered at startup, so these tasks are long finished - .Result does not block
            if task.IsCompleted and not task.IsFaulted:
                core.RemoveScriptToExecuteOnDocumentCreated(task.Result)
        fe = self.filter_engine
        self._site_script_tasks = [core.AddScriptToExecuteOnDocumentCreatedAsync(js)
                                   for js in build_site_scripts(fe.is_enabled, fe.whitelist)]

    def _hook_accelerator_keys(self):
        # The WinForms control keeps its CoreWebView2Controller private; we need its
        # AcceleratorKeyPressed event to see browser shortcuts while the page has focus.
        try:
            field = clr.GetClrType(WV2.WebView2).GetField(
                "_coreWebView2Controller", BindingFlags.NonPublic | BindingFlags.Instance)
            controller = field.GetValue(self.wv)
            controller.AcceleratorKeyPressed += self.on_accelerator_key
        except Exception as e:
            logger.warning(f"Keyboard shortcuts inside pages unavailable: {e}")

    def on_accelerator_key(self, sender, args):
        if args.KeyEventKind not in (WVC.CoreWebView2KeyEventKind.KeyDown,
                                     WVC.CoreWebView2KeyEventKind.SystemKeyDown):
            return
        key = (int(args.VirtualKey), _key_down(VK_CONTROL), _key_down(VK_SHIFT), _key_down(VK_MENU))
        action = PAGE_SHORTCUTS.get(key)
        if not action:
            return
        args.Handled = True
        if args.PhysicalKeyStatus.WasKeyDown:
            return  # auto-repeat
        # Run outside the WebView2 callback (closing a tab disposes this very control)
        QTimer.singleShot(0, lambda: self.shortcut_pressed.emit(action))

    def on_resource_requested(self, sender, args):
        uri = args.Request.Uri
        context = args.ResourceContext.ToString().lower()
        if context == "document" and uri == self._nav_uri:
            return  # the main-frame navigation itself is never blocked

        req_type = REQUEST_TYPE_MAP.get(context, "other")
        blocked = self.filter_engine.check_network(uri, sender.Source, req_type)
        self.recent_requests.append((time.strftime("%H:%M:%S"), "BLOCK" if blocked else "erlaubt", req_type, uri))
        if blocked and "dai.google.com/ondemand/" in uri and self._dai_logged_for != self._nav_uri and self.ad_logger:
            self._dai_logged_for = self._nav_uri
            self.ad_logger.event(host_of(sender.Source), "dai-blocked", sender.Source,
                                 {"summary": "werbefreier Original-Stream wird genutzt"})
        if self._request_log:
            with open(self._request_log, "a", encoding="utf-8") as f:
                f.write(f"{'BLOCK' if blocked else 'allow'}\t{req_type}\t{uri}\n")
        if not blocked:
            return

        empty = System.IO.MemoryStream()
        args.Response = sender.Environment.CreateWebResourceResponse(empty, 403, "Blocked by AdBlock", "")
        self.blocked_count += 1
        self.blocked_count_changed.emit(self.blocked_count)

    def on_web_message(self, sender, args):
        source = args.Source
        if not source.startswith(("http://", "https://")) or is_start_page(source):
            return
        try:
            msg = json.loads(args.WebMessageAsJson)
        except ValueError:
            return
        if not isinstance(msg, dict):
            return

        kind = msg.get("type")
        if kind == "adblock-init":
            self._cosmetic = self.filter_engine.get_cosmetic_rules(source)
            self._post_css(build_cosmetic_css(self._cosmetic["hide_selectors"],
                                              self._cosmetic["style_selectors"]))
        elif kind == "adblock-classes":
            rules = self._cosmetic
            if not rules or rules["generichide"]:
                return
            classes = [c for c in msg.get("classes", []) if isinstance(c, str)]
            ids = [i for i in msg.get("ids", []) if isinstance(i, str)]
            selectors = self.filter_engine.get_generic_selectors(classes, ids, rules["exceptions"])
            self._post_css(build_cosmetic_css(selectors))
        elif kind == "adblock-ad-event":
            self._handle_ad_event(source, msg)

    def _handle_ad_event(self, source: str, msg: dict):
        if not self.ad_logger:
            return
        now = time.time()
        while self._ad_log_times and now - self._ad_log_times[0] > 60:
            self._ad_log_times.popleft()
        if len(self._ad_log_times) >= 20:
            return
        self._ad_log_times.append(now)

        site = str(msg.get("site") or host_of(source))[:30]
        event = str(msg.get("kind") or "")[:40]
        details = msg.get("details") if isinstance(msg.get("details"), dict) else {}
        if event == "manual-details":
            if self._manual_incident and now - self._manual_incident[1] < 15:
                try:
                    with open(os.path.join(self._manual_incident[0], "seite.json"), "w", encoding="utf-8") as f:
                        f.write(json.dumps(details, ensure_ascii=False, indent=2)[:200_000])
                except OSError as e:
                    logger.debug(f"Could not write page details: {e}")
                self._manual_incident = None
            return

        folder = self.ad_logger.event(site, event, source, details, requests=list(self.recent_requests),
                                      with_incident=now - self._last_incident >= 30)
        if folder:
            self._last_incident = now
            self.capture_screenshot(os.path.join(folder, "screenshot.png"))

    def report_ad_manually(self):
        """User says "there is an ad here": incident with requests + screenshot, then the page
        is asked for its player/blocker state (arrives as 'manual-details')."""
        if not self.ad_logger:
            return None
        url = self.current_url_str
        folder = self.ad_logger.event(host_of(url) or "seite", "manual", url, {"summary": self.current_title_str},
                                      requests=list(self.recent_requests))
        if folder:
            self._manual_incident = (folder, time.time())
            self.capture_screenshot(os.path.join(folder, "screenshot.png"))
            if self.is_ready:
                self.wv.CoreWebView2.PostWebMessageAsJson(json.dumps({"type": "adblock-collect"}))
        return folder

    def capture_screenshot(self, path: str):
        if not self.is_ready:
            return
        try:
            stream = System.IO.FileStream(path, System.IO.FileMode.Create)
            task = self.wv.CoreWebView2.CapturePreviewAsync(WVC.CoreWebView2CapturePreviewImageFormat.Png, stream)
        except Exception as e:
            logger.debug(f"Screenshot failed: {e}")
            return

        def finish():
            if task.IsCompleted:
                stream.Dispose()
            else:
                QTimer.singleShot(100, finish)
        QTimer.singleShot(100, finish)

    def _post_css(self, css: str):
        if css and self.is_ready:
            self.wv.CoreWebView2.PostWebMessageAsJson(json.dumps({"type": "adblock-css", "css": css}))

    def on_source_changed(self, sender, args):
        new_url = sender.Source
        if is_start_page(new_url):
            new_url = "about:start"
        if new_url != self.current_url_str:
            self.current_url_str = new_url
            self.url_changed.emit(new_url)

    def on_title_changed(self, sender, args):
        new_title = "Neuer Tab" if self.current_url_str == "about:start" else sender.DocumentTitle
        if new_title:
            self.current_title_str = new_title
            self.title_changed.emit(new_title)

    def on_nav_starting(self, sender, args):
        self._nav_uri = args.Uri
        self._cosmetic = None
        self.blocked_count = 0
        self.blocked_count_changed.emit(0)
        self.load_progress.emit(30)

    def on_nav_completed(self, sender, args):
        self.load_progress.emit(100)

    def on_new_window(self, sender, args):
        # Open popups or target="_blank" in a new tab inside the browser.
        # Windows the user did not click for (ad popups) are dropped.
        args.Handled = True
        target_uri = args.Uri
        if not args.IsUserInitiated:
            logger.info(f"Blocked popup: {target_uri}")
            return
        if target_uri:
            self.new_tab_requested.emit(target_uri)

    def on_fullscreen_element_changed(self, sender, args):
        self.fullscreen_requested.emit(bool(sender.ContainsFullScreenElement))

    def on_window_close_requested(self, sender, args):
        # page called window.close() (e.g. a login popup that is done)
        QTimer.singleShot(0, self.close_requested.emit)

    def on_process_failed(self, sender, args):
        kind = args.ProcessFailedKind
        logger.warning(f"WebView2 process failed: {kind}")
        if kind == WVC.CoreWebView2ProcessFailedKind.RenderProcessExited:
            QTimer.singleShot(500, self.reload)

    def load(self, url: str):
        if not url:
            return
        if url == "about:start":
            self.load_start_page()
            return
        if not self.is_ready:
            self.pending_url = url
            return
        try:
            self.wv.CoreWebView2.Navigate(url)
        except Exception as e:
            logger.warning(f"Cannot navigate to {url!r}: {e}")

    def load_start_page(self):
        self.current_title_str = "Neuer Tab"
        self.title_changed.emit("Neuer Tab")
        if not self.is_ready:
            self.pending_url = "about:start"
            return
        write_start_page(self.start_page_dir, self.filter_engine.total_blocked)
        self.wv.CoreWebView2.Navigate(START_URL)

    def back(self):
        if self.is_ready and self.wv.CanGoBack:
            self.wv.GoBack()

    def forward(self):
        if self.is_ready and self.wv.CanGoForward:
            self.wv.GoForward()

    def reload(self, bypass_cache: bool = False):
        if not self.is_ready:
            return
        if bypass_cache:
            self.wv.CoreWebView2.CallDevToolsProtocolMethodAsync("Page.reload", '{"ignoreCache": true}')
        else:
            self.wv.Reload()

    def stop(self):
        if self.is_ready:
            self.wv.Stop()

    def set_zoom(self, factor: float):
        if self.is_ready:
            self.wv.ZoomFactor = factor

    def get_zoom(self) -> float:
        if self.is_ready:
            return float(self.wv.ZoomFactor)
        return 1.0

    def open_devtools(self):
        if self.is_ready:
            self.wv.CoreWebView2.OpenDevToolsWindow()

    def focus_page(self):
        if self.is_ready:
            self.wv.Focus()

    def dispose(self):
        """Releases the WebView2 controller (stops audio/video and frees the renderer)."""
        self.is_ready = False
        try:
            self.wv.Dispose()
        except Exception as e:
            logger.debug(f"WebView2 dispose failed: {e}")

    # --- Find in Page ---
    def show_find_bar(self):
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find_bar(self):
        self.find_bar.hide()

    def find_next(self):
        self._find(backwards=False)

    def find_prev(self):
        self._find(backwards=True)

    def _find(self, backwards: bool):
        text = self.find_input.text()
        if text and self.is_ready:
            # JavaScript window.find(aString, aCaseSensitive, aBackwards, aWrapAround)
            js = f"window.find({json.dumps(text)}, false, {json.dumps(backwards)}, true);"
            self.wv.CoreWebView2.ExecuteScriptAsync(js)
