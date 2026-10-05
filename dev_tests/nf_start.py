import time, json, sys
from nf_live import start, stop
from features_test_lib import pages, Page, wait_for
name, title_id = sys.argv[1], sys.argv[2]
start("https://www.netflix.com/browse", name)
p = Page(wait_for(lambda: next((t for t in pages() if "netflix.com" in t["url"]), None), 40))
time.sleep(6)
p.call("Page.navigate", url=f"https://www.netflix.com/watch/{title_id}?t=0")
STATE = r"""(() => {
  const v = document.querySelector('video');
  const root = document.querySelector('.watch-video') || document.body;
  const txt = (root.innerText || '').replace(/\s+/g, ' ');
  const ad = (txt.match(/(Werbung|Anzeige)\s+\d+\s+von\s+\d+[^A-Za-z]{0,12}/) || txt.match(/beginnt nach der Werbung/) || [null])[0];
  const nf = window.__abNetflix || null;
  const raw = /Werbung|Anzeige|Werbepause/.test(txt) ? txt.slice(0, 140) : null;
  return [v ? Math.round(v.currentTime) : null, ad, nf && nf.overlayActive, nf && nf.adsShown, raw];
})()"""
rows = []
for i in range(20):
    time.sleep(2)
    rows.append(p.ev(STATE))
ad_rows = [r for r in rows if r[1] or r[2]]
times = [r[0] for r in rows if r[0] is not None]
print(f"{name}: Zeit {times[:1]} -> {times[-1:]} s | Werbung sichtbar in {len(ad_rows)} von {len(rows)} Messungen")
texts = sorted(set(r[4] for r in rows if r[4]))
for t in texts[:4]: print("   Text im Player:", t)
print("   Blocker-Daten:", json.dumps(p.ev("window.__abNetflix ? {entfernt: __abNetflix.breaksRemoved, positionen: __abNetflix.seen.map(s => s.positionen)} : 'Blocker aus (Ausnahme)'"), ensure_ascii=False))
stop()
