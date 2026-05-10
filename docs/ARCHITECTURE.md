# Architecture

## Overview

Clawpilot Display follows a strict **dumb terminal** architecture. The Pi has zero intelligence — it renders whatever the bridge tells it to. All AI reasoning, M365 integration, and data processing happens on the PC inside Clawpilot.

## Components

### Bridge (`bridge.py`)

The bridge is a Python HTTP server running on the user's PC at port 8889. It serves four roles:

1. **State server** (`GET /status`) — Returns the current display state as JSON. The Pi polls this every 5 seconds.

2. **Push endpoint** (`POST /push`) — Accepts JSON payloads from Clawpilot automations to update the display state. Fields: `type`, `title`, `body`, `countdown_sec`, `meeting`, `prep`, `calendar`, `battery`, `weather`.

3. **File server** — Serves static files (the renderer script, emoji PNGs, weather icons, fonts) so the Pi can self-update and download assets.

4. **Remote shell** (`POST /cmd`, `GET /cmd`, `POST /cmd_result`) — A command queue that enables full terminal access to the Pi over HTTP, bypassing SSH protocol blocks from endpoint protection software.

5. **Weather fetcher** — Background thread that polls [wttr.in](https://wttr.in) every 15 minutes for current weather conditions.

### Renderer (`redpro.py`)

The renderer runs on the Pi as a systemd service. Its lifecycle:

1. **Startup** — Check bridge for script updates (self-healing)
2. **Download assets** — Fetch any missing emoji/weather PNGs
3. **Main loop** (every 5 seconds):
   - Poll `GET /status` for current state
   - Poll `GET /cmd` for pending shell commands, execute if any
   - Render the display only if state changed or minute changed
   - Write RGB565 pixel data directly to `/dev/fb1`

### Display State JSON

```json
{
  "type": "idle|meeting|email|teams|urgent|working|done|flight|...",
  "title": "Notification title",
  "body": "Body text for left pane",
  "countdown_sec": 279,
  "weather": {"temp": "14°C", "icon": "cloudy", "desc": "Overcast"},
  "battery": null,
  "meeting": {
    "title": "1:1 with Chris",
    "time": "14:31 - 15:01",
    "badge": "Teams",
    "attendees": [
      {"name": "Chris Luce", "status": "accepted"}
    ]
  },
  "prep": ["Review budget doc before meeting."],
  "calendar": [
    {"time": "10:00", "title": "AIPW Weekly", "until": "in 2h"},
    {"time": "10:30", "title": "Dream Teams", "until": "in 3h"}
  ]
}
```

### Clawpilot Automation

A scheduled automation ("Red Pro Display Sync") runs every 5 minutes:

1. Pulls calendar events from Microsoft 365 via Graph API
2. Filters out all-day events, past events, cancelled meetings
3. Identifies the next upcoming meeting
4. Generates prep notes from recent communications with attendees
5. Formats and POSTs the state to the bridge

Additional push events happen in real-time when Clawpilot's heartbeat detects:
- VIP emails requiring action
- Teams mentions or DMs
- Agent task start/complete/error states

## Framebuffer Rendering

The Waveshare 3.5" SPI display uses the `fbtft` kernel driver and appears as `/dev/fb1`. The renderer:

1. Creates a 480×320 RGB PIL Image
2. Draws all UI elements (text, icons, lines, shapes)
3. Converts to RGB565 (16-bit) format
4. Writes the raw bytes to `/dev/fb1`

The pixel format is little-endian RGB565:
```python
rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
```

To prevent flicker, the display only redraws when the rendered pixels actually change.

## Self-Update Mechanism

On startup, the renderer checks the bridge for a newer version of itself:

```python
def check_update():
    remote = urlopen(SCRIPT_URL).read()
    with open(SCRIPT_PATH, 'rb') as f:
        local = f.read()
    if remote != local:
        # Download and restart
        with open(SCRIPT_PATH, 'wb') as f:
            f.write(remote)
        os.execlp("sudo", "sudo", sys.executable, SCRIPT_PATH)
```

Combined with systemd's `Restart=always`, this creates a self-healing system: even if a bad version is deployed, the next restart will fetch the fix from the bridge.

## Network Topology

```
PC (192.168.1.155)          Pi (192.168.1.213)
├── Wired Ethernet          ├── WiFi (Homi.io)
├── bridge.py :8889         ├── redpro.py
└── Clawpilot               └── /dev/fb1

Both on 192.168.1.0/24 via UniFi UDM Pro
SSH blocked by MDE → HTTP command queue instead
```
