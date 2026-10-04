"""
Site-specific scripts (Twitch, YouTube, ad watch for the ad log) that run at document start.
The JavaScript lives in scripts/*.js; this module fills in the shield settings, so the
scripts stay inactive when the blocker is off or the site is on the exception list.
"""

import json
import os

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")

# Twitch player types tried (in this order) for an ad-free copy of the stream during ads.
# Measured 10/2026: fresh sessions of these are usually ad-free; "embed" and
# "picture-by-picture" always started with an ad. During a streamer's ad break every type has ads.
TWITCH_BACKUP_TYPES = ["popout", "frontpage", "autoplay"]


def _read(name: str) -> str:
    with open(os.path.join(SCRIPTS_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


def build_site_scripts(enabled: bool, whitelist) -> list[str]:
    config = json.dumps({
        "enabled": bool(enabled),
        "whitelist": sorted(whitelist),
        "twitchBackupTypes": TWITCH_BACKUP_TYPES,
    })
    twitch = (_read("twitch_main.js")
              .replace("__AB_CONFIG__", config)
              .replace("__AB_WORKER_HOOK__", json.dumps(_read("twitch_worker.js"))))
    youtube = _read("youtube.js").replace("__AB_CONFIG__", config)
    ad_watch = _read("ad_watch.js").replace("__AB_CONFIG__", config)
    return [twitch, youtube, ad_watch]
