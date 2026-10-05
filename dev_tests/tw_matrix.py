import json, sys, time
from features_test_lib import *
channels = sys.argv[1].split(",")
launch("https://www.twitch.tv/" + channels[0], "tw_matrix")
p = page_for("twitch.tv"); time.sleep(8)
print("consent:", p.ev(r"""(() => { const b=[...document.querySelectorAll('button')].find(b=>/^(Ablehnen|Alle ablehnen)$/i.test(b.innerText.trim())); if(!b) return 'none'; b.click(); return 'abgelehnt'; })()"""))
JS = r"""
(async (channels, types) => {
  const deviceId = (document.cookie.match(/unique_id=([^;]+)/) || [])[1] || '';
  const query = 'query PlaybackAccessToken_Template($login: String!, $isLive: Boolean!, $vodID: ID!, $isVod: Boolean!, $playerType: String!, $platform: String!) {  streamPlaybackAccessToken(channelName: $login, params: {platform: $platform, playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isLive) {    value    signature   authorization { isForbidden forbiddenReasonCode }   __typename  }  videoPlaybackAccessToken(id: $vodID, params: {platform: $platform, playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isVod) {    value    signature   __typename  }}';
  const out = {};
  for (const ch of channels) {
    out[ch] = {};
    for (const pt of types) {
      try {
        const r = await fetch('https://gql.twitch.tv/gql', {method: 'POST', headers: {'Client-ID': 'kimne78kx3ncx6brgo4mv6wki5h1ko', 'Device-ID': deviceId},
          body: JSON.stringify({operationName: 'PlaybackAccessToken_Template', query, variables: {isLive: true, login: ch, isVod: false, vodID: '', playerType: pt, platform: 'web'}})});
        const tok = (await r.json()).data.streamPlaybackAccessToken;
        if (!tok) { out[ch][pt] = 'kein Token'; continue; }
        const u = `https://usher.ttvnw.net/api/v2/channel/hls/${ch}.m3u8?allow_source=true&fast_bread=true&p=${Math.floor(Math.random()*1e7)}&platform=web&player_backend=mediaplayer&playlist_include_framerate=true&reassignments_supported=true&supported_codecs=avc1&sig=${tok.signature}&token=${encodeURIComponent(tok.value)}`;
        const m = await fetch(u);
        if (!m.ok) { out[ch][pt] = 'usher ' + m.status; continue; }
        const master = await m.text();
        const variant = master.split('\n').find(l => l.startsWith('http'));
        const media = await (await fetch(variant)).text();
        const ad = media.includes('stitched-ad') || /#EXTINF:[^,\n]*,(?!live)\S/.test(media);
        const src = (media.match(/X-TV-TWITCH-STREAM-SOURCE="([^"]*)"/) || [])[1];
        const dur = (media.match(/CLASS="twitch-stitched-ad",[^\n]*DURATION=([\d.]+)/) || [])[1];
        out[ch][pt] = ad ? `WERBUNG ${src || ''} ${dur ? dur + 's' : ''}`.trim() : 'frei';
      } catch (e) { out[ch][pt] = 'Fehler ' + e; }
    }
  }
  return out;
})"""
types = ["site", "popout", "frontpage", "autoplay", "embed", "picture-by-picture"]
r = p.ev(f"{JS}({json.dumps(channels)}, {json.dumps(types)})")
print(f"{'Kanal':12}" + "".join(f"{t:>22}" for t in types))
for ch, row in r.items():
    print(f"{ch:12}" + "".join(f"{str(row.get(t))[:21]:>22}" for t in types))
