"""Netflix pause ad probe 2: pause like a user (Space key via CDP into the hidden page only),
record every GraphQL request (operation) + response while paused. USER profile, hidden + muted."""
import base64, json, os, sys, threading, time
from websockets.sync.client import connect
from nf_live import start, stop
from features_test_lib import SCRATCH, pages, Page, wait_for

TITLE = sys.argv[1] if len(sys.argv) > 1 else "81916859"
WAIT = int(sys.argv[2]) if len(sys.argv) > 2 else 60
OUT = os.path.join(SCRATCH, "nf_pause2")
os.makedirs(OUT, exist_ok=True)

DOM = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nf_pause_dom.js"), encoding="utf-8").read()

gql, others = [], []
lock = threading.Lock()


def net_reader(ws_url, stop_flag):
    ws = connect(ws_url, max_size=None)
    ws.send(json.dumps({"id": 1, "method": "Network.enable", "params": {"maxTotalBufferSize": 200000000}}))
    reqs, pending, nid = {}, {}, 1000
    while not stop_flag.is_set():
        try:
            m = json.loads(ws.recv(timeout=1))
        except TimeoutError:
            continue
        except Exception:
            break
        meth, p = m.get("method"), m.get("params", {})
        if meth == "Network.requestWillBeSent":
            u = p["request"]["url"]
            if "/graphql" in u:
                reqs[p["requestId"]] = {"t": round(time.time(), 1), "post": (p["request"].get("postData") or "")[:3000]}
            elif "nflxvideo" not in u and "logs.netflix" not in u:
                with lock:
                    others.append((round(time.time(), 1), p.get("type"), u[:300]))
        elif meth == "Network.loadingFinished" and p["requestId"] in reqs:
            nid += 1
            pending[nid] = p["requestId"]
            ws.send(json.dumps({"id": nid, "method": "Network.getResponseBody", "params": {"requestId": p["requestId"]}}))
        elif m.get("id") in pending:
            rid = pending.pop(m["id"])
            r = reqs.pop(rid)
            r["body"] = ((m.get("result") or {}).get("body") or "")[:60000]
            with lock:
                gql.append(r)
    ws.close()


def key(p, name="Space", text=" ", code=32):
    for typ in ("keyDown", "keyUp"):
        p.call("Input.dispatchKeyEvent", type=typ, key=text, code=name, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code)


def op(post):
    try:
        j = json.loads(post)
        return j.get("operationName") or (j.get("extensions") or {}).get("persistedQuery", {}).get("id", "?")
    except Exception:
        return post[:80]


start("https://www.netflix.com/browse", "pause_probe2")
target = wait_for(lambda: next((t for t in pages() if "netflix.com" in t["url"]), None), 40)
p = Page(target)
p.call("Page.enable")
flag = threading.Event()
threading.Thread(target=net_reader, args=(target["webSocketDebuggerUrl"], flag), daemon=True).start()
time.sleep(5)
p.call("Page.navigate", url=f"https://www.netflix.com/watch/{TITLE}")
cur = lambda: p.ev("(() => { const v = document.querySelector('video'); return v ? [v.currentTime, v.paused] : null; })()")
wait_for(lambda: (cur() or [0, True])[0] > 0.5, 60)
a = cur(); time.sleep(4); b = cur()
print("Wiedergabe:", a, "->", b)
t0 = time.time()
key(p)
time.sleep(1.5)
print("nach Leertaste:", cur())
if cur() and not cur()[1]:
    print("Leertaste ohne Wirkung - Klick auf das Video")
    for typ in ("mousePressed", "mouseReleased"):
        p.call("Input.dispatchMouseEvent", type=typ, x=600, y=350, button="left", clickCount=1)
    time.sleep(1.5)
    print("nach Klick:", cur())
found = False
for i in range(WAIT // 3):
    time.sleep(3)
    d = p.ev(DOM)
    print(f"+{round(time.time() - t0):3}s t={d.get('t')} pausiert={d.get('paused')} labels={len(d.get('labels', []))} uias={d.get('uias')}")
    if d.get("labels") and not found:
        found = True
        json.dump(d, open(os.path.join(OUT, "dom.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        shot = p.call("Page.captureScreenshot", format="png")
        if isinstance(shot, dict) and shot.get("data"):
            open(os.path.join(OUT, "pause.png"), "wb").write(base64.b64decode(shot["data"]))
        html = p.ev(r"""(() => { const e = [...document.querySelectorAll('body *')].find(e => e.children.length === 0 && /^(Werbung|Anzeige|Ad)$/i.test((e.textContent || '').trim()));
          const out = []; for (let n = e, i = 0; n && i < 10; i++, n = n.parentElement) out.push(n.outerHTML.slice(0, 6000)); return out; })()""")
        json.dump(html, open(os.path.join(OUT, "html.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for l in d["labels"]:
            print("   Label-Kette:", " < ".join(l[:12]))
flag.set()
time.sleep(1.5)
json.dump(gql, open(os.path.join(OUT, "graphql.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(others, open(os.path.join(OUT, "other.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("GraphQL-Operationen:")
for r in gql:
    print(f"  {'nach Pause' if r['t'] >= t0 else 'vorher    '} {op(r['post'])[:70]:70} Antwort {len(r.get('body', ''))} Zeichen")
print("Andere Anfragen nach der Pause:")
for e in others:
    if e[0] >= t0:
        print("  ", e[1], e[2][:180])
stop()
