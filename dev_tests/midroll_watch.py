"""Watches big Twitch channels for streamer ad breaks (mid-rolls) and probes which player types
are ad-free during one. Writes midroll.log. No browser involved."""
import json, os, sys, time
import twlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "midroll.log")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
CHANNELS = ["jynxzi", "ricci", "eliasn97", "mingo", "rainbow6", "reflexx53", "beaulo", "gamerbrother",
            "skillsteve", "montanablack88", "zarbex", "gronkh", "papaplatte", "trymacs", "knossi",
            "handofblood", "revedtv", "stegi", "kaicenat", "xqc", "ohnepixel", "tarik", "summit1g",
            "caseoh_", "hasanabi", "zackrawrr", "thebausffs", "ironmouse"]
TYPES = ["site", "popout", "frontpage", "autoplay", "picture-by-picture", "embed"]
MAX_MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 50
WANT = int(sys.argv[2]) if len(sys.argv) > 2 else 3


def log(obj):
    obj["zeit"] = time.strftime("%H:%M:%S")
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def probe(ch):
    res = {}
    for pt in TYPES:
        try:
            v, m = twlib.session(ch, pt)
            res[pt] = twlib.ad_info(m)
        except Exception as e:
            res[pt] = {"error": str(e)[:80]}
    return res


def follow(ch, variant, started):
    """Polls the same (ad-showing) frontpage session until it is live again."""
    while time.time() - started < 400:
        time.sleep(5)
        try:
            info = twlib.ad_info(twlib.S.get(variant, timeout=10).text)
        except Exception:
            continue
        if not info["ad"]:
            return round(time.time() - started)
    return None


log({"event": "start", "channels": len(CHANNELS)})
offline, found, t0 = {}, 0, time.time()
while time.time() - t0 < MAX_MINUTES * 60 and found < WANT:
    for ch in CHANNELS:
        if offline.get(ch, 0) > time.time():
            continue
        try:
            variant, media = twlib.session(ch, "frontpage")
        except Exception as e:
            offline[ch] = time.time() + 600
            continue
        info = twlib.ad_info(media)
        if not info["ad"]:
            continue
        started = time.time()
        log({"event": "werbepause", "kanal": ch, "frontpage": info})
        log({"event": "probe", "kanal": ch, "ergebnis": probe(ch)})
        dauer = follow(ch, variant, started)
        log({"event": "ende", "kanal": ch, "dauer_s": dauer, "nachher": probe(ch)})
        found += 1
        if found >= WANT:
            break
    time.sleep(max(0, 60 - (time.time() - t0) % 60))
log({"event": "stop", "gefunden": found})
