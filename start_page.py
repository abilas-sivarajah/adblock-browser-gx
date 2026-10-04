"""
Start page ("new tab") in the GX look: animated neon background in the accent colour,
clock, search, speed dial (stored in localStorage) and the blocker statistics.
"""

import json
import os

START_PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Neuer Tab - AdBlock Browser GX</title>
<style>
:root {
    --accent: __ACCENT__;
    --accent-rgb: __ACCENT_RGB__;
    --bg: #0b0910;
    --card: rgba(23, 20, 33, 0.72);
    --card-hover: rgba(33, 29, 46, 0.9);
    --line: rgba(255, 255, 255, 0.08);
    --text: #f2eff8;
    --muted: #a7a0b8;
    --dim: #6e6782;
    --ok: #2ee88a;
    --cut: 14px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
html { scrollbar-width: thin; scrollbar-color: rgba(var(--accent-rgb), .45) transparent; }
.cut {
    position: relative; background: var(--edge, var(--line));
    clip-path: polygon(0 0, calc(100% - var(--cut)) 0, 100% var(--cut), 100% 100%, var(--cut) 100%, 0 calc(100% - var(--cut)));
}
.cut::after {
    content: ""; position: absolute; inset: 1px; z-index: 0; background: var(--fill, var(--card));
    clip-path: polygon(0 0, calc(100% - var(--cut) + .6px) 0, 100% calc(var(--cut) - .6px), 100% 100%,
                       calc(var(--cut) - .6px) 100%, 0 calc(100% - var(--cut) + .6px));
}
.cut.one, .cut.one::after { clip-path: polygon(0 0, calc(100% - var(--cut)) 0, 100% var(--cut), 100% 100%, 0 100%); }
.cut.one::after { clip-path: polygon(0 0, calc(100% - var(--cut) + .6px) 0, 100% calc(var(--cut) - .6px), 100% 100%, 0 100%); }
.glow { transition: filter .2s ease; }
body {
    background: var(--bg);
    color: var(--text);
    font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
    overflow-x: hidden;
    min-height: 100vh;
}
.gx { font-family: "Bahnschrift", "Segoe UI", sans-serif; }

/* ---------- background ---------- */
.bg { position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none; }
.blob {
    position: absolute; border-radius: 50%; filter: blur(80px); opacity: .55;
    background: radial-gradient(circle, rgba(var(--accent-rgb), .9) 0%, rgba(var(--accent-rgb), 0) 70%);
}
.blob.b1 { width: 620px; height: 620px; left: -160px; top: -200px; }
.blob.b2 { width: 520px; height: 520px; right: -140px; top: 18%; opacity: .35;
           background: radial-gradient(circle, rgba(140, 80, 255, .8) 0%, rgba(140, 80, 255, 0) 70%); }
.blob.b3 { width: 700px; height: 420px; left: 30%; bottom: -260px; opacity: .4; }
.grid {
    position: absolute; left: -50%; right: -50%; bottom: -10%; height: 55%;
    background-image:
        linear-gradient(rgba(var(--accent-rgb), .35) 1px, transparent 1px),
        linear-gradient(90deg, rgba(var(--accent-rgb), .35) 1px, transparent 1px);
    background-size: 64px 64px;
    transform: perspective(420px) rotateX(62deg);
    transform-origin: center top;
    -webkit-mask-image: linear-gradient(to bottom, transparent 0%, black 45%, black 100%);
    mask-image: linear-gradient(to bottom, transparent 0%, black 45%, black 100%);
    opacity: .45;
}
.horizon {
    position: absolute; left: 0; right: 0; bottom: 45%; height: 2px;
    background: linear-gradient(90deg, transparent, rgba(var(--accent-rgb), .9), transparent);
    box-shadow: 0 0 24px 4px rgba(var(--accent-rgb), .55);
    opacity: .5;
}
.vignette { position: absolute; inset: 0; background: radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,.65) 100%); }
.ember {
    position: absolute; bottom: -12px; width: 3px; height: 3px; border-radius: 50%;
    background: var(--accent); box-shadow: 0 0 8px 2px rgba(var(--accent-rgb), .8); opacity: 0;
}
.anim .blob.b1 { animation: drift1 22s ease-in-out infinite alternate; }
.anim .blob.b2 { animation: drift2 28s ease-in-out infinite alternate; }
.anim .blob.b3 { animation: drift3 25s ease-in-out infinite alternate; }
.anim .grid { animation: gridmove 3.2s linear infinite; }
.anim .ember { animation: rise linear infinite; }
@keyframes drift1 { to { transform: translate(180px, 120px) scale(1.15); } }
@keyframes drift2 { to { transform: translate(-160px, 90px) scale(.9); } }
@keyframes drift3 { to { transform: translate(-120px, -60px) scale(1.2); } }
@keyframes gridmove { from { background-position: 0 0; } to { background-position: 0 64px; } }
@keyframes rise {
    0% { transform: translateY(0) translateX(0); opacity: 0; }
    10% { opacity: .9; }
    100% { transform: translateY(-105vh) translateX(40px); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) { .anim * { animation: none !important; } }

/* ---------- layout ---------- */
.wrap { position: relative; z-index: 1; max-width: 1040px; margin: 0 auto; padding: 22px 28px 40px; }
.top { display: flex; align-items: center; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 10px; letter-spacing: .32em; font-size: 13px; color: var(--muted); }
.brand svg { width: 26px; height: 26px; filter: drop-shadow(0 0 8px rgba(var(--accent-rgb), .7)); }
.brand b { color: var(--text); font-weight: 600; }
.status {
    display: flex; align-items: center; gap: 9px; padding: 7px 14px 7px 12px;
    --cut: 10px; --edge: rgba(var(--accent-rgb), .6); --fill: rgba(20, 12, 22, .85);
    font-size: 12px; letter-spacing: .14em;
}
.status > * { position: relative; z-index: 1; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 10px var(--ok); }
.anim .dot { animation: pulse 1.8s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: .35; } }

.hero { text-align: center; margin: 46px 0 26px; }
.clock {
    font-size: 96px; font-weight: 600; line-height: 1; letter-spacing: .02em;
    text-shadow: 0 0 28px rgba(var(--accent-rgb), .55), 0 0 2px rgba(255,255,255,.6);
}
.clock .sec { font-size: 30px; color: var(--accent); margin-left: 6px; vertical-align: top; }
.date { margin-top: 10px; color: var(--muted); font-size: 15px; letter-spacing: .08em; }
.greet { margin-top: 4px; font-size: 18px; }
.greet b { color: var(--accent); font-weight: 600; }

.searchwrap { max-width: 680px; margin: 0 auto 38px; }
.searchwrap:focus-within { filter: drop-shadow(0 0 14px rgba(var(--accent-rgb), .45)); }
.search { --fill: rgba(23, 20, 33, .82); }
.search:focus-within { --edge: var(--accent); --fill: rgba(13, 11, 19, .96); }
.search input { position: relative; z-index: 1; }
.search svg { position: absolute; z-index: 1; left: 20px; top: 50%; transform: translateY(-50%); width: 20px; height: 20px; stroke: var(--muted); }
.search:focus-within svg { stroke: var(--accent); }
.search input {
    width: 100%; background: transparent; border: none; outline: none; color: var(--text);
    padding: 18px 60px 18px 56px; font-size: 16px; font-family: inherit;
}
.search input::placeholder { color: var(--dim); }
.search kbd {
    position: absolute; z-index: 1; right: 18px; top: 50%; transform: translateY(-50%);
    border: 1px solid var(--line); color: var(--dim); border-radius: 5px; padding: 2px 7px; font-size: 12px;
}

.label { display: flex; align-items: center; gap: 12px; color: var(--muted); font-size: 12px; letter-spacing: .28em; margin: 0 0 14px; }
.label::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, rgba(var(--accent-rgb), .5), transparent); }

.dial { display: grid; grid-template-columns: repeat(auto-fill, minmax(124px, 1fr)); gap: 14px; margin-bottom: 36px; }
.tw { transition: transform .18s ease, filter .2s ease; }
.tw:hover { transform: translateY(-3px); filter: drop-shadow(0 8px 18px rgba(var(--accent-rgb), .35)); }
.tile {
    height: 112px; text-decoration: none; color: var(--text);
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
    cursor: pointer; user-select: none;
}
.tile > * { position: relative; z-index: 1; }
.tw:hover .tile { --edge: var(--accent); --fill: var(--card-hover); }
.tile::before {
    content: ""; position: absolute; z-index: 2; left: 0; right: 0; bottom: 0; height: 2px;
    background: var(--accent); transform: scaleX(0); transition: transform .2s; transform-origin: left;
}
.tw:hover .tile::before { transform: scaleX(1); }
.glyph {
    width: 46px; height: 46px; border-radius: 12px; display: grid; place-items: center;
    font-family: "Bahnschrift", sans-serif; font-weight: 700; font-size: 19px;
}
.tile .name { font-size: 13px; color: var(--muted); max-width: 90%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tw:hover .name { color: var(--text); }
.tile > .del {
    position: absolute; z-index: 3; top: 6px; right: 16px; width: 22px; height: 22px; border-radius: 6px; border: none;
    background: rgba(0,0,0,.5); color: var(--muted); font-size: 14px; cursor: pointer; opacity: 0; transition: opacity .15s;
}
.tw:hover .del { opacity: 1; }
.del:hover { background: var(--accent); color: #fff; }
.tile.add { --edge: rgba(255, 255, 255, .14); --fill: rgba(23, 20, 33, .45); color: var(--dim); }
.tile.add .glyph { border: 1px dashed var(--dim); font-size: 26px; font-weight: 400; color: var(--muted); }

.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
.stat { padding: 18px 20px; }
.stat > * { position: relative; z-index: 1; }
.stat .k { color: var(--muted); font-size: 11px; letter-spacing: .24em; }
.stat .v { font-size: 34px; font-weight: 700; margin-top: 6px; color: var(--accent); text-shadow: 0 0 18px rgba(var(--accent-rgb), .45); }
.stat .v.ok { color: var(--ok); text-shadow: 0 0 18px rgba(46, 232, 138, .35); font-size: 22px; margin-top: 10px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip { font-size: 12px; color: var(--muted); border: 1px solid var(--line); padding: 3px 9px; border-radius: 20px; }
.chip b { color: var(--text); }
.foot { text-align: center; color: var(--dim); font-size: 12px; margin-top: 30px; letter-spacing: .06em; }

/* ---------- modal ---------- */
.modal { position: fixed; inset: 0; z-index: 10; background: rgba(5, 4, 9, .72); display: none; align-items: center; justify-content: center; }
.modal.open { display: flex; }
.sheet { width: 400px; padding: 24px; --cut: 18px; --edge: rgba(var(--accent-rgb), .6); --fill: #13111b; }
.sheet > * { position: relative; z-index: 1; }
.sheet h3 { font-size: 20px; font-weight: 600; margin-bottom: 16px; }
.sheet label { display: block; color: var(--muted); font-size: 12px; letter-spacing: .12em; margin: 12px 0 6px; }
.sheet input {
    width: 100%; background: #1b1826; border: 1px solid var(--line); color: var(--text);
    padding: 10px 12px; border-radius: 8px; outline: none; font-size: 14px; font-family: inherit;
}
.sheet input:focus { border-color: var(--accent); }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.btn { border: 1px solid var(--line); background: #1b1826; color: var(--text); padding: 9px 18px; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
.btn:hover { filter: brightness(1.12); }
</style>
</head>
<body class="__ANIM_CLASS__">
<div class="bg">
    <div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div>
    <div class="horizon"></div><div class="grid"></div><div class="vignette"></div>
    <div id="embers"></div>
</div>

<div class="wrap">
    <div class="top">
        <div class="brand gx">
            <svg viewBox="0 0 24 24"><path d="M12 1.8l8.4 3.2v6.3c0 5.4-3.6 10-8.4 11.5C7.2 21.3 3.6 16.7 3.6 11.3V5z" fill="rgba(__ACCENT_RGB__,.16)" stroke="__ACCENT__" stroke-width="1.8" stroke-linejoin="round"/><path d="M7.6 9.2l4.4 3 4.4-3v3.6l-4.4 3-4.4-3z" fill="__ACCENT__"/></svg>
            <span><b>ADBLOCK</b> GX</span>
        </div>
        <div class="status cut gx"><span class="dot"></span><span>SCHUTZ AKTIV</span></div>
    </div>

    <div class="hero">
        <div class="clock gx"><span id="hm">--:--</span><span class="sec" id="sec">00</span></div>
        <div class="date gx" id="date"></div>
        <div class="greet" id="greet"></div>
    </div>

    <div class="searchwrap glow"><form class="search cut" id="searchForm" autocomplete="off">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20.5 20.5l-4.5-4.5"/></svg>
        <input id="q" placeholder="Mit DuckDuckGo suchen oder Adresse eingeben" autofocus>
        <kbd>/</kbd>
    </form></div>

    <div class="label gx">SCHNELLZUGRIFF</div>
    <div class="dial" id="dial"></div>

    <div class="label gx">SHIELD</div>
    <div class="stats">
        <div class="stat cut one"><div class="k gx">BLOCKIERT GESAMT</div><div class="v gx" id="total">0</div>
            <div class="chips"><span class="chip">Werbung, Tracker &amp; Popups</span></div></div>
        <div class="stat cut one"><div class="k gx">VIDEO-WERBUNG ABGEFANGEN</div><div class="v gx" id="video">0</div>
            <div class="chips" id="videoChips"></div></div>
        <div class="stat cut one"><div class="k gx">ENGINE</div><div class="v ok gx">&#9679; Brave Rust-Engine</div>
            <div class="chips"><span class="chip">EasyList</span><span class="chip">EasyPrivacy</span><span class="chip">EasyList DE</span><span class="chip">Peter Lowe</span></div></div>
    </div>
    <div class="foot">AdBlock Browser GX &middot; Twitch &middot; YouTube &middot; South Park ohne Werbung</div>
</div>

<div class="modal" id="modal">
    <div class="sheet cut">
        <h3 class="gx">Schnellzugriff hinzufügen</h3>
        <label class="gx">NAME</label><input id="mName" placeholder="z. B. Twitch">
        <label class="gx">ADRESSE</label><input id="mUrl" placeholder="twitch.tv">
        <label class="gx">SYMBOL (optional, 1–2 Zeichen)</label><input id="mGlyph" maxlength="2" placeholder="T">
        <div class="actions"><button class="btn" id="mCancel">Abbrechen</button><button class="btn primary" id="mSave">Speichern</button></div>
    </div>
</div>

<script>
const STATS = __STATS__;
const DEFAULTS = [
    {title: 'Twitch', url: 'https://www.twitch.tv', emoji: 'T', color: '#a970ff'},
    {title: 'YouTube', url: 'https://www.youtube.com', emoji: '▶', color: '#ff3355'},
    {title: 'South Park', url: 'https://www.southpark.de', emoji: 'SP', color: '#ffb02e'},
    {title: 'Steam', url: 'https://store.steampowered.com', emoji: 'S', color: '#66c0f4'},
    {title: 'Epic Games', url: 'https://store.epicgames.com/de/free-games', emoji: 'E', color: '#e8e8e8'},
    {title: 'Discord', url: 'https://discord.com/app', emoji: 'D', color: '#7c86ff'},
    {title: 'Reddit', url: 'https://www.reddit.com', emoji: 'R', color: '#ff5722'},
    {title: 'Wikipedia', url: 'https://de.wikipedia.org', emoji: 'W', color: '#d8d8d8'}
];
const KEY = 'adblock_browser_shortcuts';

function load() { try { const d = localStorage.getItem(KEY); if (d) return JSON.parse(d); } catch (e) {} return DEFAULTS; }
function save(list) { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) {} }
function hexToRgb(c) {
    const m = /^#?([0-9a-f]{6})$/i.exec(c || '');
    if (!m) return null;
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function render() {
    const dial = document.getElementById('dial');
    dial.innerHTML = '';
    load().forEach((item, i) => {
        const wrap = document.createElement('div');
        wrap.className = 'tw';
        const a = document.createElement('a');
        a.className = 'tile cut'; a.href = item.url; a.title = item.url;
        const g = document.createElement('div');
        g.className = 'glyph';
        const color = item.color && item.color.startsWith('#') ? item.color : getComputedStyle(document.body).getPropertyValue('--accent');
        const rgb = hexToRgb(color.trim()) || [250, 30, 78];
        g.style.color = color;
        g.style.background = `rgba(${rgb.join(',')}, .14)`;
        g.style.boxShadow = `inset 0 0 0 1px rgba(${rgb.join(',')}, .35)`;
        g.textContent = item.emoji || (item.title || '?').slice(0, 1).toUpperCase();
        const n = document.createElement('div');
        n.className = 'name'; n.textContent = item.title;
        const del = document.createElement('button');
        del.className = 'del'; del.textContent = '×'; del.title = 'Entfernen';
        del.onclick = (e) => { e.preventDefault(); e.stopPropagation(); const l = load(); l.splice(i, 1); save(l); render(); };
        a.append(g, n, del);
        wrap.appendChild(a);
        dial.appendChild(wrap);
    });
    const addWrap = document.createElement('div');
    addWrap.className = 'tw';
    const add = document.createElement('div');
    add.className = 'tile add cut';
    add.innerHTML = '<div class="glyph">+</div><div class="name">Hinzufügen</div>';
    add.onclick = openModal;
    addWrap.appendChild(add);
    dial.appendChild(addWrap);
}

function openModal() {
    ['mName', 'mUrl', 'mGlyph'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('modal').classList.add('open');
    document.getElementById('mName').focus();
}
function closeModal() { document.getElementById('modal').classList.remove('open'); }
document.getElementById('mCancel').onclick = closeModal;
document.getElementById('modal').onclick = (e) => { if (e.target.id === 'modal') closeModal(); };
document.getElementById('mSave').onclick = () => {
    const title = document.getElementById('mName').value.trim();
    let url = document.getElementById('mUrl').value.trim();
    if (!title || !url) return;
    if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
    const list = load();
    list.push({title, url, emoji: document.getElementById('mGlyph').value.trim() || null, color: null});
    save(list); closeModal(); render();
};

document.getElementById('searchForm').onsubmit = (e) => {
    e.preventDefault();
    const v = document.getElementById('q').value.trim();
    if (!v) return;
    if (/^https?:\/\//i.test(v)) location.href = v;
    else if (/^[^\s]+\.[^\s]{2,}$/.test(v)) location.href = 'https://' + v;
    else location.href = 'https://duckduckgo.com/?q=' + encodeURIComponent(v);
};
document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT') { e.preventDefault(); document.getElementById('q').focus(); }
    if (e.key === 'Escape') closeModal();
});

function tick() {
    const d = new Date();
    document.getElementById('hm').textContent = d.toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'});
    document.getElementById('sec').textContent = String(d.getSeconds()).padStart(2, '0');
    document.getElementById('date').textContent = d.toLocaleDateString('de-DE', {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'}).toUpperCase();
    const h = d.getHours();
    const g = h < 5 ? 'Noch wach? <b>Ready to play.</b>' : (h < 11 ? 'Guten Morgen' : h < 17 ? 'Guten Tag' : h < 22 ? 'Guten Abend' : 'Gute Nacht') + ' \u2013 <b>ready to play.</b>';
    document.getElementById('greet').innerHTML = g;
}
tick(); setInterval(tick, 1000);

function countUp(el, target) {
    const fmt = (n) => n.toLocaleString('de-DE');
    if (!document.body.classList.contains('anim') || target < 10) { el.textContent = fmt(target); return; }
    const t0 = performance.now(), dur = 1100;
    (function step(t) {
        const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3);
        el.textContent = fmt(Math.round(target * e));
        if (p < 1) requestAnimationFrame(step);
    })(t0);
}
countUp(document.getElementById('total'), STATS.total || 0);
const v = STATS.video || {};
countUp(document.getElementById('video'), (v.twitch || 0) + (v.youtube || 0) + (v.southpark || 0));
document.getElementById('videoChips').innerHTML =
    `<span class="chip">Twitch <b>${v.twitch || 0}</b></span><span class="chip">YouTube <b>${v.youtube || 0}</b></span><span class="chip">South Park <b>${v.southpark || 0}</b></span>`;

if (document.body.classList.contains('anim')) {
    const box = document.getElementById('embers');
    for (let i = 0; i < 22; i++) {
        const s = document.createElement('span');
        s.className = 'ember';
        s.style.left = (Math.random() * 100) + '%';
        s.style.animationDuration = (9 + Math.random() * 12) + 's';
        s.style.animationDelay = (-Math.random() * 20) + 's';
        s.style.transform = `scale(${0.6 + Math.random()})`;
        box.appendChild(s);
    }
}
render();
</script>
</body>
</html>
"""


def get_start_page_html(blocked_count: int = 0, accent: str = "#fa1e4e", video_counts: dict | None = None,
                        animations: bool = True) -> str:
    h = accent.lstrip("#")
    rgb = f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
    stats = json.dumps({"total": int(blocked_count), "video": video_counts or {}})
    return (START_PAGE_TEMPLATE
            .replace("__ACCENT_RGB__", rgb)
            .replace("__ACCENT__", accent)
            .replace("__STATS__", stats)
            .replace("__ANIM_CLASS__", "anim" if animations else "still"))


# The start page is served from a virtual host (CoreWebView2.SetVirtualHostNameToFolderMapping)
# instead of NavigateToString, so it has a real origin: localStorage works (custom speed dials
# are kept) and the tab's URL is not "about:blank". ".example" is reserved and never resolves.
START_HOST = "start.adblockbrowser.example"
START_URL = f"https://{START_HOST}/index.html"


def is_start_page(url: str) -> bool:
    return bool(url) and url.startswith(f"https://{START_HOST}/")


def write_start_page(folder: str, blocked_count: int = 0, accent: str = "#fa1e4e",
                     video_counts: dict | None = None, animations: bool = True):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
        f.write(get_start_page_html(blocked_count, accent, video_counts, animations))
