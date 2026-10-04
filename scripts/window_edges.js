// Window edges over web pages: the page is its own native window, so the browser window
// cannot see the mouse at its right/bottom border there. Invisible strips at those edges
// report a press to the browser, which then starts the native window resize.
// Shown only while the window can be resized (not maximised / fullscreen).
(function () {
    'use strict';
    if (window.top !== window) return;
    const wv = window.chrome && window.chrome.webview;
    if (!wv || window.__abEdges) return;
    window.__abEdges = true;

    const S = 5, C = 14;
    const EDGES = [
        ['right', 'top:0;right:0;width:' + S + 'px;height:calc(100% - ' + C + 'px);cursor:ew-resize'],
        ['bottom', 'left:0;bottom:0;height:' + S + 'px;width:calc(100% - ' + C + 'px);cursor:ns-resize'],
        ['corner', 'right:0;bottom:0;width:' + C + 'px;height:' + C + 'px;cursor:nwse-resize']
    ];
    let host = null;
    let enabled = false;

    function build() {
        host = document.createElement('div');
        const root = host.attachShadow({mode: 'closed'});  // page CSS/scripts cannot touch the strips
        EDGES.forEach(function (e) {
            const d = document.createElement('div');
            d.style.cssText = 'position:fixed;z-index:2147483647;background:transparent;' + e[1];
            d.addEventListener('mousedown', function (ev) {
                if (ev.button !== 0) return;
                ev.preventDefault();
                ev.stopPropagation();
                wv.postMessage({type: 'adblock-edge', edge: e[0]});
            }, true);
            root.appendChild(d);
        });
    }

    // re-attach if the page rebuilds <html> (only direct children are watched, not every DOM change)
    const watcher = new MutationObserver(function () { if (enabled && host && !host.isConnected) sync(); });
    watcher.observe(document, {childList: true});

    function sync() {
        if (!enabled) {
            if (host && host.isConnected) host.remove();
            return;
        }
        if (!host) build();
        if (!host.isConnected && document.documentElement) {
            document.documentElement.appendChild(host);
            watcher.observe(document.documentElement, {childList: true});
        }
    }

    wv.addEventListener('message', function (ev) {
        const d = ev.data;
        if (d && d.type === 'adblock-frame') {
            enabled = !!d.resizable;
            sync();
        }
    });
    wv.postMessage({type: 'adblock-edges-hello'});
})();
