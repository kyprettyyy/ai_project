"""Start/stop local Python and Node services on macOS/Linux.

Run from any directory: python3 scripts/local_dev.py start|status|stop.
Dependencies and .env files must already be configured. Database volumes are
preserved when stopping. Existing Windows scripts remain available.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
SERVICES = {
    "gateway": (ROOT / "services/gateway", [".venv/bin/python", "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", "8123"], "http://127.0.0.1:8123/api/health/"),
    "evaluation": (ROOT / "services/evaluation", [".venv/bin/python", "-m", "uvicorn", "app.main:app",
                   "--host", "127.0.0.1", "--port", "8124"], "http://127.0.0.1:8124/api/health/db"),
    "gateway-web": (ROOT / "web/gateway", ["npm", "run", "dev", "--", "--host", "127.0.0.1",
                    "--port", "5173", "--strictPort"], "http://127.0.0.1:5173/"),
    "evaluation-web": (ROOT / "web/evaluation", ["npm", "run", "dev", "--", "--host", "127.0.0.1",
                       "--port", "5174", "--strictPort"], "http://127.0.0.1:5174/"),
    "platform-web": (ROOT / "platform-web", [str(ROOT / "services/gateway/.venv/bin/python"), "-m",
                     "http.server", "5172", "--bind", "127.0.0.1"], "http://127.0.0.1:5172/"),
}


def docker_command() -> str:
    command = shutil.which("docker")
    bundled = Path("/Applications/Docker.app/Contents/Resources/bin/docker")
    if command:
        return command
    if bundled.exists():
        return str(bundled)
    raise RuntimeError("Docker CLI not found. Install and open Docker Desktop.")


def healthy(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            if url.endswith("/health/db"):
                return response.status == 200 and json.load(response).get("status") == "ok"
            return response.status == 200
    except Exception:
        return False


def start() -> None:
    for directory in (ROOT, ROOT / "services/gateway", ROOT / "services/evaluation"):
        if not (directory / ".env").exists():
            raise RuntimeError(f"Configure {directory / '.env'} first.")
    for service in ("gateway", "evaluation"):
        if not (SERVICES[service][0] / ".venv/bin/python").exists():
            raise RuntimeError(f"Install {service} Python dependencies first.")
    if not shutil.which("npm"):
        raise RuntimeError("npm not found. Install Node.js and reopen Terminal.")
    subprocess.run([docker_command(), "compose", "up", "-d", "--wait", "--wait-timeout", "120"],
                   cwd=ROOT, check=True)
    RUNTIME.mkdir(exist_ok=True)
    for name, (directory, args, url) in SERVICES.items():
        if healthy(url):
            print(f"{name}: already available at {url}", flush=True)
            continue
        log_path = RUNTIME / f"{name}.log"
        with log_path.open("ab") as log:
            process = subprocess.Popen(args, cwd=directory, stdout=log, stderr=log, start_new_session=True)
        # Save the exact expected command along with PID to avoid stopping a reused PID.
        (RUNTIME / f"{name}.process.json").write_text(json.dumps({"pid": process.pid, "args": args}))
        for _ in range(90):
            if healthy(url):
                print(f"{name}: ready at {url}", flush=True)
                break
            if process.poll() is not None:
                raise RuntimeError(f"{name} exited; inspect {log_path}.")
            time.sleep(1)
        else:
            raise RuntimeError(f"{name} did not become ready; inspect {log_path}.")
    print("Open http://127.0.0.1:5172/", flush=True)


def stop() -> None:
    for name in reversed(SERVICES):
        state_file = RUNTIME / f"{name}.process.json"
        if not state_file.exists():
            continue
        state = json.loads(state_file.read_text())
        pid = state["pid"]
        command = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True)
        expected = " ".join(state["args"][1:])
        # npm rewrites its process title and omits the argument separator.
        if state["args"][0] == "npm":
            expected = "npm run dev " + " ".join(state["args"][4:])
        if command.returncode == 0 and expected in command.stdout:
            os.killpg(pid, signal.SIGTERM)
            print(f"Stopped {name}")
            state_file.unlink()
        elif command.returncode != 0:
            state_file.unlink()
        else:
            print(f"Skipped {name}: PID no longer matches its saved command.")
    subprocess.run([docker_command(), "compose", "stop"], cwd=ROOT, check=True)


def status() -> None:
    for name, (_, _, url) in SERVICES.items():
        print(f"{name}: {'ready' if healthy(url) else 'not ready'} ({url})")
    subprocess.run([docker_command(), "compose", "ps"], cwd=ROOT, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    action = parser.parse_args().action
    {"start": start, "stop": stop, "status": status}[action]()
