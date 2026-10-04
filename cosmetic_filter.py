"""
Cosmetic Filter and Scriptlet Injector for AdBlock Browser.
Injects CSS rules to collapse blocked ad spaces and runs ad-cleaner scriptlets (e.g. for YouTube video ads).
"""

# Runs at document start in the top frame. Reports the page's CSS classes and ids to the
# host (BrowserTab.on_web_message), which answers with the matching hide rules - both the
# site-specific ones and the generic '##.class' / '###id' rules of the filter lists.
COSMETIC_BRIDGE_SCRIPT = """
(function() {
    if (window.top !== window) return;
    const wv = window.chrome && window.chrome.webview;
    if (!wv || window.__adblockCosmetic) return;
    window.__adblockCosmetic = true;

    const seenClasses = new Set();
    const seenIds = new Set();
    let pendingClasses = [];
    let pendingIds = [];
    let flushTimer = 0;
    let cssText = '';
    let sheet = null;
    let styleEl = null;

    function applyCss(css) {
        cssText += css + '\\n';
        // Constructed stylesheets are not subject to the page's CSP (unlike <style>).
        try {
            if (!sheet) sheet = new CSSStyleSheet();
            sheet.replaceSync(cssText);
            if (!document.adoptedStyleSheets.includes(sheet)) {
                document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
            }
            return;
        } catch (e) {}
        if (!styleEl) {
            styleEl = document.createElement('style');
            styleEl.id = 'adblock-cosmetic-shield';
        }
        styleEl.textContent = cssText;
        if (!styleEl.isConnected) (document.head || document.documentElement).appendChild(styleEl);
    }

    wv.addEventListener('message', function(ev) {
        const d = ev.data;
        if (d && d.type === 'adblock-css' && d.css) applyCss(d.css);
    });

    function flush() {
        flushTimer = 0;
        if (!pendingClasses.length && !pendingIds.length) return;
        wv.postMessage({type: 'adblock-classes', classes: pendingClasses, ids: pendingIds});
        pendingClasses = [];
        pendingIds = [];
    }

    function schedule() {
        if (!flushTimer && (pendingClasses.length || pendingIds.length)) flushTimer = setTimeout(flush, 50);
    }

    function note(el) {
        const id = el.id;
        if (id && typeof id === 'string' && !seenIds.has(id)) {
            seenIds.add(id);
            pendingIds.push(id);
        }
        const cl = el.classList;
        if (!cl) return;
        for (let i = 0; i < cl.length; i++) {
            const c = cl[i];
            if (!seenClasses.has(c)) {
                seenClasses.add(c);
                pendingClasses.push(c);
            }
        }
    }

    function scan(root) {
        note(root);
        const els = root.querySelectorAll('[id],[class]');
        for (let i = 0; i < els.length; i++) note(els[i]);
    }

    new MutationObserver(function(mutations) {
        for (const m of mutations) {
            if (m.type === 'attributes') {
                note(m.target);
            } else {
                for (const n of m.addedNodes) if (n.nodeType === 1) scan(n);
            }
        }
        schedule();
    }).observe(document, {childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'id']});

    wv.postMessage({type: 'adblock-init'});
})();
"""


def build_cosmetic_css(hide_selectors, style_selectors=None) -> str:
    """One rule per selector, so a selector the browser does not understand only drops itself."""
    rules = [f"{sel} {{ display: none !important; }}"
             for sel in hide_selectors if "{" not in sel and "}" not in sel]
    for sel, styles in (style_selectors or {}).items():
        body = "; ".join(s for s in styles if "{" not in s and "}" not in s)
        if body and "{" not in sel and "}" not in sel:
            rules.append(f"{sel} {{ {body} }}")
    return "\n".join(rules)

