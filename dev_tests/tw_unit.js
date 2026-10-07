// Offline tests for scripts/twitch_worker.js with real playlists captured from Twitch.
const fs = require('fs');
const path = require('path');
const APP = path.join(__dirname, '..');
const S = __dirname;
const workerSrc = fs.readFileSync(path.join(APP, 'scripts/twitch_worker.js'), 'utf8')
    .replace('__AB_WORKER_INIT__', JSON.stringify({clientId: 'test', deviceId: 'dev', backupTypes: ['popout', 'frontpage', 'autoplay'], channel: 't'}));

const adMaster = fs.readFileSync(path.join(S, 'tw_ad_master.m3u8'), 'utf8');
const adMedia = fs.readFileSync(path.join(S, 'tw_ad_media.m3u8'), 'utf8');
const live = (seq, tag) => ['#EXTM3U', '#EXT-X-VERSION:3', '#EXT-X-TARGETDURATION:6', '#EXT-X-MEDIA-SEQUENCE:' + seq,
    '#EXT-X-DATERANGE:ID="source-1",CLASS="twitch-stream-source",START-DATE="2026-10-04T16:00:00.000Z",END-ON-NEXT=YES,X-TV-TWITCH-STREAM-SOURCE="live"',
    '#EXTINF:2.000,live', `https://${tag}.example/seg${seq}.ts`, '#EXTINF:2.000,live', `https://${tag}.example/seg${seq + 1}.ts`].join('\n');

let passed = 0, failed = 0;
function check(name, ok, detail) {
    if (ok) passed++; else failed++;
    console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? '  [' + detail + ']' : ''));
}

function makeWorker(routes, log, events) {
    const self = {};
    class FakeChannel { postMessage(m) { if (events) events.push(m); } }
    self.fetch = async (url, init) => {
        url = typeof url === 'string' ? url : url.url;
        log.push((init && init.method || 'GET') + ' ' + url.slice(0, 200));
        for (const [pattern, handler] of routes) {
            if (url.includes(pattern)) {
                const body = typeof handler === 'function' ? handler(url, init) : handler;
                if (body === 404) return new Response('gone', {status: 404});
                return new Response(typeof body === 'string' ? body : JSON.stringify(body), {status: 200});
            }
        }
        return new Response('not found', {status: 404});
    };
    new Function('self', 'BroadcastChannel', workerSrc)(self, FakeChannel);
    return self;
}

const ORIG_720 = 'https://euc1.playlist.ttvnw.net/v1/playlist/ORIGINAL-720.m3u8';
const ORIG_1080 = 'https://euc1.playlist.ttvnw.net/v1/playlist/ORIGINAL-1080.m3u8';
const playerMaster = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=6000000,RESOLUTION=1920x1080,FRAME-RATE=60.000\n' + ORIG_1080 +
    '\n#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720,FRAME-RATE=60.000\n' + ORIG_720 + '\n';
const backupMaster = (type) => '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=6000000,RESOLUTION=1920x1080,FRAME-RATE=60.000\nhttps://x/' + type + '-1080.m3u8\n' +
    '#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720,FRAME-RATE=60.000\nhttps://x/' + type + '-720.m3u8\n';
const USHER = 'https://usher.ttvnw.net/api/v2/channel/hls/gotaga.m3u8?sig=player&token=x';
const AD_END = Date.parse('2026-10-04T16:03:57.709Z') + 15235;

function gql(seen, spoofBatches) {
    return (u, init) => {
        const body = JSON.parse(init.body);
        if (Array.isArray(body)) {
            if (spoofBatches) spoofBatches.push(body);
            return body.map(() => ({data: {recordAdEvent: true}}));
        }
        const t = body && body.variables && body.variables.playerType;
        if (t && seen) seen.push(t);
        return {data: {streamPlaybackAccessToken: {value: '{"player_type":"' + t + '"}', signature: 'sig-' + t}}};
    };
}
function usher(u) {
    const m = u.match(/sig=sig-([a-z-]+)/);
    return m ? backupMaster(m[1]) : playerMaster;
}
const count = (log, s) => log.filter(l => l.includes(s)).length;

(async () => {
    const t = makeWorker([], []).__abTwitchTest;
    check('ad playlist is detected', t.hasAds(adMedia));
    check('live playlist is not flagged', !t.hasAds(live(500, 'a')));
    const v = t.pickVariant(adMaster, '1280x720', 60);
    check('variant picking finds a 720p rendition', !!v && adMaster.includes(v));
    check('end of the ad pod is read from the playlist', t.adEndsAt(adMedia) === AD_END);

    // 1) ads in the player's session, popout is ad-free
    {
        const log = [], ev = [], types = [];
        let originalAds = true;
        const w = makeWorker([
            ['gql.twitch.tv', gql(types)],
            ['usher.ttvnw.net', usher],
            ['ORIGINAL-', () => originalAds ? adMedia : live(900, 'orig')],
            ['/popout-720', live(11000, 'pop720')],
            ['/popout-1080', live(11000, 'pop1080')],
        ], log, ev);
        await w.fetch(USHER);
        let r = await (await w.fetch(ORIG_720)).text();
        check('1a during ads the player gets the ad-free backup', r === live(11000, 'pop720'), 'tried: ' + types.join(','));
        r = await (await w.fetch(ORIG_720)).text();
        check('1b next refresh reuses the backup session (no new token/usher)', r === live(11000, 'pop720') && types.length === 1 && count(log, 'sig=sig-') === 1);
        originalAds = false;
        r = await (await w.fetch(ORIG_720)).text();
        check('1c after the ad the backup stays (no jump back to other segment numbers)', r === live(11000, 'pop720'));
        r = await (await w.fetch(ORIG_1080)).text();
        check('1d quality switch uses the same backup session', r === live(11000, 'pop1080') && count(log, 'sig=sig-') === 1);
        check('1e events: backup chosen, ad break closed, nothing masked', ev.some(e => e.event === 'backup' && e.type === 'popout') &&
              ev.filter(e => e.event === 'ad-start').length === 1 && ev.some(e => e.event === 'ad-end') && !ev.some(e => e.event === 'masked'));
    }

    // 2) streamer ad break: every backup has ads too -> masked, no session churn
    {
        const log = [], ev = [], types = [];
        const w = makeWorker([
            ['gql.twitch.tv', gql(types)],
            ['usher.ttvnw.net', usher],
            ['ORIGINAL-', adMedia],
            ['https://x/', adMedia],
        ], log, ev);
        await w.fetch(USHER);
        let r;
        for (let i = 0; i < 6; i++) r = await (await w.fetch(ORIG_720)).text();
        check('2a playlist is passed on unchanged (player keeps segments + numbering)', r === adMedia);
        check('2b no session churn: one backup session per type', count(log, 'sig=sig-') === 3, count(log, 'sig=sig-') + ' sessions');
        const masked = ev.filter(e => e.event === 'masked');
        check('2c page is told to cover/mute, with the end of the ad pod', masked.length === 6 && masked[0].endsAt === AD_END);
        const results = ev.filter(e => e.event === 'backup-result');
        check('2d each backup type reported once as "werbung"', results.length === 3 && results.every(e => e.result === 'werbung'));
    }

    // 3) the backup in use runs into a streamer ad break later
    {
        const log = [], ev = [], types = [];
        let backupAds = false;
        const w = makeWorker([
            ['gql.twitch.tv', gql(types)],
            ['usher.ttvnw.net', usher],
            ['ORIGINAL-', adMedia],
            ['/popout-720', () => backupAds ? adMedia : live(11000, 'pop720')],
        ], log, ev);
        await w.fetch(USHER);
        await w.fetch(ORIG_720);
        backupAds = true;
        let r = await (await w.fetch(ORIG_720)).text();
        check('3a backup with ads is masked (stays on the backup session)', r === adMedia && ev[ev.length - 1].event === 'masked');
        backupAds = false;
        r = await (await w.fetch(ORIG_720)).text();
        check('3b afterwards the backup plays again', r === live(11000, 'pop720') && ev.some(e => e.event === 'ad-end'));
    }

    // 4) backup session in use disappears -> reopened once; if still gone, the player's own session is used
    {
        const log = [], ev = [], types = [];
        let originalAds = true, popoutGone = false;
        const w = makeWorker([
            ['gql.twitch.tv', gql(types)],
            ['usher.ttvnw.net', usher],
            ['ORIGINAL-', () => originalAds ? adMedia : live(900, 'orig')],
            ['/popout-720', () => popoutGone ? 404 : live(11000, 'pop720')],
        ], log, ev);
        await w.fetch(USHER);
        await w.fetch(ORIG_720);
        popoutGone = true;
        originalAds = false;
        const r = await (await w.fetch(ORIG_720)).text();
        check('4 vanished backup: reopened once, then back to the player\'s own (ad-free) session',
              r === live(900, 'orig') && count(log, 'sig=sig-popout') === 2, count(log, 'sig=sig-popout') + ' popout sessions');
    }

    // 5) no ads at all: nothing extra is requested
    {
        const log = [], ev = [], types = [];
        const w = makeWorker([['gql.twitch.tv', gql(types)], ['usher.ttvnw.net', usher], ['ORIGINAL-', live(900, 'orig')]], log, ev);
        await w.fetch(USHER);
        const r = await (await w.fetch(ORIG_720)).text();
        check('5 ad-free stream: original is used, no backup sessions', r === live(900, 'orig') && count(log, 'sig=sig-') === 0 && types.length === 0);
    }

    // 6) unrelated requests pass through untouched
    const w6 = makeWorker([['example.com', 'hello']], []);
    check('6 other requests are not touched', await (await w6.fetch('https://example.com/a')).text() === 'hello');

    // 7) Ad Spoofing (TTV-AB technique): reports impressions, quartiles & pod complete to Twitch GQL
    {
        const log = [], ev = [], spoofBatches = [];
        const w7 = makeWorker([
            ['gql.twitch.tv', gql([], spoofBatches)],
            ['usher.ttvnw.net', usher],
            ['ORIGINAL-', adMedia],
            ['https://x/', adMedia],
        ], log, ev);
        const t7 = w7.__abTwitchTest;

        // 7a attribute parser
        const parsed = t7.parseAttrs('#EXT-X-DATERANGE:ID="stitched-ad-test",CLASS="twitch-stitched-ad",DURATION=15.235,X-TV-TWITCH-AD-ROLL-TYPE="PREROLL"');
        check('7a parseAttrs parses quoted and unquoted attributes',
              parsed.ID === 'stitched-ad-test' && parsed['X-TV-TWITCH-AD-ROLL-TYPE'] === 'PREROLL' && parsed.DURATION === '15.235');

        // 7b fetch ad playlist triggers notifyAdComplete
        await w7.fetch(USHER);
        await w7.fetch(ORIG_720);

        check('7b ad playlist triggers GQL ad spoofing batch', spoofBatches.length >= 1);
        const batch = spoofBatches[0];
        check('7c batch contains impression, 4 quartiles and pod complete',
              batch && batch.length === 6 &&
              batch[0].variables.input.eventName === 'video_ad_impression' &&
              batch[1].variables.input.eventName === 'video_ad_quartile_complete' &&
              batch[2].variables.input.eventName === 'video_ad_quartile_complete' &&
              batch[3].variables.input.eventName === 'video_ad_quartile_complete' &&
              batch[4].variables.input.eventName === 'video_ad_quartile_complete' &&
              batch[5].variables.input.eventName === 'video_ad_pod_complete');

        const firstPayload = batch ? JSON.parse(batch[0].variables.input.eventPayload) : {};
        check('7d packet payload contains stitched ad details and RADS token',
              firstPayload.stitched === true &&
              firstPayload.ad_id === 'stitched-ad-1791129837-15235000000' &&
              firstPayload.roll_type === 'preroll' &&
              firstPayload.creative_id === '2488883100494' &&
              firstPayload.duration === 15 &&
              batch[0].variables.input.radToken.startsWith('eyJhbGci') &&
              batch[0].extensions.persistedQuery.sha256Hash === '7e6c69e6eb59f8ccb97ab73686f3d8b7d85a72a0298745ccd8bfc68e4054ca5b');

        // 7e deduplication: second poll of the same playlist does not send another batch
        const countBefore = spoofBatches.length;
        await w7.fetch(ORIG_720);
        check('7e deduplication prevents re-spoofing the same ad ID', spoofBatches.length === countBefore);

        // 7f broadcast event sent
        check('7f ad-spoofed event reported on channel',
              ev.some(e => e.event === 'ad-spoofed' && e.id === 'stitched-ad-1791129837-15235000000'));
    }

    console.log(`\n${passed} passed, ${failed} failed`);
    process.exit(failed ? 1 : 0);
})();
