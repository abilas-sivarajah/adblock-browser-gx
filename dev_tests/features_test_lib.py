"""Hidden-window feature test for the Claude copy of the browser (no focus, off-screen, muted)."""
import json, os, subprocess, sys, time, urllib.request
from websockets.sync.client import connect

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(SCRATCH, exist_ok=True)
PORT = 9333
TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")
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



def launch(url, name, extra_env=None):
    """Start the Claude copy hidden (off-screen, no focus, muted) with CDP + request log."""
    kill()
    log = os.path.join(SCRATCH, f"req_{name}.log")
    if os.path.exists(log):
        os.remove(log)
    env = dict(os.environ, ADBLOCK_REMOTE_DEBUG_PORT=str(PORT), ADBLOCK_HIDDEN_WINDOW="1", ADBLOCK_REQUEST_LOG=log,
               ADBLOCK_DATA_DIR=TESTDATA)
    env.update(extra_env or {})
    args = [sys.executable, "main.py"] + ([url] if url else [])
    subprocess.Popen(args, cwd=APP, env=env, stdout=open(os.path.join(SCRATCH, f"app_{name}.log"), "w"),
                     stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
    return log


def page_for(fragment, timeout=40):
    t = wait_for(lambda: next((t for t in pages() if fragment in t["url"]), None), timeout)
    return Page(t) if t else None
