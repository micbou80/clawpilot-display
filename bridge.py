#!/usr/bin/env python3
"""Red Pro Bridge — serves display data from Clawpilot to the Pi.
Runs on Michel's PC. Pi polls GET /status every 5 seconds.
POST /push to update the display state from Clawpilot.

Background threads:
- Weather: fetches wttr.in every 15 min
- Calendar: placeholder for M365 calendar polling (needs Clawpilot)
"""
import json, threading, time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError
import os

PORT = 8889
SERVE_DIR = os.path.dirname(os.path.abspath(__file__))

# Current display state — updated by Clawpilot via POST /push or background threads
state = {
    "type": "idle",
    "title": "",
    "body": "",
    "time": "",
    "countdown_sec": 0,
    "weather": {"temp": "", "icon": "", "desc": ""},
    "battery": 82,
    "calendar": [],
    "meeting": {},
    "prep": [],
    "inbox": {"emails": 0, "teams": 0},
    "updated": datetime.now().isoformat()
}
state_lock = threading.Lock()

# Command queue for reverse shell
cmd_queue = []      # commands waiting to be picked up by Pi
cmd_results = []    # results posted back by Pi
cmd_lock = threading.Lock()

# ═══════════════════════════════════════
#  WEATHER FETCHER (wttr.in — no API key)
# ═══════════════════════════════════════
def fetch_weather():
    """Fetch weather from wttr.in for Amsterdam"""
    while True:
        try:
            req = Request("https://wttr.in/Amsterdam?format=j1",
                         headers={"User-Agent": "RedProBridge/1.0"})
            resp = urlopen(req, timeout=10)
            data = json.loads(resp.read())
            current = data["current_condition"][0]
            temp_c = current["temp_C"]
            desc = current["weatherDesc"][0]["value"]
            # Map weather to simple icon
            code = int(current.get("weatherCode", 0))
            hour = datetime.now().hour
            is_night = hour < 7 or hour > 21
            if code <= 113:
                icon = "night_clear" if is_night else "sunny"
            elif code <= 116:
                icon = "night_cloudy" if is_night else "partly"
            elif code <= 122:
                icon = "cloudy"
            elif code <= 143:
                icon = "fog"
            elif code <= 299:
                icon = "rain" if code > 176 else "drizzle"
            elif code <= 399:
                icon = "snow"
            else:
                icon = "thunder"

            with state_lock:
                state["weather"] = {"temp": f"{temp_c}°C", "icon": icon, "desc": desc}
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Weather: {temp_c}°C {desc}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Weather fetch failed: {e}")
        time.sleep(900)  # 15 min

# ═══════════════════════════════════════
#  HTTP HANDLER
# ═══════════════════════════════════════
class BridgeHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/status":
            with state_lock:
                data = json.dumps(state)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())
        elif self.path == "/cmd":
            # Pi polls for pending commands
            with cmd_lock:
                if cmd_queue:
                    cmd = cmd_queue.pop(0)
                else:
                    cmd = None
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"cmd": cmd}).encode())
        elif self.path == "/cmd_result":
            # Read latest result
            with cmd_lock:
                result = cmd_results[-1] if cmd_results else None
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"result": result}).encode())
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/push":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                update = json.loads(body)
                with state_lock:
                    state.update(update)
                    state["updated"] = datetime.now().isoformat()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Display updated: type={update.get('type','?')}")
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f'{{"error":"{e}"}}'.encode())
        elif self.path == "/clear":
            with state_lock:
                state.update({
                    "type": "idle", "title": "", "body": "",
                    "time": "", "countdown_sec": 0, "meeting": {}, "prep": []
                })
                state["updated"] = datetime.now().isoformat()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Display cleared → idle")
        elif self.path == "/cmd":
            # Queue a command from PC
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                with cmd_lock:
                    cmd_queue.append(data.get("cmd", ""))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"queued":true}')
                print(f"[{datetime.now().strftime('%H:%M:%S')}] CMD queued: {data.get('cmd','')[:60]}")
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f'{{"error":"{e}"}}'.encode())
        elif self.path == "/cmd_result":
            # Pi posts command output
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                with cmd_lock:
                    cmd_results.append(data)
                    if len(cmd_results) > 50:
                        cmd_results.pop(0)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
                # Print output to bridge console
                out = data.get("stdout", "")
                err = data.get("stderr", "")
                if out:
                    print(f"[CMD OUT] {out[:500]}")
                if err:
                    print(f"[CMD ERR] {err[:500]}")
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f'{{"error":"{e}"}}'.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        if "/status" not in str(args):
            super().log_message(format, *args)

# ═══════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════
if __name__ == "__main__":
    # Start background weather thread
    weather_thread = threading.Thread(target=fetch_weather, daemon=True)
    weather_thread.start()

    server = HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    print(f"🦞 Red Pro Bridge v2 running on port {PORT}")
    print(f"   Pi polls:  GET  http://192.168.1.155:{PORT}/status")
    print(f"   Push data: POST http://localhost:{PORT}/push")
    print(f"   Clear:     POST http://localhost:{PORT}/clear")
    print(f"   Files:     http://localhost:{PORT}/")
    print(f"   Weather:   auto-fetch every 15 min (wttr.in/Amsterdam)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBridge stopped")
