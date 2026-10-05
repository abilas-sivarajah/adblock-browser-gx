import time, json, sys
from nf_live import start
from features_test_lib import pages, Page, wait_for
start("https://www.netflix.com/browse", sys.argv[1] if len(sys.argv) > 1 else "nf2")
t = wait_for(lambda: next((t for t in pages() if "netflix.com" in t["url"]), None), 40)
p = Page(t)
time.sleep(6)
p.call("Page.navigate", url="https://www.netflix.com/watch/81916859")
STATE = r"""(() => {
  const v = document.querySelector('video');
  const root = document.querySelector('.watch-video') || document.body;
  const txt = (root.innerText || '').replace(/\s+/g, ' ');
  const ad = (txt.match(/(Werbung|Anzeige)\s+\d+\s+von\s+\d+[^A-Za-z]{0,12}/) || [null])[0];
  const err = (document.body.innerText.match(/(Fehlercode|M\d{4}|NW-\d-\d+|Ups,[^.]*)/) || [null])[0];
  const nf = window.__abNetflix || {};
  return [v ? Math.round(v.currentTime) : null, v ? v.paused : null, ad, !!nf.overlayActive, nf.breaksRemoved, nf.adsShown, err];
})()"""
SEEK = r"""(ms) => { try { const vp = netflix.appContext.state.playerApp.getAPI().videoPlayer;
  const p = vp.getVideoPlayerBySessionId(vp.getAllPlayerSessionIds()[0]); p.seek(ms); return 'ok ' + Math.round(p.getCurrentTime() / 1000); }
  catch (e) { return 'seek-fehler ' + e; } }"""
def watch(label, secs):
    out = []
    for i in range(secs // 2):
        time.sleep(2)
        out.append(p.ev(STATE))
    ads = [s for s in out if s[2] or s[3]]
    print(f"{label:28} t: {out[0][0]}->{out[-1][0]} | Werbung sichtbar/abgedeckt: {len(ads)}x {ads[:1]} | Fehler: {set(s[6] for s in out if s[6]) or '-'}")
watch("Start", 16)
print("Werbepausen in den Daten:", json.dumps(p.ev("window.__abNetflix && window.__abNetflix.seen.map(s => s.positionen)"), ensure_ascii=False))
for minute in (20, 45, 75):
    print(f"Sprung auf {minute} min:", p.ev(f"({SEEK})({minute * 60000})"))
    watch(f"nach Sprung {minute} min", 20)
print("Blocker gesamt:", json.dumps(p.ev("window.__abNetflix && {entfernt: __abNetflix.breaksRemoved, datenMitWerbung: __abNetflix.dataWithAds, spots: __abNetflix.adsShown, alle: __abNetflix.seen.map(s => s.positionen)}"), ensure_ascii=False))
