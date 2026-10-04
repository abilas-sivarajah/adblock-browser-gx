// YouTube: runs at document start on youtube.com pages.
//
// 1. The player schedules its ads from the player response (adPlacements, playerAds, adSlots).
//    Those keys are removed before the player sees them: in ytInitialPlayerResponse (first page
//    load), in JSON.parse results and in fetch().json() results (navigation inside YouTube).
// 2. Fallback for ads that still get through: mute, fast-forward, click "skip".
// 3. Ad blocks in the page (feed, sidebar, banners) are hidden, the adblock warning dialog is removed.
// Statistics for tests: window.__abYouTube
(function () {
    'use strict';
    const CFG = __AB_CONFIG__;
    const host = location.hostname;
    if (host !== 'youtube.com' && !host.endsWith('.youtube.com')) return;
    if (!CFG.enabled || CFG.whitelist.some(function (d) { return host === d || host.endsWith('.' + d); })) return;
    if (window.__abYouTube) return;
    const stats = window.__abYouTube = {pruned: 0, skipped: 0, dialogs: 0};

    function toHost(kind, details) {
        try {
            window.chrome.webview.postMessage({type: 'adblock-ad-event', site: 'youtube', kind: kind, details: details});
        } catch (e) {}
    }

    // ---- 1. remove ad data from player responses ----
    const AD_KEYS = ['adPlacements', 'playerAds', 'adSlots'];
    const reportedVideos = new Set();

    function noteRemoved(obj) {
        const details = obj.videoDetails || (obj.playerResponse && obj.playerResponse.videoDetails);
        const id = details && details.videoId;
        if (id && !reportedVideos.has(id)) {
            reportedVideos.add(id);
            toHost('ads-removed', {summary: 'Video ' + id + (details.title ? ' – ' + String(details.title).slice(0, 60) : '')});
        }
    }

    function prune(obj) {
        if (!obj || typeof obj !== 'object') return false;
        let changed = false;
        for (let i = 0; i < AD_KEYS.length; i++) {
            if (Object.prototype.hasOwnProperty.call(obj, AD_KEYS[i])) {
                delete obj[AD_KEYS[i]];
                changed = true;
            }
        }
        if (obj.playerResponse && typeof obj.playerResponse === 'object') changed = prune(obj.playerResponse) || changed;
        if (Array.isArray(obj)) {
            for (let i = 0; i < obj.length; i++) changed = prune(obj[i]) || changed;
        }
        if (changed) {
            stats.pruned++;
            try { noteRemoved(obj); } catch (e) {}
        }
        return changed;
    }

    let initialPlayerResponse;
    try {
        Object.defineProperty(window, 'ytInitialPlayerResponse', {
            configurable: true,
            get: function () { return initialPlayerResponse; },
            set: function (v) { prune(v); initialPlayerResponse = v; }
        });
    } catch (e) {}

    // Proxies keep Function.prototype.toString() returning "[native code]".
    JSON.parse = new Proxy(JSON.parse, {
        apply: function (target, thisArg, args) {
            const result = Reflect.apply(target, thisArg, args);
            try { prune(result); } catch (e) {}
            return result;
        }
    });

    Response.prototype.json = new Proxy(Response.prototype.json, {
        apply: function (target, thisArg, args) {
            return Reflect.apply(target, thisArg, args).then(function (result) {
                try { prune(result); } catch (e) {}
                return result;
            });
        }
    });

    // ---- 2. fallback: ads that are already playing ----
    // (YouTube's server only sends the video after the ad's run time anyway, so this mainly
    //  keeps the ad invisible and silent; mute/speed are restored afterwards.)
    let restore = null;  // {video, muted} while an ad is being fast-forwarded

    function handleRunningAd() {
        const player = document.getElementById('movie_player') || document.querySelector('.html5-video-player');
        if (!player) return;
        const skip = player.querySelector('.ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-skip-ad-button, .ytp-ad-skip-button-slot button');
        if (skip) skip.click();
        const video = player.querySelector('video');
        const adRunning = player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting');
        if (!adRunning) {
            if (restore) {
                restore.video.muted = restore.muted;
                if (restore.video.playbackRate > 2) restore.video.playbackRate = 1;
                restore = null;
            }
            return;
        }
        if (!video) return;
        if (!restore) restore = {video: video, muted: video.muted};
        video.muted = true;
        if (video.playbackRate !== 16) video.playbackRate = 16;
        if (isFinite(video.duration) && video.duration > 0 && video.currentTime < video.duration - 0.5) {
            video.currentTime = video.duration - 0.1;
            stats.skipped++;
        }
    }

    // ---- 3. page ad blocks and the adblock warning ----
    const CSS = [
        '#masthead-ad', '#player-ads', 'ytd-ad-slot-renderer', 'ytd-in-feed-ad-layout-renderer',
        'ytd-banner-promo-renderer', 'ytd-statement-banner-renderer', 'ytd-promoted-sparkles-web-renderer',
        'ytd-promoted-video-renderer', 'ytd-display-ad-renderer', 'ytd-companion-slot-renderer',
        'ytd-action-companion-ad-renderer', 'ytd-player-legacy-desktop-watch-ads-renderer',
        'ytd-rich-item-renderer:has(ytd-ad-slot-renderer)', 'ytd-rich-section-renderer:has(ytd-statement-banner-renderer)',
        '.ytp-ad-overlay-container', '.ytp-ad-message-container', '.ytd-mealbar-promo-renderer',
        'tp-yt-paper-dialog:has(ytd-enforcement-message-view-model)'
    ].map(function (s) { return s + ' { display: none !important; }'; }).join('\n') +
        '\n#movie_player.ad-showing video { opacity: 0 !important; }';

    function addCss() {
        try {
            const sheet = new CSSStyleSheet();
            sheet.replaceSync(CSS);
            document.adoptedStyleSheets = document.adoptedStyleSheets.concat([sheet]);
        } catch (e) {
            const style = document.createElement('style');
            style.textContent = CSS;
            (document.head || document.documentElement).appendChild(style);
        }
    }
    addCss();

    function removeAdblockWarning() {
        const msg = document.querySelector('ytd-enforcement-message-view-model');
        if (!msg) return;
        toHost('adblock-warning', {summary: (msg.innerText || '').replace(/\s+/g, ' ').slice(0, 200)});
        const dialog = msg.closest('tp-yt-paper-dialog, ytd-popup-container');
        if (dialog && dialog.tagName === 'TP-YT-PAPER-DIALOG') dialog.remove(); else msg.remove();
        document.querySelectorAll('tp-yt-iron-overlay-backdrop').forEach(function (b) { b.remove(); });
        const video = document.querySelector('#movie_player video');
        if (video && video.paused) video.play().catch(function () {});
        stats.dialogs++;
    }

    setInterval(function () {
        try { handleRunningAd(); } catch (e) {}
        try { removeAdblockWarning(); } catch (e) {}
    }, 300);
})();
