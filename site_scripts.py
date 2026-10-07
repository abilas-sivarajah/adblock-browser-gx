"""
Site-specific scripts (Twitch, YouTube, Netflix, ad watch for the ad log) that run at document start.
The JavaScript lives in scripts/*.js; this module fills in the shield settings, so the
scripts stay inactive when the blocker is off or the site is on the exception list.
"""

import base64
import json
import os

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")

# Twitch player types tried (in this order) for an ad-free copy of the stream during ads.
# Measured 10/2026: fresh sessions of popout/frontpage/autoplay are usually ad-free; "embed" and
# "picture-by-picture" always started with an ad. During a streamer's ad break every type has ads.
# "autoplay" (360p, platform android) is the quick bridge, the others are full quality
# (mobile_web and site as in TTV-AB, github.com/GosuDRM/TTV-AB).
TWITCH_BACKUP_TYPES = ["popout", "frontpage", "mobile_web", "site", "autoplay"]

# 1.024 s black + silence as MPEG-TS (H.264 640x360 + AAC), shown instead of an ad that no backup
# can replace. Made with:
#   ffmpeg -f lavfi -i "color=c=black:s=640x360:r=125/4" -f lavfi -i "anullsrc=r=48000:cl=stereo" -t 1.024
#     -c:v libx264 -profile:v high -pix_fmt yuv420p -preset veryslow -tune stillimage -bf 0
#     -x264-params "keyint=64:scenecut=0" -c:a aac -b:a 32k -muxdelay 0 -muxpreload 0
#     -max_delay 500000 -pes_payload_size 4096 -f mpegts scripts/twitch_hold.ts
TWITCH_HOLD_SEGMENT = "twitch_hold.ts"


def _read(name: str) -> str:
    with open(os.path.join(SCRIPTS_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def twitch_worker_script() -> str:
    with open(os.path.join(SCRIPTS_DIR, TWITCH_HOLD_SEGMENT), "rb") as f:
        hold = base64.b64encode(f.read()).decode("ascii")
    return _read("twitch_worker.js").replace("__AB_HOLD_SEGMENT__", json.dumps(hold))


def build_site_scripts(enabled: bool, whitelist) -> list[str]:
    config = json.dumps({
        "enabled": bool(enabled),
        "whitelist": sorted(whitelist),
        "twitchBackupTypes": TWITCH_BACKUP_TYPES,
        "adSpoofing": True,
    })
    twitch = (_read("twitch_main.js")
              .replace("__AB_CONFIG__", config)
              .replace("__AB_WORKER_HOOK__", json.dumps(twitch_worker_script())))
    youtube = _read("youtube.js").replace("__AB_CONFIG__", config)
    netflix = _read("netflix.js").replace("__AB_CONFIG__", config)
    ad_watch = _read("ad_watch.js").replace("__AB_CONFIG__", config)
    return [twitch, youtube, netflix, ad_watch]
