"""Twitch playback sessions without a browser (for the mid-roll watcher)."""
import json, random, re, urllib.parse, requests

CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
QUERY = 'query PlaybackAccessToken_Template($login: String!, $isLive: Boolean!, $vodID: ID!, $isVod: Boolean!, $playerType: String!, $platform: String!) {  streamPlaybackAccessToken(channelName: $login, params: {platform: $platform, playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isLive) {    value    signature   authorization { isForbidden forbiddenReasonCode }   __typename  }  videoPlaybackAccessToken(id: $vodID, params: {platform: $platform, playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isVod) {    value    signature   __typename  }}'
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Origin": "https://www.twitch.tv", "Referer": "https://www.twitch.tv/"})


def device():
    return "%032x" % random.getrandbits(128)


def session(ch, player_type, dev=None):
    """Returns (variant_url, media_text) of a fresh playback session, or raises."""
    body = {"operationName": "PlaybackAccessToken_Template", "query": QUERY,
            "variables": {"isLive": True, "login": ch, "isVod": False, "vodID": "", "playerType": player_type, "platform": "web"}}
    r = S.post("https://gql.twitch.tv/gql", json=body, headers={"Client-ID": CLIENT_ID, "Device-ID": dev or device()}, timeout=10)
    tok = r.json()["data"]["streamPlaybackAccessToken"]
    if not tok:
        raise RuntimeError("offline/kein Token")
    q = {"allow_source": "true", "fast_bread": "true", "p": random.randint(0, 9999999), "platform": "web",
         "player_backend": "mediaplayer", "playlist_include_framerate": "true", "reassignments_supported": "true",
         "supported_codecs": "avc1", "sig": tok["signature"], "token": tok["value"]}
    m = S.get(f"https://usher.ttvnw.net/api/v2/channel/hls/{ch}.m3u8?" + urllib.parse.urlencode(q), timeout=10)
    if m.status_code != 200:
        raise RuntimeError(f"usher {m.status_code}")
    variant = next(l for l in m.text.splitlines() if l.startswith("http"))
    return variant, S.get(variant, timeout=10).text


def ad_info(media):
    titles = [l.split(",", 1)[1] for l in media.splitlines() if l.startswith("#EXTINF:")]
    ad = "stitched-ad" in media or any(t.strip() not in ("", "live") for t in titles)
    src = re.search(r'X-TV-TWITCH-STREAM-SOURCE="([^"]*)"', media)
    pod = re.search(r'X-TV-TWITCH-AD-POD-FILLED-DURATION="([^"]*)"', media) or re.search(r'CLASS="twitch-stitched-ad",[^\n]*DURATION=([\d.]+)', media)
    seq = re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", media)
    return {"ad": ad, "source": src.group(1) if src else None, "pod": pod.group(1) if pod else None,
            "seq": int(seq.group(1)) if seq else None, "live": titles.count("live"), "segs": len(titles)}
