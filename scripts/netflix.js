// Netflix (plan with ads): runs at document start on netflix.com pages.
//
// 1. The player learns its ad breaks from the playback data (".adverts.adBreaks": position and
//    length of every break). The list is emptied before the player sees it - in JSON.parse results
//    and fetch().json() results. Without breaks the player has nothing to play.
// 2. Safety net: if an ad still runs, the player is covered and muted until it is over.
// 3. Watchdog: if a title stays at 0:00 after the removal, it is reloaded once without removing.
// For the ad log: which ad fields the data contained (names and counts only), stalls.
// Statistics: window.__abNetflix
(function () {
    'use strict';
    const CFG = __AB_CONFIG__;
    const host = location.hostname;
    if (host !== 'netflix.com' && !host.endsWith('.netflix.com')) return;
    if (!CFG.enabled || CFG.whitelist.some(function (d) { return host === d || host.endsWith('.' + d); })) return;
    if (window.__abNetflix) return;

    const stats = window.__abNetflix = {
        dataWithAds: 0, breaksRemoved: 0, adsShown: 0, overlayActive: false, seen: [], pruning: true
    };
    // after a stall (see watchdog below) this page load runs without removing the breaks
    const NO_PRUNE_KEY = 'abNetflixNoPrune';
    try {
        if (sessionStorage.getItem(NO_PRUNE_KEY) === location.pathname) {
            sessionStorage.removeItem(NO_PRUNE_KEY);
            stats.pruning = false;
        }
    } catch (e) {}

    function toHost(kind, details) {
        try {
            window.chrome.webview.postMessage({type: 'adblock-ad-event', site: 'netflix', kind: kind, details: details});
        } catch (e) {}
    }

    // ---- 1. remove ad breaks from the playback data ----
    const AD_LIST_KEYS = ['adBreaks', 'adBreakTokens', 'adPods'];

    function describe(obj) {
        // field names and sizes only - never values (they may contain ids/tokens)
        const out = {};
        Object.keys(obj).slice(0, 25).forEach(function (k) {
            const v = obj[k];
            out[k] = Array.isArray(v) ? 'Liste(' + v.length + ')' : v === null ? 'null' : typeof v;
        });
        return out;
    }

    function pruneAdverts(adverts, path) {
        let removed = 0;
        const before = describe(adverts);
        let firstBreak = null;
        // where the breaks were (seconds into the title) - positions only, for the ad log
        const positions = Array.isArray(adverts.adBreaks) ? adverts.adBreaks.slice(0, 20).map(function (b) {
            return b && typeof b === 'object' ? {beiSek: Math.round((b.locationMs || 0) / 1000),
                                                 dauerSek: b.durationMs != null ? Math.round(b.durationMs / 1000) : null} : null;
        }) : [];
        AD_LIST_KEYS.forEach(function (k) {
            if (Array.isArray(adverts[k]) && adverts[k].length) {
                if (k === 'adBreaks') {
                    if (adverts[k][0] && typeof adverts[k][0] === 'object') firstBreak = describe(adverts[k][0]);
                    removed += adverts[k].length;  // counted: breaks only (tokens/pods belong to them)
                }
                adverts[k] = [];
            }
        });
        if (removed) {
            stats.dataWithAds++;
            stats.breaksRemoved += removed;
            stats.seen.push({pfad: path, felder: before, ersteWerbepause: firstBreak, positionen: positions, entfernt: removed});
            if (stats.seen.length > 5) stats.seen.shift();
            toHost('ads-removed', {summary: removed + ' Werbepause(n) aus den Abspieldaten entfernt', pfad: path,
                                   felder: before, ersteWerbepause: firstBreak, positionen: positions});
        }
        return removed;
    }

    // walks a parsed object (shallow: playback data keeps "adverts" near the top) for ad lists
    function prune(obj, path, depth) {
        if (!obj || typeof obj !== 'object' || depth > 4) return;
        if (Array.isArray(obj)) {
            for (let i = 0; i < obj.length && i < 20; i++) prune(obj[i], path + '[' + i + ']', depth + 1);
            return;
        }
        if (obj.adverts && typeof obj.adverts === 'object' && !Array.isArray(obj.adverts)) {
            pruneAdverts(obj.adverts, path + '.adverts');
        }
        if (Array.isArray(obj.adBreaks) && obj.adBreaks.length && obj.adBreaks[0] &&
            typeof obj.adBreaks[0] === 'object' && ('locationMs' in obj.adBreaks[0] || 'durationMs' in obj.adBreaks[0])) {
            pruneAdverts(obj, path);
        }
        const keys = Object.keys(obj);
        for (let i = 0; i < keys.length && i < 60; i++) {
            const v = obj[keys[i]];
            if (v && typeof v === 'object' && keys[i] !== 'adverts') prune(v, path + '.' + keys[i], depth + 1);
        }
    }

    function safePrune(obj) {
        if (!stats.pruning) return;
        try { prune(obj, 'daten', 0); } catch (e) {}
    }

    JSON.parse = new Proxy(JSON.parse, {
        apply: function (target, thisArg, args) {
            const result = Reflect.apply(target, thisArg, args);
            if (typeof args[0] === 'string' && args[0].length > 200 &&
                (args[0].indexOf('adBreak') !== -1 || args[0].indexOf('adverts') !== -1)) safePrune(result);
            return result;
        }
    });

    Response.prototype.json = new Proxy(Response.prototype.json, {
        apply: function (target, thisArg, args) {
            return Reflect.apply(target, thisArg, args).then(function (result) {
                safePrune(result);
                return result;
            });
        }
    });

    // ---- 2. safety net: cover and mute a running ad ----
    let overlay = null, restoreMuted = null, adSince = 0;

    function playerRoot() {
        return document.querySelector('.watch-video--player-view') || document.querySelector('.watch-video') ||
               document.querySelector('[data-uia="watch-video"]');
    }

    function adInfo(root) {
        const text = (root.innerText || '').replace(/\s+/g, ' ');
        const m = text.match(/(Werbung|Anzeige|Ad)\s+(\d+)\s+(von|of)\s+(\d+)\s*[•·]?\s*(\d+)?/i);
        if (m) return {nr: m[2], von: m[4], sekunden: m[5] ? parseInt(m[5], 10) : null};
        if (/beginnt nach der Werbung|will (begin|start) after the ad/i.test(text)) return {nr: null, von: null, sekunden: null};
        return null;
    }

    function cover(root, info) {
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.setAttribute('style', 'position:absolute;inset:0;z-index:2147483646;background:#0b0910;color:#e2e8f0;' +
                'display:flex;align-items:center;justify-content:center;text-align:center;padding:24px;pointer-events:none;' +
                'font:600 18px/1.5 Bahnschrift, "Segoe UI", sans-serif');
        }
        const left = info.sekunden != null ? ' (noch ca. ' + Math.floor(info.sekunden / 60) + ':' +
            String(info.sekunden % 60).padStart(2, '0') + ')' : '';
        const which = info.nr ? ' – Spot ' + info.nr + ' von ' + info.von : '';
        overlay.textContent = '\u{1F6E1}️ Netflix-Werbung wird ausgeblendet' + which + left +
            '. Die Sendung geht danach automatisch weiter.';
        if (overlay.parentNode !== root) root.appendChild(overlay);
        const video = root.querySelector('video');
        if (video) {
            if (restoreMuted === null) restoreMuted = video.muted;
            video.muted = true;
        }
    }

    function uncover() {
        if (overlay) overlay.remove();
        const video = document.querySelector('.watch-video video, video');
        if (video && restoreMuted !== null) video.muted = restoreMuted;
        restoreMuted = null;
    }

    // ---- 3. watchdog: rarely the player waits at 0:00 for the removed ad break ----
    // Then the title is loaded once more without removing it: the ad plays covered + muted,
    // and the title starts for sure.
    let watchStart = 0, watchPath = '';

    function watchdog() {
        const path = location.pathname;
        if (!stats.pruning || !stats.breaksRemoved || path.indexOf('/watch/') !== 0) {
            watchStart = 0;
            return;
        }
        if (path !== watchPath) {
            watchPath = path;
            watchStart = Date.now();
        }
        const video = document.querySelector('video');
        if (video && (video.currentTime >= 1 || (video.paused && video.readyState >= 2))) {
            watchStart = 0;  // playing (or paused by the user): fine for this title
            watchPath = path;
            stats.watchdogDone = path;
            return;
        }
        if (stats.watchdogDone === path || !watchStart || Date.now() - watchStart < 15000) return;
        stats.watchdogDone = path;
        toHost('stalled', {summary: 'Netflix-Player hing bei 0:00 – ohne Entfernen neu geladen',
                           video: video ? {t: video.currentTime, pausiert: video.paused, rs: video.readyState,
                                           gepuffert: video.buffered.length ? video.buffered.end(video.buffered.length - 1) : 0} : null,
                           blocker: {breaksRemoved: stats.breaksRemoved, seen: stats.seen}});
        try { sessionStorage.setItem(NO_PRUNE_KEY, path); } catch (e) { return; }
        setTimeout(function () { location.reload(); }, 300);
    }

    setInterval(function () {
        try { watchdog(); } catch (e) {}
        const root = playerRoot();
        const info = root ? adInfo(root) : null;
        if (info) {
            if (!adSince) {
                adSince = Date.now();
                stats.adsShown++;
                toHost('masked', {summary: 'Netflix-Werbung trotz entfernter Daten – abgedeckt und stumm',
                                  anzeige: info, blocker: {dataWithAds: stats.dataWithAds, breaksRemoved: stats.breaksRemoved, seen: stats.seen}});
            }
            stats.overlayActive = true;
            cover(root, info);
        } else if (adSince) {
            toHost('ad-visible-end', {summary: 'nach ' + Math.round((Date.now() - adSince) / 1000) + ' s'});
            adSince = 0;
            stats.overlayActive = false;
            uncover();
        }
    }, 500);
})();
