"""Live check of the pause ad blocking in netflix.js (USER profile, hidden + muted).
usage: python nf_pause_final.py normal|netz [title]
  normal: blocker as shipped        netz: data removal switched off -> only the CSS safety net"""
import base64, json, os, sys, time
from nf_live import start, stop
from features_test_lib import SCRATCH, pages, Page, wait_for

MODE = sys.argv[1]
TITLE = sys.argv[2] if len(sys.argv) > 2 else "81916859"
OUT = os.path.join(SCRATCH, "nf_final")
os.makedirs(OUT, exist_ok=True)

STATE = r"""(() => { const v = document.querySelector('video'); const d = document.querySelector('[data-uia="pause-ad"]');
  const nf = window.__abNetflix || {}; const b = document.body.innerText.replace(/\s+/g, ' ');
  const r = d ? d.getBoundingClientRect() : null;
  return {t: v ? Math.round(v.currentTime * 10) / 10 : null, paused: v ? v.paused : null,
          dialog: d ? {display: getComputedStyle(d).display, opacity: getComputedStyle(d).opacity, w: Math.round(r.width), h: Math.round(r.height)} : null,
          fokus: document.activeElement ? document.activeElement.tagName + '[' + (document.activeElement.getAttribute('data-uia') || '') + ']' : null,
          nf: {daten: nf.pauseAdData, entfernt: nf.pauseAdsRemoved, durchgekommen: nf.pauseAdsHidden, weg: nf.pauseAdVia, pausePrune: nf.pausePrune},
          sieSehen: /Sie sehen gerade/.test(b), werbungSichtbar: /Werbung/.test((document.querySelector('.watch-video') || document.body).innerText),
          err: (b.match(/(Fehlercode|Ups,[^.]{0,60}|M\d{4}|NW-\d-\d+|etwas ist schiefgelaufen)/) || [null])[0]}; })()"""


def key(p):
    for typ in ("keyDown", "keyUp"):
        p.call("Input.dispatchKeyEvent", type=typ, key=" ", code="Space", windowsVirtualKeyCode=32, nativeVirtualKeyCode=32)


def shot(p, name):
    r = p.call("Page.captureScreenshot", format="png")
    if isinstance(r, dict) and r.get("data"):
        open(os.path.join(OUT, f"{MODE}_{name}.png"), "wb").write(base64.b64decode(r["data"]))


start("https://www.netflix.com/browse", f"final_{MODE}")
target = wait_for(lambda: next((t for t in pages() if "netflix.com" in t["url"]), None), 40)
p = Page(target)
p.call("Page.enable")
time.sleep(5)
p.call("Page.navigate", url=f"https://www.netflix.com/watch/{TITLE}")
wait_for(lambda: ((p.ev(STATE) or {}).get("t") or 0) > 0.5, 60)
time.sleep(3)
if p.ev(STATE)["paused"]:
    # autoplay blocked (no user gesture on a direct /watch load): click the play button, page only
    size = p.ev("[innerWidth, innerHeight]")
    for typ in ("mousePressed", "mouseReleased"):
        p.call("Input.dispatchMouseEvent", type=typ, x=size[0] // 2, y=size[1] // 2, button="left", clickCount=1)
    time.sleep(4)
    print("Autoplay gesperrt -> Klick auf Play:", json.dumps(p.ev(STATE), ensure_ascii=False))
if MODE == "netz":
    p.ev("window.__abNetflix.pausePrune = false")
print(MODE, "laeuft:", json.dumps(p.ev(STATE), ensure_ascii=False))
for runde in (1, 2):
    key(p)
    for s, wait in ((4, 4), (10, 6), (16, 6)):
        time.sleep(wait)
        st = p.ev(STATE)
        print(f" Pause {runde} +{s:2}s pausiert={st['paused']} t={st['t']} dialog={st['dialog']} fokus={st['fokus']} blocker={st['nf']} "
              f"'Sie sehen gerade'={st['sieSehen']} 'Werbung' sichtbar={st['werbungSichtbar']} fehler={st['err']}")
        if s == 10:
            shot(p, f"pause{runde}")
    key(p)
    time.sleep(5)
    st = p.ev(STATE)
    print(f" nach Leertaste: pausiert={st['paused']} t={st['t']} fehler={st['err']}")
    if st["paused"]:
        size = p.ev("[innerWidth, innerHeight]")
        for typ in ("mousePressed", "mouseReleased"):
            p.call("Input.dispatchMouseEvent", type=typ, x=size[0] // 2, y=size[1] // 2, button="left", clickCount=1)
        time.sleep(4)
        st = p.ev(STATE)
        print(f" nach Klick aufs Bild: pausiert={st['paused']} t={st['t']} fehler={st['err']}")
stop()
