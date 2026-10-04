"""
Start Page Generator for AdBlock Browser.
Creates a modern, sleek New Tab page with customizable Speed Dial shortcuts (with icons),
Search, and Live Shield stats.
"""

import os

START_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neuer Tab - AdBlock Browser</title>
    <style>
        :root {
            --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
            --card-bg: rgba(30, 41, 59, 0.7);
            --card-hover: rgba(51, 65, 85, 0.95);
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.35);
            --shield-green: #10b981;
            --shield-glow: rgba(16, 185, 129, 0.3);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: rgba(255, 255, 255, 0.1);
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }
        body {
            background: var(--bg-gradient);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            padding: 40px 20px;
            user-select: none;
        }
        .header {
            text-align: center;
            margin-top: 20px;
            margin-bottom: 25px;
        }
        .time {
            font-size: 3.5rem;
            font-weight: 700;
            letter-spacing: -1px;
            background: linear-gradient(to right, #ffffff, #94a3b8);
            -webkit-background-clip: text;
            color: transparent;
        }
        .greeting {
            font-size: 1.1rem;
            color: var(--text-muted);
            margin-top: 5px;
        }
        .shield-banner {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 9999px;
            padding: 8px 20px;
            margin-top: 15px;
            font-size: 0.95rem;
            color: #34d399;
            box-shadow: 0 0 20px var(--shield-glow);
        }
        .shield-banner svg {
            width: 18px;
            height: 18px;
            fill: currentColor;
        }
        .search-container {
            width: 100%;
            max-width: 650px;
            margin-bottom: 40px;
            position: relative;
        }
        .search-box {
            width: 100%;
            padding: 16px 24px 16px 54px;
            border-radius: 30px;
            background: rgba(30, 41, 59, 0.85);
            border: 1px solid var(--border);
            color: var(--text-main);
            font-size: 1.1rem;
            outline: none;
            backdrop-filter: blur(12px);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
            transition: all 0.25s ease;
        }
        .search-box:focus {
            border-color: var(--accent);
            box-shadow: 0 0 25px var(--accent-glow);
            background: rgba(30, 41, 59, 1);
        }
        .search-icon {
            position: absolute;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
        }
        .shortcuts-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            width: 100%;
            max-width: 680px;
            margin-bottom: 40px;
        }
        .shortcut-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px 12px;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: var(--text-main);
            backdrop-filter: blur(8px);
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            position: relative;
        }
        .shortcut-card:hover {
            background: var(--card-hover);
            transform: translateY(-4px);
            border-color: var(--accent);
            box-shadow: 0 12px 24px -6px rgba(0, 0, 0, 0.5);
        }
        .shortcut-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: 600;
            overflow: hidden;
        }
        .shortcut-icon img {
            width: 32px;
            height: 32px;
            object-fit: contain;
            border-radius: 6px;
        }
        .shortcut-title {
            font-size: 0.9rem;
            font-weight: 500;
            color: var(--text-main);
            text-align: center;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 110px;
        }
        .delete-btn {
            position: absolute;
            top: 6px;
            right: 8px;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: rgba(239, 68, 68, 0.8);
            color: white;
            display: none;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
            border: none;
        }
        .shortcut-card:hover .delete-btn {
            display: flex;
        }
        .delete-btn:hover {
            background: #ef4444;
            transform: scale(1.1);
        }
        .add-card {
            border: 1px dashed rgba(255, 255, 255, 0.2);
            background: rgba(30, 41, 59, 0.4);
        }
        .add-card:hover {
            border-color: var(--accent);
            background: rgba(30, 41, 59, 0.8);
        }
        .add-icon {
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent);
            font-size: 1.8rem;
        }

        /* Modal Styles */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(8px);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        .modal-overlay.active {
            display: flex;
        }
        .modal {
            background: #1e293b;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
        }
        .modal-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text-main);
        }
        .modal-field {
            margin-bottom: 14px;
        }
        .modal-label {
            display: block;
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-bottom: 6px;
        }
        .modal-input {
            width: 100%;
            padding: 10px 14px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: var(--text-main);
            font-size: 0.95rem;
            outline: none;
        }
        .modal-input:focus {
            border-color: var(--accent);
        }
        .modal-actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-top: 20px;
        }
        .modal-btn {
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }
        .modal-btn-cancel {
            background: #334155;
            color: var(--text-muted);
        }
        .modal-btn-cancel:hover {
            background: #475569;
            color: var(--text-main);
        }
        .modal-btn-save {
            background: #0284c7;
            color: white;
        }
        .modal-btn-save:hover {
            background: #0369a1;
        }

        .stats-footer {
            margin-top: auto;
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-muted);
            padding: 20px;
        }
    </style>
</head>
<body>

    <div class="header">
        <div class="time" id="clock">12:00</div>
        <div class="greeting" id="dateStr">Willkommen</div>
        <div class="shield-banner">
            <svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg>
            <span>Werbe- &amp; Trackingschutz aktiv &bull; <strong id="blockedCount">__BLOCKED_COUNT__</strong> Elemente blockiert</span>
        </div>
    </div>

    <div class="search-container">
        <svg class="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input type="text" class="search-box" id="searchInput" placeholder="Web durchsuchen oder URL eingeben..." autofocus />
    </div>

    <div class="shortcuts-grid" id="shortcutsGrid">
        <!-- Rendered dynamically via JavaScript -->
    </div>

    <div class="stats-footer">
        AdBlock Browser &bull; Sicher, blitzschnell und werbefrei surfen
    </div>

    <!-- Modal for adding a new shortcut with icon -->
    <div class="modal-overlay" id="addModal">
        <div class="modal">
            <div class="modal-title">Verknüpfung hinzufügen</div>
            <div class="modal-field">
                <label class="modal-label">Name</label>
                <input type="text" class="modal-input" id="shortcutName" placeholder="z. B. Twitch oder ChatGPT" />
            </div>
            <div class="modal-field">
                <label class="modal-label">Webadresse (URL)</label>
                <input type="text" class="modal-input" id="shortcutUrl" placeholder="https://..." />
            </div>
            <div class="modal-field">
                <label class="modal-label">Optionales Symbol / Emoji</label>
                <input type="text" class="modal-input" id="shortcutEmoji" placeholder="z. B. 🎮 oder leer lassen für automatisches Favicon" />
            </div>
            <div class="modal-actions">
                <button class="modal-btn modal-btn-cancel" onclick="closeAddModal()">Abbrechen</button>
                <button class="modal-btn modal-btn-save" onclick="saveShortcut()">Speichern</button>
            </div>
        </div>
    </div>

    <script>
        function updateTime() {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            document.getElementById('clock').textContent = h + ':' + m;
            
            const options = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
            document.getElementById('dateStr').textContent = now.toLocaleDateString('de-DE', options);
        }
        setInterval(updateTime, 1000);
        updateTime();

        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                const val = searchInput.value.trim();
                if (!val) return;
                if (val.startsWith('http://') || val.startsWith('https://')) {
                    window.location.href = val;
                } else if (val.includes('.') && !val.includes(' ')) {
                    window.location.href = 'https://' + val;
                } else {
                    window.location.href = 'https://duckduckgo.com/?q=' + encodeURIComponent(val);
                }
            }
        });

        // Default shortcuts
        const DEFAULT_SHORTCUTS = [
            { title: 'YouTube', url: 'https://www.youtube.com', emoji: '▶', bg: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' },
            { title: 'Google', url: 'https://www.google.de', emoji: 'G', bg: 'rgba(59, 130, 246, 0.2)', color: '#60a5fa' },
            { title: 'Wikipedia', url: 'https://de.wikipedia.org', emoji: 'W', bg: 'rgba(255, 255, 255, 0.15)', color: '#f8fafc' },
            { title: 'GitHub', url: 'https://github.com', emoji: '⌨', bg: 'rgba(255, 255, 255, 0.1)', color: '#cbd5e1' },
            { title: 'Reddit', url: 'https://www.reddit.com', emoji: '🤖', bg: 'rgba(249, 115, 22, 0.2)', color: '#fb923c' },
            { title: 'Spiegel', url: 'https://www.spiegel.de', emoji: 'S', bg: 'rgba(239, 68, 68, 0.2)', color: '#f87171' },
            { title: 'Heise', url: 'https://www.heise.de', emoji: 'H', bg: 'rgba(20, 184, 166, 0.2)', color: '#2dd4bf' },
            { title: 'Tagesschau', url: 'https://www.tagesschau.de', emoji: 'T', bg: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }
        ];

        function getStoredShortcuts() {
            try {
                const data = localStorage.getItem('adblock_browser_shortcuts');
                if (data) return JSON.parse(data);
            } catch(e) {}
            return DEFAULT_SHORTCUTS;
        }

        function saveStoredShortcuts(shortcuts) {
            try {
                localStorage.setItem('adblock_browser_shortcuts', JSON.stringify(shortcuts));
            } catch(e) {}
        }

        function renderShortcuts() {
            const grid = document.getElementById('shortcutsGrid');
            grid.innerHTML = '';
            const list = getStoredShortcuts();

            list.forEach((item, index) => {
                const card = document.createElement('a');
                card.className = 'shortcut-card';
                card.href = item.url;

                // Delete button
                const delBtn = document.createElement('button');
                delBtn.className = 'delete-btn';
                delBtn.innerHTML = '&times;';
                delBtn.title = 'Verknüpfung entfernen';
                delBtn.onclick = function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    deleteShortcut(index);
                };
                card.appendChild(delBtn);

                // Icon container
                const iconDiv = document.createElement('div');
                iconDiv.className = 'shortcut-icon';

                if (item.emoji) {
                    iconDiv.textContent = item.emoji;
                    iconDiv.style.background = item.bg || 'rgba(56, 189, 248, 0.15)';
                    iconDiv.style.color = item.color || '#38bdf8';
                } else {
                    // Try favicon
                    let domain = item.url;
                    try {
                        domain = new URL(item.url).hostname;
                    } catch(e) {}
                    const img = document.createElement('img');
                    img.src = 'https://www.google.com/s2/favicons?sz=64&domain=' + domain;
                    img.alt = item.title;
                    img.onerror = function() {
                        iconDiv.innerHTML = item.title.charAt(0).toUpperCase();
                        iconDiv.style.background = 'rgba(56, 189, 248, 0.15)';
                        iconDiv.style.color = '#38bdf8';
                    };
                    iconDiv.appendChild(img);
                }

                const titleSpan = document.createElement('span');
                titleSpan.className = 'shortcut-title';
                titleSpan.textContent = item.title;

                card.appendChild(iconDiv);
                card.appendChild(titleSpan);
                grid.appendChild(card);
            });

            // Add new shortcut card
            const addCard = document.createElement('div');
            addCard.className = 'shortcut-card add-card';
            addCard.title = 'Neue Verknüpfung im Browser hinzufügen';
            addCard.onclick = openAddModal;

            const addIcon = document.createElement('div');
            addIcon.className = 'shortcut-icon add-icon';
            addIcon.textContent = '+';

            const addTitle = document.createElement('span');
            addTitle.className = 'shortcut-title';
            addTitle.textContent = 'Hinzufügen';

            addCard.appendChild(addIcon);
            addCard.appendChild(addTitle);
            grid.appendChild(addCard);
        }

        function deleteShortcut(index) {
            const list = getStoredShortcuts();
            list.splice(index, 1);
            saveStoredShortcuts(list);
            renderShortcuts();
        }

        function openAddModal() {
            document.getElementById('shortcutName').value = '';
            document.getElementById('shortcutUrl').value = '';
            document.getElementById('shortcutEmoji').value = '';
            document.getElementById('addModal').classList.add('active');
            document.getElementById('shortcutName').focus();
        }

        function closeAddModal() {
            document.getElementById('addModal').classList.remove('active');
        }

        function saveShortcut() {
            const name = document.getElementById('shortcutName').value.trim();
            let url = document.getElementById('shortcutUrl').value.trim();
            const emoji = document.getElementById('shortcutEmoji').value.trim();

            if (!name || !url) {
                alert('Bitte Name und Webadresse eingeben.');
                return;
            }

            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                url = 'https://' + url;
            }

            const list = getStoredShortcuts();
            list.push({
                title: name,
                url: url,
                emoji: emoji || null,
                bg: 'rgba(56, 189, 248, 0.2)',
                color: '#38bdf8'
            });
            saveStoredShortcuts(list);
            closeAddModal();
            renderShortcuts();
        }

        // Render on load
        renderShortcuts();
    </script>
</body>
</html>
"""

def get_start_page_html(blocked_count: int = 0) -> str:
    return START_PAGE_TEMPLATE.replace("__BLOCKED_COUNT__", str(blocked_count))


# The start page is served from a virtual host (CoreWebView2.SetVirtualHostNameToFolderMapping)
# instead of NavigateToString, so it has a real origin: localStorage works (custom speed dials
# are kept) and the tab's URL is not "about:blank". ".example" is reserved and never resolves.
START_HOST = "start.adblockbrowser.example"
START_URL = f"https://{START_HOST}/index.html"


def is_start_page(url: str) -> bool:
    return bool(url) and url.startswith(f"https://{START_HOST}/")


def write_start_page(folder: str, blocked_count: int = 0):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as f:
        f.write(get_start_page_html(blocked_count))
