"""User's problem case: stream starts with an ad and no backup is ad-free. Hidden, own test profile.
usage: python tw_mask_test.py <name> <channel> <backup types comma separated> [seconds]"""
import json, os, sys, time
from features_test_lib import *

name, ch, types = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
secs = int(sys.argv[4]) if len(sys.argv) > 4 else 40
SITE_SCRIPTS = os.path.join(APP, "site_scripts.py")
ORIG_LINE = 'TWITCH_BACKUP_TYPES = ["popout", "frontpage", "autoplay"]'

FORCE_EMBED = r"""
(() => {
  const swap = b => typeof b === 'string' ? b.replace(/"playerType":"site"/g, '"playerType":"embed"') : b;
  const f = window.fetch;
  window.fetch = function (input, init) {
    const u = typeof input === 'string' ? input : input && input.url;
    if (u && u.includes('gql.twitch.tv') && input instanceof Request && !init) {
      const self = this;
      return input.clone().text().then(b => f.call(self, new Request(input, {body: swap(b)})));
    }
    if (u && u.includes('gql.twitch.tv') && init && typeof init.body === 'string') init = Object.assign({}, init, {body: swap(init.body)});
    return f.call(this, input, init);
  };
})();
"""

orig = open(SITE_SCRIPTS, encoding="utf-8").read()
assert orig.count(ORIG_LINE) == 1
try:
    open(SITE_SCRIPTS, "w", encoding="utf-8").write(orig.replace(ORIG_LINE, "TWITCH_BACKUP_TYPES = " + json.dumps(types)))
    launch("https://www.twitch.tv/directory", name)
    p = page_for("twitch.tv")
    time.sleep(4)
finally:
    open(SITE_SCRIPTS, "w", encoding="utf-8").write(orig)   # app has read it at startup

p.call("Page.enable")
p.call("Page.addScriptToEvaluateOnNewDocument", source=FORCE_EMBED)
p.call("Page.navigate", url=f"https://www.twitch.tv/{ch}")
t0 = time.time()
STATE = r"""(() => {
  const ab = window.__abTwitch || {};
  const v = document.querySelector('[data-a-target="video-player"] video');
  const ov = document.getElementById('adblock-twitch-overlay');
  return {t: v ? Math.round(v.currentTime) : null, playing: v ? (!v.paused && v.readyState > 2) : false, muted: v ? v.muted : null,
          overlay: ov ? (ov.style.inset === '0px' || ov.getAttribute('style').includes('inset:0') ? 'ABGEDECKT' : 'Hinweis') + ': ' + ov.textContent.slice(-45) : null,
          masters: ab.masters, playlists: ab.playlists, ads: ab.adBreaks, replaced: ab.replaced, masked: ab.masked};
})()"""
first_live = None
for i in range(secs // 2):
    time.sleep(2)
    s = p.ev(STATE)
    el = round(time.time() - t0)
    if first_live is None and s.get("playing") and not s.get("overlay"):
        first_live = el
    print(f"{el:3}s", json.dumps(s, ensure_ascii=False))
s = p.ev(STATE)
rate = s["playlists"] / (time.time() - t0) if s.get("playlists") else 0
print(f"\nStream lief ohne Abdeckung ab: {first_live} s | Master-Abrufe (Sitzungen des Players): {s['masters']} | Playlist-Abrufe pro Sekunde: {rate:.1f}")
print("Ersatz-Versuche:", json.dumps(p.ev("window.__abTwitch && window.__abTwitch.backupTrail"), ensure_ascii=False))
