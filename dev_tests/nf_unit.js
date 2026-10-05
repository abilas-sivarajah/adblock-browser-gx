// Offline tests for scripts/netflix.js (built with config) in a fake page context.
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync(require('path').join(__dirname, '..', 'scripts', 'netflix.js'), 'utf8')
    .replace('__AB_CONFIG__', JSON.stringify({enabled: true, whitelist: [], twitchBackupTypes: ['popout', 'frontpage', 'autoplay']}));

let passed = 0, failed = 0;
function check(name, ok, detail) {
    if (ok) passed++; else failed++;
    console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail ? '  [' + detail + ']' : ''));
}

const messages = [];
let playerText = '';
let fakeNow = 1000000;
let reloads = 0;
const store = {};
const video = {currentTime: 0, paused: false, readyState: 1, muted: false, buffered: {length: 0}};
let pauseAdEl = null;
function makeSandbox() {
    const sb = {
        CSSStyleSheet: class { replaceSync(t) { this.text = t; } },
        location: {hostname: 'www.netflix.com', pathname: '/browse', reload: () => { reloads++; }},
        sessionStorage: {getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; }},
        JSON: {parse: JSON.parse, stringify: JSON.stringify},
        Response: class { constructor(o) { this.o = o; } },
        Proxy, Reflect, Object, Array, String, Math, parseInt, Promise,
        Date: {now: () => fakeNow},
        setTimeout: (fn) => fn(),
        setInterval: (fn) => { sb.__tick = fn; return 1; },
        document: {
            adoptedStyleSheets: [],
            querySelector: (sel) => sel === '[data-uia="pause-ad"]' ? pauseAdEl : sel === 'video' || sel.startsWith('.watch-video video') ? video : sel.includes('watch-video') ? {
                get innerText() { return playerText; },
                querySelector: () => video,
                appendChild: () => {},
            } : null,
            createElement: () => ({setAttribute() {}, remove() {}, style: {}, parentNode: null}),
        },
    };
    sb.Response.prototype.json = function () { return Promise.resolve(this.o); };
    sb.window = sb;
    sb.chrome = {webview: {postMessage: (m) => messages.push(m)}};
    vm.createContext(sb);
    vm.runInContext(src, sb);
    return sb;
}
const sandbox = makeSandbox();

(async () => {
    check('script activates on netflix.com', !!sandbox.__abNetflix);
    const manifest = {
        version: 2, result: {
            movieId: 81000001, duration: 5400000,
            adverts: {
                hasAdverts: true,
                adBreaks: [{locationMs: 0, durationMs: 30000, ads: [{id: 'a1'}]}, {locationMs: 900000, durationMs: 60000, ads: []}],
                adBreakTokens: ['tok1', 'tok2'],
            },
            video_tracks: [{streams: [1, 2, 3]}],
        }
    };
    const parsed = sandbox.JSON.parse(JSON.stringify(manifest) + ' '.repeat(10));
    check('ad breaks emptied in JSON.parse result', Array.isArray(parsed.result.adverts.adBreaks) && parsed.result.adverts.adBreaks.length === 0);
    check('ad break tokens emptied', parsed.result.adverts.adBreakTokens.length === 0);
    check('rest of the playback data untouched', parsed.result.movieId === 81000001 && parsed.result.video_tracks[0].streams.length === 3 && parsed.result.adverts.hasAdverts === true);
    const st = sandbox.__abNetflix;
    check('statistics count 2 breaks', st.breaksRemoved === 2 && st.dataWithAds === 1, JSON.stringify({b: st.breaksRemoved, d: st.dataWithAds}));
    const ev = messages.find(m => m.kind === 'ads-removed');
    check('ad log gets field names only (no values)', ev && ev.details.felder.adBreaks === 'Liste(2)' && ev.details.ersteWerbepause.locationMs === 'number' && !JSON.stringify(ev).includes('tok1'),
          ev && JSON.stringify(ev.details).slice(0, 140));

    const other = sandbox.JSON.parse(JSON.stringify({result: {list: new Array(50).fill({title: 'x'})}}));
    check('unrelated data passes through', other.result.list.length === 50);

    const viaFetch = await new sandbox.Response({payload: {adverts: {adBreaks: [{locationMs: 5, durationMs: 1}]}}}).json();
    check('fetch().json() results are pruned too', viaFetch.payload.adverts.adBreaks.length === 0);

    // safety net: ad UI text as in the user's screenshot
    playerText = 'Werbung 1 von 2 • 33   War Machine beginnt nach der Werbung';
    sandbox.__tick();
    const masked = messages.find(m => m.kind === 'masked');
    check('running ad is detected and covered', st.overlayActive && masked && masked.details.anzeige.sekunden === 33 && masked.details.anzeige.von === '2',
          masked && JSON.stringify(masked.details.anzeige));
    playerText = 'War Machine  Folge 1';
    sandbox.__tick();
    check('cover removed after the ad', !st.overlayActive && messages.some(m => m.kind === 'ad-visible-end'));

    // watchdog: player stays at 0:00 after the breaks were removed
    playerText = '';
    sandbox.location.pathname = '/watch/123';
    video.currentTime = 0; video.paused = false; video.readyState = 1;
    sandbox.__tick();
    fakeNow += 8000; sandbox.__tick();
    check('no reload while the title is still starting (8 s)', reloads === 0);
    fakeNow += 8000; sandbox.__tick();
    check('stalled at 0:00 for 16 s -> reloaded once without removing', reloads === 1 && store.abNetflixNoPrune === '/watch/123' &&
          messages.some(m => m.kind === 'stalled'), 'reloads=' + reloads);
    fakeNow += 30000; sandbox.__tick();
    check('only one reload per title', reloads === 1);

    // normal playback never triggers it
    sandbox.location.pathname = '/watch/456';
    video.currentTime = 0; sandbox.__tick();
    video.currentTime = 4.2; fakeNow += 3000; sandbox.__tick();
    fakeNow += 60000; sandbox.__tick();
    check('playing title is never reloaded', reloads === 1);

    // the reloaded page keeps the ad data (the ad then plays covered + muted)
    delete store.abNetflixNoPrune;
    store.abNetflixNoPrune = '/watch/123';
    const sb3 = makeSandbox();  // fresh page load; its location.pathname is set below before checking
    check('after the reload the flag is only used for that title', sb3.__abNetflix.pruning === true, 'flag path differs from /browse');
    store.abNetflixNoPrune = '/browse';
    const sb4 = makeSandbox();
    check('reloaded title page skips the removal once (flag consumed)', sb4.__abNetflix.pruning === false && !('abNetflixNoPrune' in store));
    const kept = sb4.JSON.parse(JSON.stringify({result: {adverts: {adBreaks: [{locationMs: 0, durationMs: 1}]}}}) + ' '.repeat(200));
    check('...and leaves the ad breaks in the data', kept.result.adverts.adBreaks.length === 1);

    // pause ad (GraphQL "PauseAdsArtwork", shape as recorded live)
    const pauseResponse = () => ({data: {
        pinotPausedPlaybackPage: {__typename: 'PinotPausedPlaybackAdPage', adPageSections: {
            __typename: 'PinotSectionConnection', totalCount: 1, pageInfo: {endCursor: 'c'},
            edges: [{__typename: 'PinotSectionEdge', node: {entity: {displayAd: {content: {uri: 'https://occ.example/ad.jpg', adEvents: {start: {token: 'tokA'}}}}}}}]}},
        videos: [{__typename: 'Movie', videoId: 81916859, titleArt: {url: 'https://occ.example/title.jpg'}}]}});
    const sb5 = makeSandbox();
    const st5 = sb5.__abNetflix;
    check('pause ad stylesheet installed', sb5.document.adoptedStyleSheets.length === 1 &&
          /\[data-uia="pause-ad"\] \{ opacity: 0 !important/.test(sb5.document.adoptedStyleSheets[0].text) &&
          /pointer-events: none !important/.test(sb5.document.adoptedStyleSheets[0].text) && !/display/.test(sb5.document.adoptedStyleSheets[0].text));
    const pr = await new sb5.Response(pauseResponse()).json();
    const secs = pr.data.pinotPausedPlaybackPage.adPageSections;
    check('pause ad emptied in fetch().json() result', secs.edges.length === 0 && secs.totalCount === 0 && st5.pauseAdsRemoved === 1 && st5.pauseAdVia === 'Response.json');
    check('...title data of the pause screen untouched', pr.data.videos[0].videoId === 81916859 && secs.pageInfo.endCursor === 'c');
    const pm = messages.filter(m => m.kind === 'pause-ad-removed');
    check('pause ad removal is logged (no tokens)', pm.length === 1 && !JSON.stringify(pm).includes('tokA'));
    const pr2 = sb5.JSON.parse(JSON.stringify(pauseResponse()));
    check('pause ad emptied in JSON.parse result', pr2.data.pinotPausedPlaybackPage.adPageSections.edges.length === 0 && st5.pauseAdVia === 'JSON.parse');
    // pause ad dialog (empty when the data was removed, with "Zurück zum Pausenbildschirm" button)
    let backClicks = 0;
    const dialog = () => ({querySelector: (s) => s === '[data-uia="pause-ad-expand-button"]' ? {click: () => { backClicks++; }} : null});
    const pauseMasked = () => messages.filter(m => m.kind === 'masked' && m.details.pausenWerbung).length;
    pauseAdEl = dialog();
    sb5.__tick(); fakeNow += 1000; sb5.__tick(); fakeNow += 1000; sb5.__tick(); fakeNow += 5000; sb5.__tick();
    check('dialog after removed data: no incident', backClicks === 0 && pauseMasked() === 0);
    pauseAdEl = null; sb5.__tick();

    const sb6 = makeSandbox();
    pauseAdEl = dialog();
    sb6.__tick(); fakeNow += 1000; sb6.__tick();
    check('dialog without data: waits for the answer (1 s)', pauseMasked() === 0);
    fakeNow += 1000; sb6.__tick(); fakeNow += 1000; sb6.__tick(); fakeNow += 1000; sb6.__tick();
    check('...then one incident, no clicks into the page', backClicks === 0 && pauseMasked() === 1 && sb6.__abNetflix.pauseAdsHidden === 1);
    sb6.document.adoptedStyleSheets = [];
    sb6.__tick();
    check('stylesheet re-added if the page drops it', sb6.document.adoptedStyleSheets.length === 1);
    pauseAdEl = null; sb6.__tick();
    // next pause: answer with an ad that was not removed (data path known, removal switched off)
    sb6.__abNetflix.pausePrune = false;
    await new sb6.Response(pauseResponse()).json();
    pauseAdEl = dialog();
    sb6.__tick(); fakeNow += 2000; sb6.__tick();
    check('ad reached the dialog (removal off) -> incident again', backClicks === 0 && pauseMasked() === 2);
    pauseAdEl = null; sb6.__tick();

    store.abNetflixNoPrune = '/browse';
    const sb7 = makeSandbox();
    const pr3 = await new sb7.Response(pauseResponse()).json();
    check('pause ad is removed even on a watchdog reload (breaks kept)', sb7.__abNetflix.pruning === false &&
          pr3.data.pinotPausedPlaybackPage.adPageSections.edges.length === 0);
    const empty = await new sb7.Response({data: {pinotPausedPlaybackPage: {adPageSections: {edges: [], totalCount: 0}}}}).json();
    check('no-ad answer counted, nothing logged', sb7.__abNetflix.pauseAdData === 2 && sb7.__abNetflix.pauseAdsRemoved === 1 && empty.data.pinotPausedPlaybackPage.adPageSections.edges.length === 0);

    console.log(`\n${passed} passed, ${failed} failed`);
    process.exit(failed ? 1 : 0);
})();
