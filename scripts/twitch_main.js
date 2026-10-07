// Twitch: runs at document start on twitch.tv pages.
// Twitch's player (Amazon IVS) fetches the HLS playlists inside a Web Worker, so page-level
// hooks cannot see them. We wrap that worker and prepend twitch_worker.js to its code.
// Statistics for the shield / tests: window.__abTwitch
(function () {
    'use strict';
    const CFG = __AB_CONFIG__;
    const host = location.hostname;
    if (host !== 'twitch.tv' && !host.endsWith('.twitch.tv')) return;
    if (!CFG.enabled || CFG.whitelist.some(function (d) { return host === d || host.endsWith('.' + d); })) return;
    if (window.__abTwitch) return;

    const WORKER_HOOK = __AB_WORKER_HOOK__;
    const CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko';  // Twitch's public web client id
    const CHANNEL = 'adblock-twitch-' + Math.random().toString(36).slice(2);  // per page, not per origin
    const stats = window.__abTwitch = {
        workers: 0, hookedWorkers: 0, masters: 0, playlists: 0, adBreaks: 0, replaced: 0, masked: 0,
        holds: 0, nativeReturns: 0, adSeconds: 0, vodAdsBlocked: 0, spoofedAds: 0,
        lastBackupType: null, backupTrail: [], errors: [], overlayActive: false, bridgeActive: false
    };
    const channelName = function () { return location.pathname.split('/')[1] || ''; };

    // ---- hint in the player while Twitch's ad break has to be waited out ----
    let overlay = null, overlayTimer = 0, overlayEndsAt = null, overlayStarted = 0, cover = false, muted = null;

    function renderOverlay() {
        const player = document.querySelector('[data-a-target="video-player"]') ||
                       document.querySelector('.video-player__container');
        if (!player) return;
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'adblock-twitch-overlay';
        }
        // cover mode: the ad itself is running underneath (see twitch_worker.js 'masked')
        overlay.setAttribute('style', cover
            ? 'position:absolute;inset:0;z-index:9999;pointer-events:none;background:#0f172a;color:#e2e8f0;display:flex;' +
              'align-items:center;justify-content:center;padding:20px;font:600 16px/1.5 system-ui,sans-serif;text-align:center'
            : 'position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:9999;pointer-events:none;' +
              'background:rgba(15,23,42,.85);color:#e2e8f0;border:1px solid #10b981;border-radius:12px;padding:14px 20px;' +
              'font:600 15px/1.4 system-ui,sans-serif;text-align:center;max-width:80%');
        const video = player.querySelector('video');
        if (cover && video) {
            if (muted === null) muted = video.muted;
            video.muted = true;
        }
        // remaining time only while Twitch's announced end is still ahead, otherwise how long it has been
        const left = overlayEndsAt ? Math.round((overlayEndsAt - Date.now()) / 1000) : 0;
        const since = Math.round((Date.now() - overlayStarted) / 1000);
        const clock = function (sec) { return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0'); };
        overlay.textContent = '\u{1F6E1}\uFE0F Twitch-Werbepause \u2013 die Werbung wird ausgeblendet' +
            (left > 0 ? ' (noch ca. ' + clock(left) + ')' : ' (seit ' + clock(since) + ')') +
            '. Der Stream geht danach automatisch weiter.';
        if (overlay.parentNode !== player) player.appendChild(overlay);
    }

    function showOverlay(endsAt, coverPlayer) {
        if (endsAt) overlayEndsAt = endsAt;
        cover = cover || !!coverPlayer;
        if (!stats.overlayActive) overlayStarted = Date.now();
        stats.overlayActive = true;
        renderOverlay();
        if (!overlayTimer) overlayTimer = setInterval(renderOverlay, 1000);
    }

    function hideOverlay() {
        if (overlayTimer) clearInterval(overlayTimer);
        overlayTimer = 0;
        overlayEndsAt = null;
        if (overlay) overlay.remove();
        if (muted !== null) {
            const video = document.querySelector('[data-a-target="video-player"] video, .video-player__container video');
            if (video) video.muted = muted;
            muted = null;
        }
        cover = false;
        stats.overlayActive = false;
    }

    // ---- messages from the hooked player worker ----
    const lastLogged = {};  // event kind -> time, so the ad log gets one line per ad break, not one per playlist refresh

    function logOnce(kind, details) {
        const key = kind + '|' + channelName();
        if (Date.now() - (lastLogged[key] || 0) < 90 * 1000) return;
        lastLogged[key] = Date.now();
        toHost(kind, details);
    }

    let channel = null;
    try {
        channel = new BroadcastChannel(CHANNEL);
        let adPlaylist = null;
        channel.onmessage = function (e) {
            const d = e.data || {};
            if (d.event === 'worker-hooked') stats.hookedWorkers++;
            else if (d.event === 'seen-master') stats.masters++;
            else if (d.event === 'seen-playlist') stats.playlists++;
            else if (d.event === 'ad-start') {
                stats.adBreaks++;
                adPlaylist = d.playlist;
            } else if (d.event === 'ad-end') {
                hideOverlay();
            } else if (d.event === 'replaced') {
                stats.replaced++;
                hideOverlay();
                logOnce('ad-blocked', {summary: 'Twitch-Werbepause ersetzt durch Player-Typ "' + stats.lastBackupType + '"', kanal: channelName()});
            } else if (d.event === 'masked') {
                stats.masked++;
                showOverlay(d.endsAt, true);
                logOnce('masked', {summary: 'Twitch, Kanal ' + channelName() + ' – kein werbefreier Ersatz-Stream', playlist: adPlaylist,
                                   ersatzVersuche: stats.backupTrail.slice(-12), fehler: stats.errors.slice(-10), blocker: stats});
            } else if (d.event === 'ad-spoofed') {
                stats.spoofedAds += (d.count || 1);
                logOnce('ad-spoofed', {summary: 'Twitch-Werbung als gesehen gemeldet (Spoofing, ' + (d.roll || 'Spot') + ')', kanal: channelName(), adId: d.id});
            } else if (d.event === 'backup') {
                stats.lastBackupType = d.type;
            } else if (d.event === 'backup-result') {
                stats.backupTrail.push({zeit: new Date().toLocaleTimeString(), typ: d.type, ergebnis: d.result,
                                        neu: d.neu, fehler: d.error, werbungBis: d.endsAt ? new Date(d.endsAt).toLocaleTimeString() : undefined});
                if (stats.backupTrail.length > 30) stats.backupTrail.shift();
                if (d.result === 'fehler') {
                    stats.errors.push(d.type + ': ' + d.error);
                    if (stats.errors.length > 20) stats.errors.shift();
                }
            } else if (d.event === 'error') {
                stats.errors.push(d.error);
                if (stats.errors.length > 20) stats.errors.shift();
            }
        };
    } catch (e) {}

    // Sniff Twitch page's GQL fetch headers (Client-Integrity, Authorization, etc.)
    // and broadcast them to the player worker for authenticated requests and ad spoofing.
    try {
        const origFetch = window.fetch;
        let lastHeaders = {};
        window.fetch = function (input, init) {
            try {
                const url = typeof input === 'string' ? input : (input && input.url) || '';
                if (url.indexOf('gql.twitch.tv') !== -1 && init && init.headers) {
                    const h = init.headers;
                    const getHeader = function (name) {
                        if (!h) return null;
                        if (typeof h.get === 'function') return h.get(name);
                        if (Array.isArray(h)) {
                            const entry = h.find(function (r) { return r && String(r[0] || '').toLowerCase() === name.toLowerCase(); });
                            return entry ? entry[1] : null;
                        }
                        if (typeof h === 'object') {
                            return h[name] || h[name.toLowerCase()] || null;
                        }
                        return null;
                    };
                    const integrity = getHeader('Client-Integrity');
                    const auth = getHeader('Authorization');
                    const version = getHeader('Client-Version');
                    const session = getHeader('Client-Session-Id');
                    const dev = getHeader('X-Device-Id');
                    let changed = false;
                    const updates = {};
                    if (integrity && integrity !== lastHeaders.integrity) { updates.integrity = integrity; changed = true; }
                    if (auth && auth !== lastHeaders.auth) { updates.auth = auth; changed = true; }
                    if (version && version !== lastHeaders.version) { updates.version = version; changed = true; }
                    if (session && session !== lastHeaders.session) { updates.session = session; changed = true; }
                    if (dev && dev !== lastHeaders.device) { updates.device = dev; changed = true; }
                    if (changed && channel) {
                        Object.assign(lastHeaders, updates);
                        try { channel.postMessage({event: 'update-headers', headers: updates}); } catch (e) {}
                    }
                }
            } catch (e) {}
            return origFetch.apply(this, arguments);
        };
    } catch (e) {}

    function toHost(kind, details) {
        try {
            window.chrome.webview.postMessage({type: 'adblock-ad-event', site: 'twitch', kind: kind, details: details});
        } catch (e) {}
    }

    function deviceId() {
        const m = document.cookie.match(/(?:^|;\s*)unique_id=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }

    function authHeader() {
        const m = document.cookie.match(/(?:^|;\s*)auth-token=([^;]+)/);
        return m ? 'OAuth ' + decodeURIComponent(m[1]) : '';
    }

    function hookCode() {
        const init = JSON.stringify({
            clientId: CLIENT_ID,
            deviceId: deviceId(),
            authHeader: authHeader(),
            backupTypes: CFG.twitchBackupTypes,
            channel: CHANNEL,
            adSpoofing: CFG.adSpoofing !== false
        });
        return WORKER_HOOK.replace('__AB_WORKER_INIT__', function () { return init; });
    }

    function readBlob(url) {
        try {
            const xhr = new XMLHttpRequest();
            xhr.open('GET', url, false);  // blob: URLs are local, a sync read is instant
            xhr.send();
            return xhr.status === 200 || xhr.status === 0 ? xhr.responseText : null;
        } catch (e) {
            return null;
        }
    }

    function wrapWorkerUrl(url, options) {
        if (options && options.type === 'module') return url;
        const abs = new URL(String(url), location.href).href;
        let code = null;
        if (abs.startsWith('blob:')) {
            const original = readBlob(abs);
            if (original && /amazon-ivs|wasmworker/i.test(original)) code = hookCode() + '\n' + original;
        } else if (/amazon-ivs.*worker/i.test(abs)) {
            code = hookCode() + '\nimportScripts(' + JSON.stringify(abs) + ');';
        }
        if (!code) return url;
        return URL.createObjectURL(new Blob([code], {type: 'text/javascript'}));
    }

    const NativeWorker = window.Worker;
    class Worker extends NativeWorker {
        constructor(url, options) {
            let wrapped = url;
            try {
                wrapped = wrapWorkerUrl(url, options);
            } catch (e) {
                stats.errors.push('wrap: ' + e);
            }
            super(wrapped, options);
            stats.workers++;
        }
    }
    window.Worker = Worker;
})();
