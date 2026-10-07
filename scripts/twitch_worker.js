// Runs inside Twitch's video player Web Worker (prepended by twitch_main.js).
//
// Twitch stitches ads into the live HLS media playlist: ad segments have an #EXTINF title
// other than "live" (e.g. "Amazon|123") and there are DATERANGE tags of class
// "twitch-stitched-ad".
//
// - When the player's playlist contains ads, the same stream is fetched through another
//   player type ("backup"). If that one is ad-free, the player gets the backup playlist - and
//   keeps getting it for this channel: switching back would hand the player lower segment
//   numbers (sessions are numbered differently), and it would stall.
// - If no backup is ad-free (a streamer's ad break reaches every player type), the playlist is
//   passed on unchanged and the page covers and mutes the player ('masked', twitch_main.js).
//   Cutting the ads out does not work: an emptied playlist makes the player re-request it many
//   times a second and open new sessions, each starting with a new ad.
(function () {
    'use strict';
    if (self.__abTwitchWorker) return;
    self.__abTwitchWorker = true;

    const INIT = __AB_WORKER_INIT__;
    const BACKUP_TYPES = INIT.backupTypes || ['popout', 'frontpage', 'autoplay'];
    const AD_SPOOFING_ENABLED = INIT.adSpoofing !== false;
    const GQL_QUERY = 'query PlaybackAccessToken_Template($login: String!, $isLive: Boolean!, $vodID: ID!, $isVod: Boolean!, $playerType: String!, $platform: String!) {  streamPlaybackAccessToken(channelName: $login, params: {platform: $platform, playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isLive) {    value    signature   authorization { isForbidden forbiddenReasonCode }   __typename  }  videoPlaybackAccessToken(id: $vodID, params: {platform: $platform, playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isVod) {    value    signature   __typename  }}';
    const GQL_EVENT_HASH = '7e6c69e6eb59f8ccb97ab73686f3d8b7d85a72a0298745ccd8bfc68e4054ca5b';
    const gqlHeaders = {'Client-ID': INIT.clientId, 'Content-Type': 'text/plain;charset=UTF-8'};
    if (INIT.deviceId) {
        gqlHeaders['Device-ID'] = INIT.deviceId;
        gqlHeaders['X-Device-Id'] = INIT.deviceId;
    }
    if (INIT.authHeader) {
        gqlHeaders['Authorization'] = INIT.authHeader;
    }
    const SESSION_MAX_AGE = 5 * 60 * 1000;

    const realFetch = self.fetch.bind(self);
    let channel = null;
    try {
        channel = new BroadcastChannel(INIT.channel);
        channel.onmessage = function (e) {
            const d = e.data || {};
            if (d.event === 'update-headers' && d.headers) {
                const h = d.headers;
                if (h.integrity) gqlHeaders['Client-Integrity'] = h.integrity;
                if (h.auth) gqlHeaders['Authorization'] = h.auth;
                if (h.version) gqlHeaders['Client-Version'] = h.version;
                if (h.session) gqlHeaders['Client-Session-Id'] = h.session;
                if (h.device) {
                    gqlHeaders['Device-ID'] = h.device;
                    gqlHeaders['X-Device-Id'] = h.device;
                }
            }
        };
    } catch (e) {}

    const variants = new Map();   // player's media playlist URL -> {login, res, fps, usher}
    const tokens = new Map();     // login|type -> {value, signature, ts}
    // One backup session per channel and player type. Sessions are kept and re-polled:
    // every new session risks a new pre-roll ad.
    const sessions = new Map();   // login|type -> {master, created, retryAt, last}
    const sticky = new Map();     // login -> backup type the player is being fed from
    const spoofedAdIds = new Set();
    const recentSpoofedAdIds = new Map(); // adId -> timestamp, capped at 50
    let inAdBreak = false;

    function report(event, extra) {
        if (channel) {
            try { channel.postMessage(Object.assign({event: event}, extra || {})); } catch (e) {}
        }
    }

    function withTimeout(promise, ms) {
        return Promise.race([promise, new Promise(function (_, reject) {
            setTimeout(function () { reject(new Error('timeout')); }, ms || 4000);
        })]);
    }

    async function fetchText(url, init) {
        const r = await withTimeout(realFetch(url, init));
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.text();
    }

    // ---- playlist parsing ----
    const ATTR_REGEX = /([A-Z0-9-]+)=("[^"]*"|[^,]*)/gi;
    function parseAttrs(str) {
        const result = {};
        ATTR_REGEX.lastIndex = 0;
        let match = ATTR_REGEX.exec(str);
        while (match !== null) {
            let val = match[2];
            if (val && val.charCodeAt(0) === 34 && val.charCodeAt(val.length - 1) === 34) {
                val = val.slice(1, -1);
            }
            result[match[1].toUpperCase()] = val;
            match = ATTR_REGEX.exec(str);
        }
        return result;
    }

    function isAdTitle(extinf) {
        const i = extinf.indexOf(',');
        const title = i < 0 ? '' : extinf.slice(i + 1).trim();
        return title !== '' && title !== 'live';
    }

    function isAdMarker(line) {
        if (!line.startsWith('#EXT-X-DATERANGE')) return false;
        if (line.indexOf('stitched-ad') !== -1 || line.indexOf('X-TV-TWITCH-AD') !== -1) return true;
        // stream source "Amazon|..." instead of "live" drives the player's ad overlay
        const m = line.match(/X-TV-TWITCH-STREAM-SOURCE="([^"]*)"/);
        return !!m && m[1] !== 'live';
    }

    function hasAds(text) {
        if (text.indexOf('stitched-ad') !== -1 || text.indexOf('X-TV-TWITCH-AD') !== -1) return true;
        const lines = text.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if ((line.startsWith('#EXTINF:') && isAdTitle(line)) || isAdMarker(line)) return true;
        }
        return false;
    }

    // When does the ad pod end? (START-DATE + DURATION of the stitched-ad DATERANGE tags)
    function adEndsAt(text) {
        let end = 0;
        const lines = text.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (!line.startsWith('#EXT-X-DATERANGE') || line.indexOf('stitched-ad') === -1) continue;
            const start = Date.parse((line.match(/START-DATE="([^"]+)"/) || [])[1] || '');
            const dur = parseFloat((line.match(/[,:]DURATION=([\d.]+)/) || [])[1] ||
                                   (line.match(/AD-POD-FILLED-DURATION="([\d.]+)"/) || [])[1] || 'NaN');
            if (isFinite(start) && isFinite(dur)) end = Math.max(end, start + dur * 1000);
        }
        return end || null;
    }

    // ---- ad spoofing (TTV-AB technique): report ad impressions & quartiles to Twitch GQL ----
    async function notifyAdComplete(text) {
        if (!AD_SPOOFING_ENABLED || !text || typeof text !== 'string') return;
        const lines = text.split('\n');
        const adLines = [];
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (line.startsWith('#EXT-X-DATERANGE') && (line.indexOf('stitched-ad') !== -1 || line.indexOf('twitch-stitched-ad') !== -1)) {
                adLines.push(line);
            }
        }
        if (!adLines.length) return;

        const podLenMatch = text.match(/X-TV-TWITCH-AD-POD-LENGTH="(\d+)"/);
        const explicitPodLength = podLenMatch ? parseInt(podLenMatch[1], 10) : 0;
        const hasExplicitPodLength = explicitPodLength > 0;
        const podLength = hasExplicitPodLength ? explicitPodLength : adLines.length;

        if (hasExplicitPodLength && spoofedAdIds.size >= podLength) return;

        for (let i = 0; i < adLines.length; i++) {
            if (hasExplicitPodLength && spoofedAdIds.size >= podLength) break;
            const line = adLines[i];
            const attr = parseAttrs(line);
            const idMatch = line.match(/\bID="([^"]+)"/);
            const stitchedAdId = (idMatch && idMatch[1]) || attr['ID'] || '';
            if (!stitchedAdId) continue;

            if (recentSpoofedAdIds.has(stitchedAdId)) {
                spoofedAdIds.add(stitchedAdId);
                continue;
            }
            if (spoofedAdIds.has(stitchedAdId)) continue;

            const radToken = attr['X-TV-TWITCH-AD-RADS-TOKEN'];
            if (!radToken) continue;

            const rollType = (attr['X-TV-TWITCH-AD-ROLL-TYPE'] || '').toLowerCase();
            const adPos = parseInt(attr['X-TV-TWITCH-AD-POD-POSITION'] || String(i), 10) || 0;
            const dur = parseFloat(attr['X-TV-TWITCH-AD-DURATION'] || attr['DURATION'] || attr['X-TV-TWITCH-AD-POD-FILLED-DURATION'] || '0') || 0;
            const adDuration = Math.round(dur);

            const payload = {
                stitched: true,
                ad_id: stitchedAdId,
                roll_type: rollType,
                creative_id: attr['X-TV-TWITCH-AD-CREATIVE-ID'] || '',
                order_id: attr['X-TV-TWITCH-AD-ORDER-ID'] || '',
                line_item_id: attr['X-TV-TWITCH-AD-LINE-ITEM-ID'] || '',
                player_mute: false,
                player_volume: 1.0,
                visible: true,
                duration: adDuration,
                ad_position: adPos,
                total_ads: podLength,
            };

            const makePacket = function (eventName, extra) {
                return {
                    operationName: 'ClientSideAdEventHandling_RecordAdEvent',
                    variables: {
                        input: {
                            eventName: eventName,
                            eventPayload: JSON.stringify(Object.assign({}, payload, extra || {})),
                            radToken: radToken,
                        },
                    },
                    extensions: {
                        persistedQuery: {
                            version: 1,
                            sha256Hash: GQL_EVENT_HASH,
                        },
                    },
                };
            };

            spoofedAdIds.add(stitchedAdId);
            recentSpoofedAdIds.set(stitchedAdId, Date.now());
            while (recentSpoofedAdIds.size > 50) {
                const oldest = recentSpoofedAdIds.keys().next().value;
                if (oldest === undefined) break;
                recentSpoofedAdIds.delete(oldest);
            }

            const batch = [
                makePacket('video_ad_impression'),
                makePacket('video_ad_quartile_complete', { quartile: 1 }),
                makePacket('video_ad_quartile_complete', { quartile: 2 }),
                makePacket('video_ad_quartile_complete', { quartile: 3 }),
                makePacket('video_ad_quartile_complete', { quartile: 4 }),
            ];
            if (hasExplicitPodLength && spoofedAdIds.size >= podLength) {
                batch.push(makePacket('video_ad_pod_complete'));
            }

            const headers = Object.assign({}, gqlHeaders, {
                'Content-Type': 'text/plain;charset=UTF-8',
            });
            if (!headers['X-Device-Id']) {
                headers['X-Device-Id'] = headers['Device-ID'] || 'oauth';
            }

            try {
                realFetch('https://gql.twitch.tv/gql', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(batch),
                }).then(function (response) {
                    if (response && response.status !== 200) {
                        report('error', {error: 'Ad spoofing GQL status ' + response.status});
                    }
                }).catch(function (err) {
                    report('error', {error: 'Ad spoofing failed: ' + (err && err.message || err)});
                });
            } catch (err) {
                report('error', {error: 'Ad spoofing sync error: ' + (err && err.message || err)});
            }

            report('ad-spoofed', {count: 1, id: stitchedAdId, roll: rollType});
        }
    }

    function parseVariants(master) {
        const lines = master.split('\n');
        const list = [];
        for (let i = 0; i < lines.length - 1; i++) {
            if (!lines[i].startsWith('#EXT-X-STREAM-INF')) continue;
            const uri = lines[i + 1].trim();
            if (!uri || uri.startsWith('#')) continue;
            const res = (lines[i].match(/RESOLUTION=(\d+x\d+)/) || [])[1] || '';
            const fps = parseFloat((lines[i].match(/FRAME-RATE=([\d.]+)/) || [])[1] || '0');
            list.push({uri: uri, res: res, fps: fps, height: parseInt(res.split('x')[1] || '0', 10)});
        }
        return list;
    }

    function pickVariant(master, res, fps) {
        const list = parseVariants(master);
        if (!list.length) return null;
        const height = parseInt((res || '').split('x')[1] || '0', 10);
        const exact = list.filter(function (v) { return v.res === res; });
        if (exact.length) {
            exact.sort(function (a, b) { return Math.abs(a.fps - fps) - Math.abs(b.fps - fps); });
            return exact[0].uri;
        }
        const lower = list.filter(function (v) { return v.height <= height; });
        const pool = lower.length ? lower : list;
        pool.sort(function (a, b) { return b.height - a.height; });
        return pool[0].uri;
    }

    function loginFromUsher(url) {
        const m = url.match(/\/channel\/hls\/([^/.?]+)\.m3u8/);
        return m ? decodeURIComponent(m[1]).toLowerCase() : null;
    }

    // ---- backup sessions ----
    async function getToken(login, type) {
        const key = login + '|' + type;
        const cached = tokens.get(key);
        if (cached && Date.now() - cached.ts < 5 * 60 * 1000) return cached;
        const body = JSON.stringify({
            operationName: 'PlaybackAccessToken_Template',
            query: GQL_QUERY,
            variables: {isLive: true, login: login, isVod: false, vodID: '', playerType: type, platform: 'web'}
        });
        const r = await withTimeout(realFetch('https://gql.twitch.tv/gql', {method: 'POST', headers: gqlHeaders, body: body}));
        const j = await r.json();
        const t = j && j.data && j.data.streamPlaybackAccessToken;
        if (!t || !t.value || !t.signature) throw new Error('no token for ' + type);
        const token = {value: t.value, signature: t.signature, ts: Date.now()};
        tokens.set(key, token);
        return token;
    }

    function randomHex(n) {
        let s = '';
        for (let i = 0; i < n; i++) s += Math.floor(Math.random() * 16).toString(16);
        return s;
    }

    async function openSession(info, type) {
        const token = await getToken(info.login, type);
        const u = new URL(info.usher);
        u.searchParams.set('sig', token.signature);
        u.searchParams.set('token', token.value);
        u.searchParams.set('p', String(Math.floor(Math.random() * 1e7)));
        u.searchParams.set('play_session_id', randomHex(32));
        const master = await fetchText(u.href);
        if (!parseVariants(master).length) throw new Error('no variants');
        return {master: master, created: Date.now(), retryAt: 0, last: null};
    }

    // The backup session's playlist for the resolution the player asked for (null on failure).
    async function backupText(info, type) {
        const key = info.login + '|' + type;
        let session = sessions.get(key);
        for (let attempt = 0; attempt < 2; attempt++) {
            const fresh = !session || !session.master || Date.now() - session.created > SESSION_MAX_AGE;
            try {
                if (fresh) {
                    session = await openSession(info, type);
                    sessions.set(key, session);
                }
                return {session: session, fresh: fresh,
                        text: await fetchText(pickVariant(session.master, info.res, info.fps))};
            } catch (e) {
                if (!fresh) {          // old session expired: try once with a new one
                    session = null;
                    continue;
                }
                sessions.set(key, {master: null, created: 0, retryAt: Date.now() + 30 * 1000, last: 'fehler'});
                report('backup-result', {type: type, result: 'fehler', error: String(e && e.message || e)});
                return null;
            }
        }
        return null;
    }

    function noteResult(session, type, result, extra) {
        if (session.last === result) return;  // only changes, not every 2 s
        session.last = result;
        report('backup-result', Object.assign({type: type, result: result}, extra || {}));
    }

    async function findAdFreeBackup(info) {
        for (let i = 0; i < BACKUP_TYPES.length; i++) {
            const type = BACKUP_TYPES[i];
            const known = sessions.get(info.login + '|' + type);
            if (known && known.retryAt > Date.now()) continue;
            const b = await backupText(info, type);
            if (!b) continue;
            if (hasAds(b.text)) {
                // keep the session: its own ad ends after a while, a new one would start a new ad
                b.session.retryAt = Date.now() + 15 * 1000;
                noteResult(b.session, type, 'werbung', {neu: b.fresh, endsAt: adEndsAt(b.text)});
                continue;
            }
            noteResult(b.session, type, 'frei', {neu: b.fresh});
            return {type: type, text: b.text};
        }
        return null;
    }

    // ---- what the player gets ----
    function enterAdBreak(text) {
        if (inAdBreak) return;
        inAdBreak = true;
        report('ad-start', {playlist: text.slice(0, 15000), endsAt: adEndsAt(text)});  // kept for the ad log
    }

    function leaveAdBreak() {
        if (!inAdBreak) return;
        inAdBreak = false;
        spoofedAdIds.clear();
        report('ad-end');
    }

    function masked(text) {
        enterAdBreak(text);
        report('masked', {endsAt: adEndsAt(text)});
        return text;
    }

    async function processMediaPlaylist(url, text) {
        const info = variants.get(url);
        const login = info && info.login;

        if (hasAds(text)) {
            notifyAdComplete(text).catch(function () {});
        }

        const stickyType = login && sticky.get(login);
        if (stickyType) {
            const b = await backupText(info, stickyType);
            if (b) {
                if (hasAds(b.text)) {
                    notifyAdComplete(b.text).catch(function () {});
                    return masked(b.text);   // ad break reached the backup too
                }
                leaveAdBreak();
                if (hasAds(text)) report('replaced');
                return b.text;
            }
            sticky.delete(login);  // backup unusable: continue with the player's own session
        }

        if (!hasAds(text)) {
            leaveAdBreak();
            return text;
        }
        enterAdBreak(text);
        if (!login) {
            report('backup-result', {type: '-', result: 'fehler', error: 'Playlist nicht in der Master-Liste'});
            return masked(text);
        }
        const backup = await findAdFreeBackup(info);
        if (backup) {
            sticky.set(login, backup.type);
            report('backup', {type: backup.type, res: info.res});
            report('replaced');
            leaveAdBreak();
            return backup.text;
        }
        return masked(text);
    }

    self.fetch = async function (input, init) {
        const url = typeof input === 'string' ? input : (input && input.url) || String(input);
        const isUsher = url.indexOf('usher.ttvnw.net/api/') !== -1 && url.indexOf('/channel/hls/') !== -1;
        const isMedia = !isUsher && url.indexOf('.ttvnw.net/v1/playlist/') !== -1;
        if (!isUsher && !isMedia) return realFetch(input, init);

        report(isUsher ? 'seen-master' : 'seen-playlist');
        const resp = await realFetch(input, init);
        if (!resp.ok) return resp;
        const text = await resp.text();
        let out = text;
        try {
            if (isUsher) {
                const login = loginFromUsher(url);
                parseVariants(text).forEach(function (v) {
                    variants.set(v.uri, {login: login, res: v.res, fps: v.fps, usher: url});
                });
            } else {
                out = await processMediaPlaylist(url, text);
            }
        } catch (e) {
            report('error', {error: String(e && e.message || e)});
        }
        return new Response(out, {status: resp.status, statusText: resp.statusText, headers: resp.headers});
    };

    // exposed for tests only
    self.__abTwitchTest = {
        hasAds: hasAds,
        pickVariant: pickVariant,
        adEndsAt: adEndsAt,
        parseAttrs: parseAttrs,
        notifyAdComplete: notifyAdComplete,
        spoofedAdIds: spoofedAdIds,
        recentSpoofedAdIds: recentSpoofedAdIds
    };
    report('worker-hooked');
})();
