"""Tiny CDP client for the WebView2 remote-debugging port.

usage:
  python cdp.py targets
  python cdp.py eval "<js expression>"        (awaits promises, returns JSON)
  python cdp.py shot out.png
  python cdp.py nav <url>
  python cdp.py net <seconds> [filter]         (logs network requests for N seconds)
"""
import base64, json, sys, time, urllib.request
from websockets.sync.client import connect

PORT = 9333


def page_ws():
    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
    pages = [t for t in targets if t["type"] == "page"]
    # prefer a real http page over the start page
    pages.sort(key=lambda t: not t["url"].startswith("http"))
    return pages[0]["webSocketDebuggerUrl"], targets


class CDP:
    def __init__(self):
        url, _ = page_ws()
        self.ws = connect(url, max_size=None, open_timeout=10)
        self.i = 0

    def call(self, method, **params):
        self.i += 1
        my = self.i
        self.ws.send(json.dumps({"id": my, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv(timeout=60))
            if msg.get("id") == my:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg["result"]


def main():
    cmd = sys.argv[1]
    if cmd == "targets":
        _, targets = page_ws()
        for t in targets:
            print(t["type"], t["url"][:150])
        return
    c = CDP()
    if cmd == "eval":
        r = c.call("Runtime.evaluate", expression=sys.argv[2], awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            print("EXC:", json.dumps(r["exceptionDetails"])[:2000])
        else:
            v = r["result"].get("value")
            print(json.dumps(v, indent=1, ensure_ascii=False) if not isinstance(v, str) else v)
    elif cmd == "shot":
        r = c.call("Page.captureScreenshot", format="png")
        open(sys.argv[2], "wb").write(base64.b64decode(r["data"]))
        print("saved", sys.argv[2])
    elif cmd == "nav":
        print(c.call("Page.navigate", url=sys.argv[2]))
    elif cmd == "net":
        secs = float(sys.argv[2])
        flt = sys.argv[3] if len(sys.argv) > 3 else ""
        c.call("Network.enable")
        end = time.time() + secs
        while time.time() < end:
            try:
                msg = json.loads(c.ws.recv(timeout=max(0.1, end - time.time())))
            except TimeoutError:
                break
            m = msg.get("method")
            p = msg.get("params", {})
            if m == "Network.requestWillBeSent":
                u = p["request"]["url"]
                if flt in u:
                    print("REQ", p.get("type"), p["request"]["method"], u[:220])
            elif m == "Network.responseReceived":
                u = p["response"]["url"]
                if flt in u:
                    print("RES", p["response"]["status"], p.get("type"), u[:220])
            elif m == "Network.loadingFailed":
                print("FAIL", p.get("type"), p.get("errorText"), p.get("blockedReason", ""))


if __name__ == "__main__":
    main()
