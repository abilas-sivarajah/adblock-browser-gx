"""After moving/copying the project: does the real profile (browser_data) still work at the new place?
Starts hidden with the USER profile (only when the normal browser is closed), opens netflix.com/browse and
reports whether the login survived. Nothing is played."""
import json, time
from nf_live import start, stop, USER_DATA
from features_test_lib import pages, Page, wait_for

print("Profil:", USER_DATA)
start("https://www.netflix.com/browse", "profile_check")
target = wait_for(lambda: next((t for t in pages() if "netflix.com" in t["url"]), None), 40)
p = Page(target)
wait_for(lambda: p.ev("document.readyState === 'complete' && document.body.innerText.length > 200"), 30)
time.sleep(4)
# logged out -> Netflix redirects to /login or the landing page ("Anmelden", no title rows)
state = p.ev(r"""(() => { const t = document.body.innerText.replace(/\s+/g, ' ');
  return {pfad: location.pathname, profilauswahl: /Wer schaut gerade|Who's watching/i.test(t),
          titelreihen: document.querySelectorAll('.lolomoRow, [data-list-context], .title-card-container').length,
          anmeldeseite: /\/login|LoginHelp/i.test(location.pathname) || /^Anmelden|Jetzt anmelden|Sign In/.test(t.trim()),
          eingeloggt: /^\/browse/.test(location.pathname) && !/Jetzt anmelden|Sign In/.test(t)}; })()""")
print("Netflix:", json.dumps(state, ensure_ascii=False))
stop()
