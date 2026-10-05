"""Hidden instance with the USER'S profile (permission given) for the Netflix test."""
import os, subprocess, sys, time
from features_test_lib import APP, SCRATCH, PORT, pages, Page, wait_for, ps

USER_DATA = os.path.join(APP, "browser_data")


def start(url, name):
    log = os.path.join(SCRATCH, f"req_{name}.log")
    if os.path.exists(log):
        os.remove(log)
    env = dict(os.environ, ADBLOCK_REMOTE_DEBUG_PORT=str(PORT), ADBLOCK_HIDDEN_WINDOW="1",
               ADBLOCK_REQUEST_LOG=log, ADBLOCK_DATA_DIR=USER_DATA)
    proc = subprocess.Popen([sys.executable, "main.py", url], cwd=APP, env=env,
                            stdout=open(os.path.join(SCRATCH, f"app_{name}.log"), "w"), stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
    open(os.path.join(SCRATCH, "nf_pid.txt"), "w").write(str(proc.pid))
    return log


def stop():
    try:
        pid = int(open(os.path.join(SCRATCH, "nf_pid.txt")).read())
        ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")
    except Exception:
        pass
