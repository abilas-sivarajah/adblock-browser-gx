"""Click -> first content frame, measured precisely (new video id, state==1, currentTime>0.3, no ad)."""
import json, sys, time
from features_test_lib import *
p = page_for("youtube.com")
MEASURE = r"""(async (oldVid, secs) => {
  const t0 = Date.now(); const out = {firstAdMs: null, adMs: 0, contentMs: null};
  while (Date.now() - t0 < secs * 1000) {
    const vid = new URLSearchParams(location.search).get('v');
    const mp = document.querySelector('#movie_player'); const v = mp && mp.querySelector('video');
    let st = null; try { st = mp.getPlayerState(); } catch (e) {}
    const ad = mp && mp.classList.contains('ad-showing');
    if (vid !== oldVid && ad) { out.adMs += 100; if (out.firstAdMs === null) out.firstAdMs = Date.now() - t0; }
    if (vid !== oldVid && !ad && st === 1 && v && v.currentTime > 0.3 && v.currentTime < 5) { out.contentMs = Date.now() - t0; break; }
    await new Promise(r => setTimeout(r, 100));
  }
  return out;
})"""
for i in range(int(sys.argv[1])):
    old = p.ev("new URLSearchParams(location.search).get('v')")
    href = p.ev(r"""(() => { const a = [...document.querySelectorAll('#secondary a[href^="/watch?v="], ytd-watch-next-secondary-results-renderer a[href^="/watch?v="], a#thumbnail[href^="/watch?v="]')].find(a => a.offsetParent && !a.href.includes(new URLSearchParams(location.search).get('v'))); if (!a) return null; a.click(); return a.getAttribute('href'); })()""", gesture=True)
    r = p.ev(f"{MEASURE}({json.dumps(old)}, 25)")
    print(f"click {i+1} {href.split('&')[0] if isinstance(href, str) else href}: {r}")
    time.sleep(2)
