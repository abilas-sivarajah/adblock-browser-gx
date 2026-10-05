"""Restart the Claude copy of the browser with given user rules and report player state.

usage: python trial.py <name> [rules-file-content (\\n separated)] [--wait N] [--url URL]
"""
import json, os, subprocess, sys, time, urllib.request

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(SCRATCH, exist_ok=True)
EPISODE = "https://www.southpark.de/folgen/mphf21/south-park-butters-ober-bitch-staffel-13-ep-9"

args = sys.argv[1:]
name = args.pop(0)
wait = 25
url = EPISODE
rules = None
while args:
    a = args.pop(0)
    if a == "--wait":
        wait = float(args.pop(0))
    elif a == "--url":
        url = args.pop(0)
    else:
        rules = a.replace("\\n", "\n")


def kill():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*main.py*' -and $_.CommandLine -notlike '*trial.py*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    # wait for the WebView2 processes of this profile to exit
    for _ in range(20):
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-CimInstance Win32_Process -Filter \"Name='msedgewebview2.exe'\" | Where-Object { $_.CommandLine -like '*dev_tests*testdata*' }).Count"],
                           capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if r.stdout.strip() in ("", "0"):
            return
        time.sleep(0.5)


kill()
rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "filters", "user_rules.txt")
os.makedirs(os.path.dirname(rules_path), exist_ok=True)
if rules is None:
    if os.path.exists(rules_path):
        os.remove(rules_path)
else:
    open(rules_path, "w", encoding="utf-8").write(rules + "\n")

log = os.path.join(SCRATCH, f"req_{name}.log")
if os.path.exists(log):
    os.remove(log)
env = dict(os.environ, ADBLOCK_REMOTE_DEBUG_PORT="9333", ADBLOCK_REQUEST_LOG=log, ADBLOCK_HIDDEN_WINDOW="1", ADBLOCK_DATA_DIR=os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata"))
subprocess.Popen([sys.executable, "main.py", url], cwd=APP, env=env,
                 stdout=open(os.path.join(SCRATCH, f"app_{name}.log"), "w"), stderr=subprocess.STDOUT,
                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)

host = url.split("/")[2]
t0 = time.time()
while time.time() - t0 < 40:
    try:
        targets = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=2))
        if any(host in t["url"] for t in targets if t["type"] == "page"):
            break
    except Exception:
        pass
    time.sleep(1)
time.sleep(wait)

sys.argv = ["cdp", "x"]
from cdp import CDP
c = CDP()
expr = ("JSON.stringify({videos:[...document.querySelectorAll('video')].map(v=>({paused:v.paused,t:Math.round(v.currentTime),"
        "d:Math.round(v.duration),rs:v.readyState,err:v.error&&v.error.code})),"
        "werbung:/WERBUNG/.test(document.body.innerText)})")
r = c.call("Runtime.evaluate", expression=expr, returnByValue=True)
print(name, "->", r["result"].get("value"))
lines = open(log, encoding="utf-8").read().splitlines() if os.path.exists(log) else []
for k in ["mica.json", "dai.google.com", "ns-stream", "googlevideo", "orchestrator"]:
    hits = [l.split("\t")[0] for l in lines if k in l]
    if hits:
        print(f"   {k}: {len(hits)}x ({', '.join(sorted(set(hits)))})")
