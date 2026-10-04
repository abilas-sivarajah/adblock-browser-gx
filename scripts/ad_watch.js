// Ad watch: notices when a video ad is actually running despite the blocker and reports it
// to the browser (ad_logger.py), together with the state of the site's blocker script.
// Also answers the browser's "collect" request when the user reports an ad by hand.
(function () {
    'use strict';
    const CFG = __AB_CONFIG__;
    if (window.top !== window) return;
    const wv = window.chrome && window.chrome.webview;
    if (!wv || window.__abAdWatch) return;
    window.__abAdWatch = true;
    const host = location.hostname;
    const on = function (d) { return host === d || host.endsWith('.' + d); };
    if (!CFG.enabled || CFG.whitelist.some(on)) return;

    function text(el, n) { return el ? (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, n || 200) : ''; }
    function videoState(v) {
        return v ? {t: Math.round(v.currentTime * 10) / 10, dauer: isFinite(v.duration) ? Math.round(v.duration) : null,
                    pausiert: v.paused, stumm: v.muted, tempo: v.playbackRate} : null;
    }

    // Each detector returns null (no ad) or details about the running ad.
    const DETECTORS = [
        {site: 'youtube', match: on('youtube.com'), detect: function () {
            const mp = document.getElementById('movie_player');
            if (!mp || !(mp.classList.contains('ad-showing') || mp.classList.contains('ad-interrupting'))) return null;
            const adElements = [...mp.querySelectorAll('[class*="ad-"], [class*="-ad"]')];
            const label = adElements.map(function (e) { return text(e, 80); }).find(function (t) { return t; }) || '';
            return {
                summary: 'YouTube-Werbung im Player (' + (label.slice(0, 60) || 'ohne Text') + ')',
                videoId: new URLSearchParams(location.search).get('v'),
                werbetext: label,
                adElemente: [...new Set(adElements.map(function (e) { return e.className.toString().slice(0, 80); }))].slice(0, 20),
                video: videoState(mp.querySelector('video'))
            };
        }},
        {site: 'twitch', match: on('twitch.tv'), detect: function () {
            // our own hint/cover is up: the ad is cut out or hidden on purpose
            if (window.__abTwitch && window.__abTwitch.overlayActive) return null;
            const player = document.querySelector('[data-a-target="video-player"]');
            const label = document.querySelector('[data-a-target="video-ad-label"], [data-a-target="video-ad-countdown"]');
            const t = text(player, 400);
            // texts of the ad overlay ("Enthält bezahlte Werbung" is only the sponsoring label)
            const adText = /nach dieser Werbung|Werbepause|commercial break|right after this ad/i.test(t);
            if (!label && !adText) return null;
            return {summary: 'Twitch-Werbung im Player', kanal: location.pathname.split('/')[1], playertext: t,
                    video: videoState(player && player.querySelector('video'))};
        }},
        {site: 'southpark', match: on('southpark.de'), detect: function () {
            const ui = [...document.querySelectorAll('.avia-ad-control-container, .avia-ad-prog-bar')].find(function (e) { return e.offsetParent; });
            const badge = /WERBUNG\s*\d+\s*\/\s*\d+/.test(text(document.body, 5000));
            if (!ui && !badge) return null;
            return {summary: 'South-Park-Werbung im Player', video: videoState(document.querySelector('video'))};
        }}
    ];

    function siteState() {
        return {twitch: window.__abTwitch || null, youtube: window.__abYouTube || null};
    }

    function send(site, kind, details) {
        try {
            wv.postMessage({type: 'adblock-ad-event', site: site, kind: kind, details: details || {}});
        } catch (e) {}
    }

    const detector = DETECTORS.find(function (d) { return d.match; });
    if (detector) {
        let since = 0;
        setInterval(function () {
            let found = null;
            try { found = detector.detect(); } catch (e) {}
            if (found && !since) {
                since = Date.now();
                found.blocker = siteState();
                send(detector.site, 'ad-visible', found);
            } else if (!found && since) {
                send(detector.site, 'ad-visible-end', {summary: 'nach ' + Math.round((Date.now() - since) / 1000) + ' s'});
                since = 0;
            }
        }, 1000);
    }

    // manual report: the browser asks for the page state
    wv.addEventListener('message', function (ev) {
        const d = ev.data;
        if (!d || d.type !== 'adblock-collect') return;
        const videos = [...document.querySelectorAll('video')].map(videoState);
        const frames = [...document.querySelectorAll('iframe')].map(function (f) { return f.src; }).filter(Boolean).slice(0, 30);
        send(detector ? detector.site : host, 'manual-details', {
            blocker: siteState(), videos: videos, iframes: frames,
            laufendeWerbung: detector ? (function () { try { return detector.detect(); } catch (e) { return null; } })() : null
        });
    });
})();
