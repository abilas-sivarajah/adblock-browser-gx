"""Live test of the ad logger in the hidden browser. Each scenario temporarily patches a file of the
Claude copy where needed and always restores it."""
import json, os, shutil, subprocess, sys, time
from features_test_lib import *

LOGS = os.path.join(TESTDATA, "logs")
SITE_SCRIPTS = os.path.join(APP, "site_scripts.py")
YT = os.path.join(APP, "scripts", "youtube.js")


class TempPatch:
    def __init__(self, path, old, new):
        self.path, self.old, self.new = path, old, new

    def __enter__(self):
        self.orig = open(self.path, encoding="utf-8").read()
        assert self.orig.count(self.old) == 1, self.old
        open(self.path, "w", encoding="utf-8").write(self.orig.replace(self.old, self.new))

    def __exit__(self, *a):
        open(self.path, "w", encoding="utf-8").write(self.orig)


def log_entries():
    f = os.path.join(LOGS, "werbung.log")
    return [json.loads(l) for l in open(f, encoding="utf-8")] if os.path.exists(f) else []


def incidents():
    d = os.path.join(LOGS, "vorfaelle")
    return sorted(os.listdir(d)) if os.path.exists(d) else []


def show_new(before_entries, before_incidents):
    for e in log_entries()[len(before_entries):]:
        print(f"   LOG  [{e['site']}] {e['kind']}: {e['summary'][:110]}  {('-> ' + e['incident']) if e['incident'] else ''}")
    for inc in incidents():
        if inc not in before_incidents:
            files = sorted(os.listdir(os.path.join(LOGS, "vorfaelle", inc)))
            sizes = {f: os.path.getsize(os.path.join(LOGS, "vorfaelle", inc, f)) for f in files}
            print(f"   VORFALL {inc}: {sizes}")


FORCE_EMBED = r"""
(() => {
  const swap = b => typeof b === 'string' ? b.replace(/"playerType":"site"/g, '"playerType":"embed"') : b;
  const f = window.fetch;
  window.fetch = function (input, init) {
    const u = typeof input === 'string' ? input : input && input.url;
    if (u && u.includes('gql.twitch.tv') && input instanceof Request && !init) {
      const self = this;
      return input.clone().text().then(b => f.call(self, new Request(input, {body: swap(b)})));
    }
    if (u && u.includes('gql.twitch.tv') && init && typeof init.body === 'string') init = Object.assign({}, init, {body: swap(init.body)});
    return f.call(this, input, init);
  };
})();
"""


def twitch_run(name, secs=20):
    launch("https://www.twitch.tv/directory", name)
    p = page_for("twitch.tv")
    time.sleep(4)
    p.call("Page.enable")
    p.call("Page.addScriptToEvaluateOnNewDocument", source=FORCE_EMBED)
    p.call("Page.navigate", url="https://www.twitch.tv/gotaga")
    time.sleep(secs)
    print("   __abTwitch:", json.dumps(p.ev("window.__abTwitch && {ads: __abTwitch.adBreaks, replaced: __abTwitch.replaced, stripped: __abTwitch.stripped, backup: __abTwitch.lastBackupType}")))


shutil.rmtree(LOGS, ignore_errors=True)

print("1) Twitch, Werbung wird ersetzt:")
b, bi = log_entries(), incidents()
twitch_run("log_tw1")
show_new(b, bi)

print("2) Twitch, kein werbefreier Ersatz (nur 'embed' erlaubt) -> Werbung wird herausgeschnitten:")
b, bi = log_entries(), incidents()
with TempPatch(SITE_SCRIPTS, 'TWITCH_BACKUP_TYPES = ["popout", "frontpage", "autoplay", "embed"]', 'TWITCH_BACKUP_TYPES = ["embed"]'):
    twitch_run("log_tw2")
    time.sleep(2)
show_new(b, bi)

print("3) YouTube normal (Werbe-Daten werden entfernt):")
b, bi = log_entries(), incidents()
launch("https://www.youtube.com/watch?v=OPf0YbXqDm0", "log_yt1")
p = page_for("youtube.com"); time.sleep(15)
show_new(b, bi)

print("4) YouTube mit abgeschaltetem Entfernen -> Werbung kommt durch:")
b, bi = log_entries(), incidents()
with TempPatch(YT, "    function prune(obj) {\n        if (!obj || typeof obj !== 'object') return false;",
               "    function prune(obj) {\n        return false;  // TEMP logger test\n        if (!obj || typeof obj !== 'object') return false;"):
    launch("https://www.youtube.com/watch?v=OPf0YbXqDm0", "log_yt2")
    p = page_for("youtube.com"); time.sleep(25)
show_new(b, bi)

print("5) South Park:")
b, bi = log_entries(), incidents()
launch("https://www.southpark.de/folgen/mphf21/south-park-butters-ober-bitch-staffel-13-ep-9", "log_sp")
p = page_for("southpark.de"); time.sleep(20)
show_new(b, bi)
kill()

print("6) Von Hand melden (heise.de):")
b, bi = log_entries(), incidents()
kill()
if os.path.exists(os.path.join(SCRATCH, "manual_harness.log")): os.remove(os.path.join(SCRATCH, "manual_harness.log"))
proc = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "manual_harness.py")], cwd=APP,
                        stdout=open(os.path.join(SCRATCH, "app_manual.log"), "w"), stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
proc.wait(timeout=60)
print("   harness:", open(os.path.join(SCRATCH, "manual_harness.log")).read().strip()[:200])
show_new(b, bi)
