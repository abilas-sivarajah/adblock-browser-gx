"""Startup time and in-app (SPA) navigation test for YouTube in the hidden browser."""
import json, sys, time
from features_test_lib import *
p = page_for("youtube.com")
MEASURE = r"""(async (secs, t0) => {
  t0 = t0 || Date.now();
  const out = {startMs: null, adSeconds: 0, endT: 0, title: null};
  while (Date.now() - t0 < secs * 1000) {
    const mp = document.querySelector('#movie_player');
    const v = mp && mp.querySelector('video');
    if (mp && (mp.classList.contains('ad-showing') || mp.classList.contains('ad-interrupting'))) out.adSeconds += 0.1;
    else if (v && v.currentTime > 0.3 && out.startMs === null) out.startMs = Date.now() - t0;
    if (v && !(mp.classList.contains('ad-showing'))) out.endT = Math.round(v.currentTime * 10) / 10;
    await new Promise(r => setTimeout(r, 100));
  }
  out.adSeconds = Math.round(out.adSeconds * 10) / 10;
  out.title = document.title.slice(0, 50);
  out.yt = window.__abYouTube;
  return out;
})"""
# 1) full page load
p.call("Page.navigate", url="https://www.youtube.com/watch?v=OPf0YbXqDm0")
t_nav = time.time()
r = p.ev(f"{MEASURE}(15)")
print("full load   :", json.dumps(r, ensure_ascii=False), f"(+{time.time()-t_nav-15:.1f}s before script ran)")
# 2) in-app navigation: click recommended videos
for i in range(3):
    href = p.ev(r"""(() => { const a = [...document.querySelectorAll('#secondary a[href^="/watch?v="], ytd-watch-next-secondary-results-renderer a[href^="/watch?v="], a#thumbnail[href^="/watch?v="]')].find(a => a.offsetParent && !a.href.includes(new URLSearchParams(location.search).get('v'))); if (!a) return null; a.click(); return a.getAttribute('href'); })()""", gesture=True)
    if not href:
        print("no recommendation link found"); break
    r = p.ev(f"{MEASURE}(15, Date.now())")
    r["spa"] = p.ev("performance.getEntriesByType('navigation').length === 1 && location.href.includes(" + json.dumps(href.split('&')[0]) + ")")
    print(f"SPA click {i+1} :", href.split('&')[0], json.dumps(r, ensure_ascii=False))
