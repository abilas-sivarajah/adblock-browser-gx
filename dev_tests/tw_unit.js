// Offline tests for scripts/twitch_worker.js: real playlists captured from Twitch (tw_ad_*.m3u8)
// and simulated sessions with PROGRAM-DATE-TIME, as Twitch numbers each session differently.
const fs = require('fs');
const path = require('path');
const APP = path.join(__dirname, '..');
const S = __dirname;
const HOLD_B64 = fs.readFileSync(path.join(APP, 'scripts/twitch_hold.ts')).toString('base64');
const SRC = fs.readFileSync(path.join(APP, 'scripts/twitch_worker.js'), 'utf8')
    .replace('__AB_HOLD_SEGMENT__', JSON.stringify(HOLD_B64));
const TIMING = {proof: 0, hqDwell: 0, search: 400, fetch: 1000, spoofRealtime: false, spoofHeaderWait: 0, spoofRetry: 0};

const adMaster = fs.readFileSync(path.join(S, 'tw_ad_master.m3u8'), 'utf8');
const adMedia = fs.readFileSync(path.join(S, 'tw_ad_media.m3u8'), 'utf8');

let passed = 0, failed = 0;
function check(name, ok, detail) {
    if (ok) passed++; else failed++;
    console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? '  [' + detail + ']' : ''));
}

// twitch_main.js is not run here, but must at least parse (a merge once dropped a "};" and the
// whole Twitch script stopped working)
try {
    new Function(fs.readFileSync(path.join(APP, 'scripts/twitch_main.js'), 'utf8'));
    check('0 scripts/twitch_main.js parses', true);
} catch (e) {
    check('0 scripts/twitch_main.js parses', false, e.message);
}

// ---- simulated Twitch ----
// Content index c = 2 s of stream at T0 + 2c s. Each session numbers its segments c + delta.
const T0 = Date.parse('2026-10-04T16:00:00.000Z');
const iso = (c) => new Date(T0 + c * 2000).toISOString();
const SESS = {
    native: {tag: 'orig', delta: 100},
    popout: {tag: 'popout', delta: 5000},
    frontpage: {tag: 'front', delta: 6000},
    mobile_web: {tag: 'mweb', delta: 7000},
    site: {tag: 'site', delta: 8000},
    autoplay: {tag: 'auto', delta: 9000},
};

function playlist(sess, k, opts) {
    opts = opts || {};
    const ads = opts.ads || (() => false);
    const n = opts.n || 5;
    const lines = ['#EXTM3U', '#EXT-X-VERSION:3', '#EXT-X-TARGETDURATION:6', '#EXT-X-MEDIA-SEQUENCE:' + (k - n + 1 + sess.delta),
                   '#EXT-X-DATERANGE:ID="playlist-session-1",CLASS="twitch-session",START-DATE="' + iso(0) + '",END-ON-NEXT=YES,X-TV-TWITCH-SESSIONID="' + sess.tag + '"'];
    for (let c = k - n + 1; c <= k; c++) {
        const ad = ads(c);
        if (ad && (c === k - n + 1 || !ads(c - 1))) {
            let start = c;
            while (ads(start - 1)) start--;  // the ad's tag keeps its id while the ad is in the window
            lines.push('#EXT-X-DATERANGE:ID="stitched-ad-' + sess.tag + start + '",CLASS="twitch-stitched-ad",START-DATE="' + iso(c) + '",DURATION=30.000,X-TV-TWITCH-AD-POD-LENGTH="1"');
            lines.push('#EXT-X-DISCONTINUITY');
            if (opts.adMap) lines.push('#EXT-X-MAP:URI="https://' + sess.tag + '.example/adinit.mp4"');
        }
        if (!ad && c > k - n + 1 && ads(c - 1)) lines.push('#EXT-X-DISCONTINUITY');
        if (!ad && opts.fmp4 && (c === k - n + 1 || ads(c - 1))) lines.push('#EXT-X-MAP:URI="https://' + sess.tag + '.example/init.mp4"');
        lines.push('#EXT-X-PROGRAM-DATE-TIME:' + iso(c), '#EXTINF:2.000,' + (ad ? 'Amazon|123' : 'live'),
                   'https://' + sess.tag + '.example/' + (ad ? 'ad' : 'seg') + c + (opts.fmp4 && !ad ? '.mp4' : '.ts'));
    }
    if (opts.prefetch) lines.push('#EXT-X-TWITCH-PREFETCH:https://' + sess.tag + '.example/seg' + (k + 1) + '.ts');
    return lines.join('\n') + '\n';
}

const ORIG = (q) => 'https://euc1.playlist.ttvnw.net/v1/playlist/ORIGINAL-' + q + '.m3u8';
function master(variantUrl, codecs) {
    codecs = codecs || 'avc1.4D401F,mp4a.40.2';
    return '#EXTM3U\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=6000000,RESOLUTION=1920x1080,CODECS="' + codecs + '",FRAME-RATE=60.000,IVS-NAME="1080p60"\n' + variantUrl('1080') + '\n' +
        '#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720,CODECS="' + codecs + '",FRAME-RATE=60.000,IVS-NAME="720p60"\n' + variantUrl('720') + '\n';
}
const lqMaster = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=630000,RESOLUTION=640x360,CODECS="avc1.4D401E,mp4a.40.2",FRAME-RATE=30.000,IVS-NAME="360p30"\nhttps://x/autoplay-360.m3u8\n';
const USHER = 'https://usher.ttvnw.net/api/v2/channel/hls/gotaga.m3u8?sig=player&token=x&supported_codecs=avc1';

// A fake Twitch: `world` decides what each session shows at the current clock `world.k`.
function makeWorld(over) {
    const world = Object.assign({
        k: 20,
        ads: {},            // session name -> (c) => is ad
        gone: {},           // session name -> true: its playlists answer 404
        forbidden: {},      // session name -> true: anonymous token refused
        nativeCodecs: null, backupCodecs: null,
        fmp4: false, adMap: false, prefetch: false,
        gqlFails: false,
    }, over || {});
    world.log = [];
    world.gqlTypes = [];
    world.gqlHeaders = [];
    world.routes = function (url, init) {
        world.log.push(((init && init.method) || 'GET') + ' ' + url.slice(0, 160));
        if (url.indexOf('gql.twitch.tv') !== -1) {
            if (world.gqlFails) throw new TypeError('Failed to fetch');
            const body = JSON.parse(init.body);
            if (Array.isArray(body)) {
                if (world.spoofFailCount > 0) {
                    world.spoofFailCount--;
                    throw new TypeError('Failed to fetch');
                }
                if (world.spoofBatches) world.spoofBatches.push(body);
                if (world.spoofHeaders) world.spoofHeaders.push(init && init.headers);
                return body.map(() => ({data: {recordAdEvent: true}}));
            }
            const t = body.variables.playerType;
            world.gqlTypes.push(t + '/' + body.variables.platform);
            world.gqlHeaders.push(init.headers);
            const refused = world.forbidden[t] && !init.headers.Authorization;
            return {data: {streamPlaybackAccessToken: {value: '{"player_type":"' + t + '"}', signature: 'sig-' + t,
                                                       authorization: {isForbidden: !!refused, forbiddenReasonCode: refused ? 'UNAUTHORIZED' : 'NONE'}}}};
        }
        if (url.indexOf('usher.ttvnw.net') !== -1) {
            const m = url.match(/sig=sig-([a-z_]+)/);
            if (!m) return master(ORIG, world.nativeCodecs);
            if (m[1] === 'autoplay') return lqMaster;
            return master((q) => 'https://x/' + m[1] + '-' + q + '.m3u8', world.backupCodecs);
        }
        const opts = (name) => ({ads: world.ads[name], fmp4: world.fmp4, adMap: world.adMap, prefetch: world.prefetch});
        if (url.indexOf('ORIGINAL-') !== -1) return world.gone.native ? 404 : playlist(SESS.native, world.k, opts('native'));
        const b = url.match(/^https:\/\/x\/([a-z_]+)-\d+\.m3u8/);
        if (b) return world.gone[b[1]] ? 404 : playlist(SESS[b[1]], world.k, opts(b[1]));
        if (url.indexOf('example.com') !== -1) return 'hello';
        return 404;
    };
    return world;
}

function makeWorker(world, init) {
    const self = {};
    const events = [];
    const listeners = [];
    const page = {onRequest: null};
    class FakeChannel {
        addEventListener(type, fn) { listeners.push(fn); }
        postMessage(m) {
            events.push(m);
            if (m.event === 'fetch-request' && page.onRequest) page.onRequest(m);
        }
    }
    self.fetch = async (input, opts) => {
        const url = typeof input === 'string' ? input : input.url;
        const body = world.routes(url, opts);
        if (body === 404) return new Response('gone', {status: 404});
        return new Response(typeof body === 'string' ? body : JSON.stringify(body), {status: 200});
    };
    const cfg = Object.assign({clientId: 'test', deviceId: 'dev12345', backupTypes: ['popout', 'frontpage', 'mobile_web', 'site', 'autoplay'],
                               channel: 't', timing: TIMING}, init || {});
    new Function('self', 'BroadcastChannel', SRC.replace('__AB_WORKER_INIT__', JSON.stringify(cfg)))(self, FakeChannel);
    self.events = events;
    self.pageSend = (m) => listeners.forEach((fn) => fn({data: m}));
    self.page = page;
    return self;
}

// What the player sees: segments of each response with their numbers. Checks that a number always
// means the same segment, numbers only go up, and content never repeats or skips (except across holds).
function Player(worker) {
    const t = worker.__abTwitchTest;
    const bySeq = new Map();
    const p = {problems: [], outputs: [], lastSeq: -1, lastContent: null, afterHold: false};
    p.take = (text) => {
        p.outputs.push(text);
        const parsed = t.parseMedia(text, null);
        parsed.segs.forEach((s) => {
            const known = bySeq.get(s.seq);
            if (known && known !== s.uri) p.problems.push('#' + s.seq + ' changed ' + known + ' -> ' + s.uri);
            bySeq.set(s.seq, s.uri);
            if (s.seq <= p.lastSeq) return;
            if (p.lastSeq >= 0 && s.seq !== p.lastSeq + 1) p.problems.push('gap ' + p.lastSeq + ' -> ' + s.seq);
            p.lastSeq = s.seq;
            const m = s.uri.match(/(seg|ad)(\d+)\./);
            if (!m) { p.afterHold = true; return; }  // hold segment
            const c = parseInt(m[2], 10);
            if (p.lastContent !== null && !p.afterHold && c !== p.lastContent + 1) p.problems.push('content ' + p.lastContent + ' -> ' + c + ' at #' + s.seq);
            if (p.lastContent !== null && p.afterHold && c <= p.lastContent) p.problems.push('repeat after hold ' + p.lastContent + ' -> ' + c);
            p.lastContent = c;
            p.afterHold = false;
        });
        return parsed;
    };
    return p;
}

async function poll(w, player, world, url) {
    world.k++;
    const text = await (await w.fetch(url || ORIG('720'))).text();
    return {text: text, parsed: player.take(text)};
}
const tags = (parsed) => parsed.segs.map((s) => s.uri.split('/')[2].split('.')[0]);
const count = (log, s) => log.filter((l) => l.includes(s)).length;
const ev = (w, name) => w.events.filter((e) => e.event === name);

(async () => {
    // ---- parsing ----
    const t = makeWorker(makeWorld()).__abTwitchTest;
    check('ad playlist is detected', t.hasAds(adMedia));
    check('live playlist is not flagged', !t.hasAds(playlist(SESS.native, 10)));
    const variants = t.parseVariants(adMaster, 'https://usher.ttvnw.net/x.m3u8');
    const v720 = t.pickVariant(variants, {res: '1280x720', fps: 60, height: 720, family: 'avc', name: '720p60'});
    check('variant picking finds the 720p60 rendition', !!v720 && v720.name === '720p60' && adMaster.includes(v720.uri));
    check('a backup without the player\'s codec is not used', t.pickVariant(variants, {res: '1280x720', fps: 60, height: 720, family: 'hevc'}) === null);
    check('end of the ad pod is read from the playlist', t.adEndsAt(adMedia) === Date.parse('2026-10-04T16:03:57.709Z') + 15235);
    const pm = t.parseMedia(adMedia, null);
    const round = t.parseMedia(t.render(pm.header, pm.segs.map((s) => Object.assign({out: s.seq}, s)), pm.tail), null);
    check('parse + render keeps segments, numbers and init map', round.segs.length === 4 && round.segs.every((s, i) =>
        s.uri === pm.segs[i].uri && s.seq === pm.segs[i].seq && s.map === pm.segs[i].map && s.pdt === pm.segs[i].pdt) && !!round.segs[0].map);
    const mixed = t.parseMedia(playlist(SESS.native, 30, {ads: (c) => c >= 27 && c <= 28, adMap: true}), null);
    check('an ad\'s EXT-X-MAP does not stick to the live segments after it', mixed.segs[2].map && !mixed.segs[4].map);

    // ---- hold segment ----
    const h1 = t.holdSegment(1), h3 = t.holdSegment(3);
    const firstPts = (b) => {
        for (let i = 0; i < b.length; i += 188) {
            if (!(b[i + 1] & 0x40)) continue;
            let p = i + 4;
            if (b[i + 3] & 0x20) p += 1 + b[p];
            if (b[p] === 0 && b[p + 1] === 0 && b[p + 2] === 1) {
                const o = p + 9;
                return ((b[o] >> 1) & 7) * 1073741824 + b[o + 1] * 4194304 + (b[o + 2] >> 1) * 32768 + b[o + 3] * 128 + (b[o + 4] >> 1);
            }
        }
        return -1;
    };
    check('hold segment: valid MPEG-TS, timestamps move on 1.024 s per number',
          h1.length % 188 === 0 && h1.every((x, i) => i % 188 || x === 0x47) && firstPts(h3) - firstPts(h1) === 2 * 92160);

    // 1) preroll in the player's session: 360p bridge at once, full quality after a second look,
    //    back to the player's own session once it is ad-free - one continuous timeline
    {
        const world = makeWorld({ads: {native: (c) => c >= 15 && c <= 32}, prefetch: true});
        const w = makeWorker(world);
        const player = Player(w);
        await w.fetch(USHER);
        let r = await poll(w, player, world);
        check('1a ad: the player gets the 360p bridge right away', tags(r.parsed).every((x) => x === 'auto') && !/Amazon|stitched-ad/.test(r.text),
              tags(r.parsed).join(','));
        check('1b autoplay is asked with platform android', world.gqlTypes.includes('autoplay/android') && world.gqlTypes.includes('popout/web'));
        r = await poll(w, player, world);
        check('1c second look: full quality (popout) takes over', tags(r.parsed).slice(-1)[0] === 'popout', tags(r.parsed).join(','));
        check('1d the change is a discontinuity, aligned in time', /#EXT-X-DISCONTINUITY\n(#EXT-X-PROGRAM-DATE-TIME:[^\n]+\n)?#EXTINF:2.000,live\nhttps:\/\/popout/.test(r.text));
        for (let i = 0; i < 5; i++) r = await poll(w, player, world);
        check('1e popout session is reused (one token, one master)', count(world.log, 'sig=sig-popout') === 1 && world.gqlTypes.filter((x) => x.startsWith('popout')).length === 1);
        check('1f prefetch hint of the backup is passed on', /#EXT-X-TWITCH-PREFETCH:https:\/\/popout/.test(r.text));
        // ad over (window clean from k=37): 3 new clean playlists, then back to the own session
        while (world.k < 37) r = await poll(w, player, world);
        r = await poll(w, player, world);
        check('1g still on popout during the 3 clean playlists', tags(r.parsed).slice(-1)[0] === 'popout');
        r = await poll(w, player, world);
        check('1h then back to the player\'s own session', tags(r.parsed).slice(-1)[0] === 'orig', tags(r.parsed).join(','));
        for (let i = 0; i < 6; i++) r = await poll(w, player, world);
        check('1i own session continues on the same timeline', tags(r.parsed).every((x) => x === 'orig') && player.problems.length === 0,
              player.problems.slice(0, 3).join('; '));
        check('1j events: bridge, backup, back home, no hold/mask',
              ev(w, 'bridge').length === 2 && ev(w, 'replaced').length === 1 && ev(w, 'native-back').length === 1 &&
              ev(w, 'masked').length === 0 && ev(w, 'ad-start').length === 1 && ev(w, 'ad-end').length === 1);
        check('1k ad seconds reported once per ad', ev(w, 'ad-seconds').reduce((a, e) => a + e.seconds, 0) === 30);
    }

    // 2) streamer ad break: every session has ads -> black hold segments, afterwards live without replay
    {
        const ads = (c) => c >= 22 && c <= 40;
        const world = makeWorld({ads: {native: ads, popout: ads, frontpage: ads, mobile_web: ads, site: ads, autoplay: ads}});
        const w = makeWorker(world);
        const player = Player(w);
        await w.fetch(USHER);
        let r = await poll(w, player, world);       // k=21: clean
        check('2a clean stream is passed on unchanged', r.text === playlist(SESS.native, 21));
        const outs = [];
        for (let i = 0; i < 8; i++) outs.push(await poll(w, player, world));
        check('2b no ad reaches the player (only live and hold segments)', outs.every((o) => !/Amazon|stitched-ad|\/ad\d/.test(o.text)));
        check('2c hold segments are used', outs.slice(1).every((o) => o.text.includes('__adblock_gx_hold.ts')));
        check('2d page covers the player (hold)', ev(w, 'masked').length >= 7 && ev(w, 'masked').every((e) => e.hold));
        check('2e no session churn: one session per backup type', ['popout', 'frontpage', 'mobile_web', 'site', 'autoplay'].every((x) => count(world.log, 'sig=sig-' + x) === 1));
        while (world.k < 45) r = await poll(w, player, world);
        check('2f after the break: live again, continuing at the current time', tags(r.parsed).slice(-1)[0] === 'orig' && player.lastContent === 45,
              tags(r.parsed).join(',') + ' last ' + player.lastContent);
        check('2g numbering stayed continuous', player.problems.length === 0, player.problems.slice(0, 3).join('; '));
        check('2h overlay removed afterwards', w.events.slice(-12).some((e) => e.event === 'unmasked'));
    }

    // 2x) same in an fMP4 stream: hold not possible -> ad passed on, covered and muted
    {
        const ads = (c) => c >= 22 && c <= 40;
        const world = makeWorld({fmp4: true, ads: {native: ads, popout: ads, frontpage: ads, mobile_web: ads, site: ads, autoplay: ads}});
        const w = makeWorker(world);
        const player = Player(w);
        await w.fetch(USHER);
        await poll(w, player, world);
        let r;
        for (let i = 0; i < 4; i++) r = await poll(w, player, world);
        check('2x fMP4: ad passed on and masked (no hold)', !r.text.includes('__adblock_gx_hold') && /Amazon/.test(r.text) &&
              ev(w, 'masked').length === 4 && ev(w, 'masked').every((e) => !e.hold));
    }

    // 3) the backup in use runs into an ad later: own session clean -> back to it, else bridge, else hold
    {
        const world = makeWorld({ads: {native: (c) => c >= 21 && c <= 60}});
        const w = makeWorker(world);
        const player = Player(w);
        await w.fetch(USHER);
        await poll(w, player, world);
        let r = await poll(w, player, world);
        check('3a on popout', tags(r.parsed).slice(-1)[0] === 'popout');
        world.ads.popout = (c) => c >= 23 && c <= 50;
        world.ads.frontpage = world.ads.mobile_web = world.ads.site = world.ads.popout;
        r = await poll(w, player, world);
        check('3b popout with ads -> the 360p bridge', tags(r.parsed).slice(-1)[0] === 'auto' && !/Amazon/.test(r.text), tags(r.parsed).join(','));
        world.ads.autoplay = world.ads.popout;
        r = await poll(w, player, world);
        check('3c bridge with ads too -> hold', r.text.includes('__adblock_gx_hold') && !/Amazon/.test(r.text));
        check('3d numbering continuous throughout', player.problems.length === 0, player.problems.slice(0, 3).join('; '));
    }

    // 4) the backup in use disappears: reopened once; still gone -> next source
    {
        const world = makeWorld({ads: {native: (c) => c >= 21 && c <= 60}});
        const w = makeWorker(world);
        const player = Player(w);
        await w.fetch(USHER);
        await poll(w, player, world);
        await poll(w, player, world);
        world.gone.popout = true;
        const r = await poll(w, player, world);
        check('4 vanished backup: reopened once, then the next player type', count(world.log, 'sig=sig-popout') === 2 &&
              ['front', 'auto'].includes(tags(r.parsed).slice(-1)[0]) && player.problems.length === 0, tags(r.parsed).join(','));
    }

    // 5) no ads at all: nothing extra is requested, the playlist is not touched
    {
        const world = makeWorld();
        const w = makeWorker(world);
        await w.fetch(USHER);
        world.k++;
        const r = await (await w.fetch(ORIG('720'))).text();
        check('5 ad-free stream: original passed on, no backup requests', r === playlist(SESS.native, world.k) && world.gqlTypes.length === 0);
    }

    // 6) HEVC stream, backups only have H.264: no backup, no hold -> masked
    {
        const world = makeWorld({nativeCodecs: 'hvc1.1.6.L120.90,mp4a.40.2', ads: {native: (c) => c >= 21}});
        const w = makeWorker(world);
        const player = Player(w);
        await w.fetch(USHER);
        const r = await poll(w, player, world);
        check('6 HEVC: H.264 backups are not mixed in, ad covered', tags(r.parsed).every((x) => x === 'orig') && ev(w, 'masked').length === 1 &&
              ev(w, 'backup-result').some((e) => /Codec/.test(e.error || '')));
    }

    // 7) login token only when Twitch refuses anonymous viewers
    {
        const world = makeWorld({ads: {native: (c) => c >= 21}, forbidden: {popout: true}});
        const w = makeWorker(world, {backupTypes: ['popout']});
        w.pageSend({event: 'viewer', headers: {Authorization: 'OAuth abc', 'Client-Version': 'v1', 'Client-Session-Id': 's1'}});
        const player = Player(w);
        await w.fetch(USHER);
        await poll(w, player, world);
        const h = world.gqlHeaders;
        check('7 anonymous first, then with the viewer\'s login (forbidden)', h.length === 2 && !h[0].Authorization && h[1].Authorization === 'OAuth abc' &&
              h[0]['Client-Version'] === 'v1' && h[0]['Client-Session-Id'] === 's1' && h[0]['X-Device-Id'] === 'dev12345');
    }

    // 8) GQL from the worker fails -> relayed through the page
    {
        const world = makeWorld({ads: {native: (c) => c >= 21}});
        const w = makeWorker(world, {backupTypes: ['autoplay']});
        let relayed = 0;
        w.page.onRequest = (m) => {
            relayed++;
            const body = JSON.parse(m.init.body);
            setTimeout(() => w.pageSend({event: 'fetch-response', id: m.id, status: 200, body: JSON.stringify(
                {data: {streamPlaybackAccessToken: {value: '{}', signature: 'sig-' + body.variables.playerType}}})}), 5);
        };
        world.gqlFails = true;
        const player = Player(w);
        await w.fetch(USHER);
        const r = await poll(w, player, world);
        check('8 token request relayed through the page', relayed === 1 && tags(r.parsed).every((x) => x === 'auto'));
    }

    // 9) VOD: ad segments left out, VAST requests blocked on VOD pages
    {
        const world = makeWorld();
        const vodMaster = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720,CODECS="avc1.4D401F,mp4a.40.2",FRAME-RATE=30.000\nhttps://d1.cloudfront.net/abc/720p30/index-dvr.m3u8\n';
        const vod = ['#EXTM3U', '#EXT-X-VERSION:3', '#EXT-X-TARGETDURATION:10', '#EXT-X-PLAYLIST-TYPE:VOD', '#EXT-X-MEDIA-SEQUENCE:0',
                     '#EXT-X-DATERANGE:ID="stitched-ad-1",CLASS="twitch-stitched-ad",START-DATE="' + iso(0) + '",DURATION=20.000',
                     '#EXTINF:10.000,Amazon|1', 'https://ads.example/ad0.ts', '#EXTINF:10.000,Amazon|1', 'https://ads.example/ad1.ts',
                     '#EXT-X-DISCONTINUITY', '#EXTINF:10.000,', 'https://d1.cloudfront.net/abc/720p30/0.ts',
                     '#EXTINF:10.000,', 'https://d1.cloudfront.net/abc/720p30/1.ts', '#EXT-X-ENDLIST'].join('\n');
        const routes = world.routes;
        world.routes = (url, init) => url.indexOf('/vod/') !== -1 ? vodMaster : url.indexOf('index-dvr') !== -1 ? vod : routes(url, init);
        const w = makeWorker(world, {vod: true});
        await w.fetch('https://usher.ttvnw.net/vod/2575862349.m3u8?sig=x&token=y');
        const r = await (await w.fetch('https://d1.cloudfront.net/abc/720p30/index-dvr.m3u8')).text();
        const p = w.__abTwitchTest.parseMedia(r, null);
        check('9a VOD: ad segments removed, the rest kept with ENDLIST', p.segs.length === 2 && p.ended && !/Amazon|stitched/.test(r) &&
              p.segs[0].uri.endsWith('/0.ts'));
        const vast = await w.fetch('https://edge.ads.twitch.tv/ads?x=1');
        check('9b VOD: VAST ad request answered empty', vast.status === 204 && count(world.log, 'edge.ads') === 0);
    }

    // 10) hold segment request and unrelated requests
    {
        const world = makeWorld();
        const w = makeWorker(world);
        const hold = await w.fetch('https://www.twitch.tv/__adblock_gx_hold.ts?n=4');
        const bytes = new Uint8Array(await hold.arrayBuffer());
        check('10a hold segment is served by the worker', hold.status === 200 && bytes.length === h1.length && bytes[0] === 0x47);
        check('10b other requests are not touched', await (await w.fetch('https://example.com/a')).text() === 'hello');
    }

    // 11) Ad Spoofing (TTV-AB technique, a setting): reports impressions, quartiles & pod complete to Twitch GQL
    {
        const world = makeWorld({
            ads: {native: () => true}
        });
        world.spoofBatches = [];
        const origRoutes = world.routes;
        world.routes = (url, init) => {
            if (url.indexOf('ORIGINAL-') !== -1) {
                return adMedia;
            }
            return origRoutes(url, init);
        };
        const w = makeWorker(world, {adSpoofing: true, relay: false});
        const t = w.__abTwitchTest;
        const names = () => world.spoofBatches.map((b) => b[0] && b[0].variables.input.eventName);

        // 11a attribute parser
        const parsed = t.parseAttrs('#EXT-X-DATERANGE:ID="stitched-ad-test",CLASS="twitch-stitched-ad",DURATION=15.235,X-TV-TWITCH-AD-ROLL-TYPE="PREROLL"');
        check('11a parseAttrs parses quoted and unquoted attributes',
              parsed.ID === 'stitched-ad-test' && parsed['X-TV-TWITCH-AD-ROLL-TYPE'] === 'PREROLL' && parsed.DURATION === '15.235');

        // 11b fetch ad playlist triggers notifyAdComplete
        await w.fetch(USHER);
        await w.fetch(ORIG('720'));

        check('11b ad playlist triggers GQL ad spoofing events', world.spoofBatches.length >= 6);
        check('11c events are impression, 4 quartiles and pod complete (one GQL each)',
              names().slice(0, 6).join(',') === 'video_ad_impression,video_ad_quartile_complete,video_ad_quartile_complete,video_ad_quartile_complete,video_ad_quartile_complete,video_ad_pod_complete');

        const firstPayload = world.spoofBatches[0] ? JSON.parse(world.spoofBatches[0][0].variables.input.eventPayload) : {};
        check('11d packet payload contains stitched ad details and RADS token',
              firstPayload.stitched === true &&
              firstPayload.ad_id === 'stitched-ad-1791129837-15235000000' &&
              firstPayload.roll_type === 'preroll' &&
              firstPayload.creative_id === '2488883100494' &&
              firstPayload.duration === 15 &&
              world.spoofBatches[0][0].variables.input.radToken.startsWith('eyJhbGci') &&
              world.spoofBatches[0][0].extensions.persistedQuery.sha256Hash === '7e6c69e6eb59f8ccb97ab73686f3d8b7d85a72a0298745ccd8bfc68e4054ca5b');

        // 11e deduplication: second poll of the same playlist does not send another batch
        const countBefore = world.spoofBatches.length;
        await w.fetch(ORIG('720'));
        check('11e deduplication prevents re-spoofing the same ad ID', world.spoofBatches.length === countBefore);

        // 11f broadcast event sent
        check('11f ad-spoofed event reported on channel',
              w.events.some(e => e.event === 'ad-spoofed' && e.id === 'stitched-ad-1791129837-15235000000'));

        // 11g off by default: without the setting nothing is reported
        const world2 = makeWorld({ads: {native: () => true}});
        world2.spoofBatches = [];
        const origRoutes2 = world2.routes;
        world2.routes = (url, init) => url.indexOf('ORIGINAL-') !== -1 ? adMedia : origRoutes2(url, init);
        const w2 = makeWorker(world2, {relay: false});
        await w2.fetch(USHER);
        await w2.fetch(ORIG('720'));
        check('11g without the setting no spoofing batch is sent',
              world2.spoofBatches.length === 0 && !w2.events.some(e => e.event === 'ad-spoofed'));

        function stitched(ads) {
            return '#EXTM3U\n' + ads.map((a) => {
                let line = '#EXT-X-DATERANGE:ID="' + a.id + '",CLASS="twitch-stitched-ad",DURATION=' + (a.duration || 12) +
                    ',X-TV-TWITCH-AD-ROLL-TYPE="' + (a.roll || 'MIDROLL') + '"';
                if (a.pod) line += ',X-TV-TWITCH-AD-POD-LENGTH="' + a.pod + '"';
                if (a.pos != null) line += ',X-TV-TWITCH-AD-POD-POSITION="' + a.pos + '"';
                if (a.rad) line += ',X-TV-TWITCH-AD-RADS-TOKEN="' + a.rad + '"';
                if (a.creative) line += ',X-TV-TWITCH-AD-CREATIVE-ID="' + a.creative + '"';
                return line;
            }).join('\n') + '\n';
        }

        // 11h second pod after endAd: new IDs are spoofed again
        {
            const worldH = makeWorld();
            worldH.spoofBatches = [];
            const wH = makeWorker(worldH, {adSpoofing: true, relay: false});
            const tH = wH.__abTwitchTest;
            await tH.notifyAdComplete(stitched([{id: 'stitched-ad-pod1', pod: 1, pos: 0, rad: 'tok-1'}]));
            const afterFirst = worldH.spoofBatches.length;
            tH.resetSpoofPod();
            await tH.notifyAdComplete(stitched([{id: 'stitched-ad-pod2', pod: 1, pos: 0, rad: 'tok-2'}]));
            check('11h second pod after reset is spoofed',
                  afterFirst >= 6 && worldH.spoofBatches.length >= afterFirst + 6 &&
                  worldH.spoofBatches[afterFirst][0].variables.input.radToken === 'tok-2');
        }

        // 11i bounce: same IDs after reset do not re-send impression, but missing pod_complete is healed
        {
            const worldB = makeWorld();
            worldB.spoofBatches = [];
            const wB = makeWorker(worldB, {adSpoofing: true, relay: false});
            const tB = wB.__abTwitchTest;
            const pl = stitched([{id: 'stitched-ad-bounce', pod: 1, pos: 0, rad: 'tok-b'}]);
            await tB.notifyAdComplete(pl);
            const n = worldB.spoofBatches.length;
            const pods = worldB.spoofBatches.filter((b) => b[0].variables.input.eventName === 'video_ad_pod_complete').length;
            tB.resetSpoofPod();
            await tB.notifyAdComplete(pl);
            const podsAfter = worldB.spoofBatches.filter((b) => b[0].variables.input.eventName === 'video_ad_pod_complete').length;
            check('11i bounce does not re-spoof the same ad, pod_complete stays once',
                  worldB.spoofBatches.length === n && pods === 1 && podsAfter === 1);
        }

        // 11j missing RADS token: nothing is sent
        {
            const worldM = makeWorld();
            worldM.spoofBatches = [];
            const wM = makeWorker(worldM, {adSpoofing: true, relay: false});
            await wM.__abTwitchTest.notifyAdComplete(stitched([{id: 'stitched-ad-notoken', pod: 1, pos: 0}]));
            check('11j missing RADS token sends no GQL', worldM.spoofBatches.length === 0);
        }

        // 11k GQL failure is retried
        {
            const worldR = makeWorld();
            worldR.spoofBatches = [];
            worldR.spoofFailCount = 1;
            const wR = makeWorker(worldR, {adSpoofing: true, relay: false});
            await wR.__abTwitchTest.notifyAdComplete(stitched([{id: 'stitched-ad-retry', pod: 1, pos: 0, rad: 'tok-r'}]));
            check('11k first GQL failure is retried',
                  worldR.spoofBatches.length >= 6 &&
                  worldR.spoofBatches[0][0].variables.input.eventName === 'video_ad_impression');
        }

        // 11l player mute/volume/visibility is copied into the payload
        {
            const worldP = makeWorld();
            worldP.spoofBatches = [];
            const wP = makeWorker(worldP, {adSpoofing: true, relay: false});
            Object.assign(wP.__abTwitchTest.playerState, {mute: true, volume: 0.25, visible: false});
            await wP.__abTwitchTest.notifyAdComplete(stitched([{id: 'stitched-ad-state', pod: 1, pos: 0, rad: 'tok-s'}]));
            const payload = JSON.parse(worldP.spoofBatches[0][0].variables.input.eventPayload);
            check('11l payload mirrors mute, volume and visibility',
                  payload.player_mute === true && payload.player_volume === 0.25 && payload.visible === false);
        }

        // 11m Device-ID "oauth" / too short is not sent
        {
            const wD = makeWorker(makeWorld(), {adSpoofing: true, relay: false, deviceId: 'oauth'});
            const headers = wD.__abTwitchTest.gqlHeaders(true);
            check('11m invalid Device-ID is omitted (never "oauth")',
                  headers['X-Device-Id'] == null && headers['Device-ID'] == null &&
                  wD.__abTwitchTest.validDeviceId('oauth') === false &&
                  wD.__abTwitchTest.validDeviceId('dev12345') === true);
        }

        // 11n runtime toggle without reload
        {
            const worldT = makeWorld();
            worldT.spoofBatches = [];
            const wT = makeWorker(worldT, {adSpoofing: false, relay: false});
            const pl = stitched([{id: 'stitched-ad-toggle', pod: 1, pos: 0, rad: 'tok-t'}]);
            await wT.__abTwitchTest.notifyAdComplete(pl);
            check('11n off: runtime-disabled worker sends nothing', worldT.spoofBatches.length === 0);
            wT.pageSend({event: 'set-spoofing', enabled: true});
            await wT.__abTwitchTest.notifyAdComplete(pl);
            check('11n on: BroadcastChannel toggle enables spoofing without reload', worldT.spoofBatches.length >= 6);
        }

        // 11o quartile spread is capped, so a long ad does not delay pod_complete by its full length
        {
            const wO = makeWorker(makeWorld(), {adSpoofing: true, relay: false,
                timing: Object.assign({}, TIMING, {spoofRealtime: true, spoofSpan: 4000, spoofJitter: 0})});
            const d = wO.__abTwitchTest.spoofDelayMs;
            check('11o a 30 s ad finishes its beacons within the 4 s cap',
                  d(30, 0) === 0 && d(30, 4) === 4000 && d(2, 4) === 2000);
        }

        // 11p endAd while quartiles are still in flight must not drop pod_complete
        {
            const worldF = makeWorld();
            worldF.spoofBatches = [];
            const wF = makeWorker(worldF, {adSpoofing: true, relay: false,
                timing: Object.assign({}, TIMING, {spoofRealtime: true, spoofSpan: 60, spoofJitter: 0})});
            const pl = stitched([{id: 'stitched-ad-inflight', pod: 1, pos: 0, rad: 'tok-f', duration: 30}]);
            const pending = wF.__abTwitchTest.notifyAdComplete(pl);
            wF.__abTwitchTest.resetSpoofPod();
            await pending;
            await new Promise((r) => setTimeout(r, 250));
            const evs = worldF.spoofBatches.map((b) => b[0].variables.input.eventName);
            check('11p pod_complete still arrives after the break ends mid-spoof',
                  evs[0] === 'video_ad_impression' && evs[evs.length - 1] === 'video_ad_pod_complete' && evs.length === 6);
        }
    }

    console.log(`\n${passed} passed, ${failed} failed`);
    process.exit(failed ? 1 : 0);
})();
