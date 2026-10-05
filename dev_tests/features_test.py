"""Hidden-window feature test for the Claude copy of the browser (no focus, off-screen, muted)."""
import json, os, subprocess, sys, time, urllib.request
from websockets.sync.client import connect

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(SCRATCH, exist_ok=True)
PORT = 9333
NEWS = sys.argv[1] if len(sys.argv) > 1 else "https://www.heise.de/"


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()


def kill():
    ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*main.py*' } | "
       "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    for _ in range(20):
        if ps("(Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" | Where-Object { $_.CommandLine -like '*dev_tests*testdata*' }).Count") in ("", "0"):
            return
        time.sleep(0.5)


def pages():
    try:
        return [t for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2)) if t["type"] == "page"]
    except Exception:
        return []


class Page:
    def __init__(self, target):
        self.ws = connect(target["webSocketDebuggerUrl"], max_size=None)
        self.i = 0

    def call(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv(timeout=60))
            if m.get("id") == self.i:
                return m.get("result", m.get("error"))

    def ev(self, expr, gesture=False):
        r = self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True, userGesture=gesture)
        return r.get("result", {}).get("value", r)


def wait_for(pred, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = pred()
        if v:
            return v
        time.sleep(0.5)
    return None


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


kill()
env = dict(os.environ, ADBLOCK_REMOTE_DEBUG_PORT=str(PORT), ADBLOCK_HIDDEN_WINDOW="1", ADBLOCK_DATA_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata"))
subprocess.Popen([sys.executable, "main.py"], cwd=APP, env=env,
                 stdout=open(os.path.join(SCRATCH, "app_features.log"), "w"), stderr=subprocess.STDOUT,
                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)

# --- A. start page via virtual host ---
start = wait_for(lambda: next((t for t in pages() if "start.adblockbrowser.example" in t["url"]), None))
check("start page opens on its own origin", bool(start), start and start["url"])
if start:
    p = Page(start)
    wait_for(lambda: p.ev("location.origin + document.readyState") == "https://start.adblockbrowser.examplecomplete", 15)
    ls = p.ev("(() => { try { localStorage.setItem('x','1'); return localStorage.getItem('x'); } catch(e) { return 'ERR ' + e.name; } })()")
    check("start page localStorage works (speed dials persist)", ls == "1", ls)
    check("start page renders speed dials", p.ev("document.querySelectorAll('.tile').length") > 0)

    # --- B. cosmetic filtering on a news site ---
    p.call("Page.navigate", url=NEWS)
    time.sleep(12)
    info = p.ev("""(() => {
        const rules = [...document.adoptedStyleSheets].map(s => s.cssRules.length);
        const hidden = [...document.querySelectorAll('body *')].filter(e => getComputedStyle(e).display === 'none').length;
        return {url: location.href, adoptedSheets: rules, hiddenElements: hidden};
    })()""")
    nrules = sum(info.get("adoptedSheets", [])) if isinstance(info, dict) else 0
    check("element-hiding rules injected", nrules > 0, json.dumps(info))

    # --- C. popup blocker ---
    n0 = len(pages())
    p.ev("window.open('https://example.com/?nogesture', '_blank'); 1")
    time.sleep(3)
    check("popup without click is blocked", len(pages()) == n0, f"{n0} -> {len(pages())} pages")
    p.ev("window.open('https://example.com/?gesture', '_blank'); 1", gesture=True)
    popup = wait_for(lambda: next((t for t in pages() if "example.com/?gesture" in t["url"]), None), 15)
    check("link/window opened by click becomes a new tab", bool(popup))

    # --- D. window.close() closes that tab ---
    if popup:
        Page(popup).ev("window.close(); 1")
        gone = wait_for(lambda: not any("example.com/?gesture" in t["url"] for t in pages()), 10)
        check("window.close() closes its tab", bool(gone))

    # --- E. page fullscreen hides the browser chrome and restores it ---
    h0 = p.ev("innerHeight")
    p.ev("document.documentElement.requestFullscreen().then(() => 1)", gesture=True)
    time.sleep(1.5)
    h1 = p.ev("innerHeight")
    p.ev("document.exitFullscreen().then(() => 1)")
    time.sleep(1.5)
    h2 = p.ev("innerHeight")
    check("fullscreen hides toolbar/tabs/bookmarks", h1 > h0, f"{h0} -> {h1}")
    check("leaving fullscreen restores the layout", h2 == h0, f"{h1} -> {h2}")

errors = [l for l in open(os.path.join(SCRATCH, "app_features.log"), encoding="utf-8", errors="ignore") if "Traceback" in l or "Error" in l or "WARNING" in l]
check("no errors in app log", not errors, "".join(errors[:5]).strip())
kill()
