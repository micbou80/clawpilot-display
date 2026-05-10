#!/usr/bin/env python3
"""Red Pro V1 — Dashboard for Waveshare 3.5" SPI (480x320)
Polls bridge on Michel's PC for display state.

Layout (matching v3 concept render):
  TOP ROW: time · date · weather · battery
  ─────────────────────────────────────────
  LEFT (160px)          │ RIGHT (300px)
  Scenario header       │ Next meeting title (bold)
  Big countdown / note  │ Time + badge
  "until start"         │ ─────────────────
                        │ PREPARE header (orange)
  [emoji centered]      │ Prep note in card bg
                        │ ─────────────────
                        │ TODAY calendar strip
"""
import time, struct, os, sys, json, subprocess as sp
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sp.check_call(["sudo", "apt", "install", "-y", "python3-pil"])
    from PIL import Image, ImageDraw, ImageFont

try:
    from urllib.request import urlopen, Request
except:
    pass

BRIDGE_BASE = "http://192.168.1.155:8889"
BRIDGE = BRIDGE_BASE + "/status"
FB = "/dev/fb1"
W, H = 480, 320

# Read BPP
BPP = 16
try:
    with open(f"/sys/class/graphics/{os.path.basename(FB)}/bits_per_pixel") as f:
        BPP = int(f.read().strip())
except:
    pass

# Fonts
def ff(names, size):
    for n in names:
        if os.path.exists(n):
            return ImageFont.truetype(n, size)
    return ImageFont.load_default()

BOLD = ["/usr/share/fonts/truetype/inter/Inter-SemiBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
REG  = ["/usr/share/fonts/truetype/inter/Inter-Medium.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
LIGHT = ["/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf"]

f_sbar      = ff(REG, 14)       # status bar
f_sbar_bold = ff(BOLD, 14)      # status bar bold (time)
f_hdr       = ff(BOLD, 15)      # section headers (ALL CLEAR, UPCOMING MEETING)
f_countdown = ff(LIGHT, 44)     # big countdown "4m 39s"
f_sublabel  = ff(REG, 13)       # "until start"
f_meet_title= ff(BOLD, 18)      # meeting title "1:1 with Chris"
f_meet_info = ff(REG, 13)       # time + badge "14:31 - 15:01  Teams"
f_prep_body = ff(REG, 14)       # prep body text
f_cal_time  = ff(REG, 13)       # calendar time
f_cal_title = ff(REG, 13)       # calendar title
f_cal_until = ff(REG, 12)       # calendar "until" label
f_tiny      = ff(REG, 12)       # tiny labels
f_note_title= ff(BOLD, 14)      # notification title
f_note_body = ff(REG, 13)       # left pane body text
f_indicator = ff(BOLD, 32)      # big indicator letter/symbol

# Colors
BG      = (10, 10, 15)
CARD_BG = (20, 20, 26)
CARD_BD = (35, 35, 42)
WHITE   = (224, 224, 224)
DIM     = (140, 140, 140)
MUTED   = (100, 100, 100)
DARK    = (68, 68, 68)
ACCENT  = (232, 124, 62)
ACCENT2 = (224, 90, 58)
GREEN   = (74, 222, 128)
BLUE    = (91, 155, 213)
RED_C   = (248, 113, 113)
GOLD    = (251, 191, 36)
CYAN    = (103, 232, 249)
PURPLE  = (123, 104, 238)
LINE    = (30, 30, 38)

def poll_and_exec_cmd():
    """Poll bridge for commands, execute, post result back"""
    try:
        resp = urlopen(f"{BRIDGE_BASE}/cmd", timeout=3)
        data = json.loads(resp.read())
        cmd = data.get("cmd")
        if cmd:
            print(f"[CMD] Executing: {cmd}")
            try:
                result = sp.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                payload = json.dumps({
                    "cmd": cmd,
                    "stdout": result.stdout[-2000:] if result.stdout else "",
                    "stderr": result.stderr[-2000:] if result.stderr else "",
                    "returncode": result.returncode
                }).encode()
            except sp.TimeoutExpired:
                payload = json.dumps({"cmd": cmd, "stdout": "", "stderr": "TIMEOUT", "returncode": -1}).encode()
            req = Request(f"{BRIDGE_BASE}/cmd_result", data=payload,
                         headers={"Content-Type": "application/json"})
            urlopen(req, timeout=5)
    except:
        pass

# Layout constants
LEFT_X   = 14
COL_DIV  = 190
RIGHT_X  = 210
SBAR_H   = 40
LEFT_W   = COL_DIV - LEFT_X - 8   # max text width in left column
RIGHT_W  = W - RIGHT_X - 14       # max text width in right column

def fetch_state():
    try:
        resp = urlopen(BRIDGE, timeout=3)
        return json.loads(resp.read())
    except:
        return None

def wrap_text(draw, text, font, max_w, max_lines=3):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        bb = draw.textbbox((0,0), test, font=font)
        if bb[2] - bb[0] > max_w:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
        if len(lines) >= max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines

def draw_rounded_rect(draw, xy, radius, fill=None, outline=None):
    x0, y0, x1, y1 = xy
    r = radius
    if fill:
        draw.rectangle((x0+r, y0, x1-r, y1), fill=fill)
        draw.rectangle((x0, y0+r, x1, y1-r), fill=fill)
        draw.pieslice((x0, y0, x0+2*r, y0+2*r), 180, 270, fill=fill)
        draw.pieslice((x1-2*r, y0, x1, y0+2*r), 270, 360, fill=fill)
        draw.pieslice((x0, y1-2*r, x0+2*r, y1), 90, 180, fill=fill)
        draw.pieslice((x1-2*r, y1-2*r, x1, y1), 0, 90, fill=fill)
    if outline:
        draw.arc((x0, y0, x0+2*r, y0+2*r), 180, 270, fill=outline)
        draw.arc((x1-2*r, y0, x1, y0+2*r), 270, 360, fill=outline)
        draw.arc((x0, y1-2*r, x0+2*r, y1), 90, 180, fill=outline)
        draw.arc((x1-2*r, y1-2*r, x1, y1), 0, 90, fill=outline)
        draw.line((x0+r, y0, x1-r, y0), fill=outline)
        draw.line((x0+r, y1, x1-r, y1), fill=outline)
        draw.line((x0, y0+r, x0, y1-r), fill=outline)
        draw.line((x1, y0+r, x1, y1-r), fill=outline)

# ═══════════════════════════════════════
#  STATUS BAR (shared across all layouts)
# ═══════════════════════════════════════
def draw_sbar(draw, img, now, weather=None, battery=None):
    # Time (bold)
    draw.text((LEFT_X, 12), now.strftime("%H:%M"), fill=DIM, font=f_sbar_bold)
    # Dot separator
    draw.ellipse((60, 18, 64, 22), fill=MUTED)
    # Date
    draw.text((70, 12), now.strftime("%a, %b %-d"), fill=MUTED, font=f_sbar)

    # Weather — icon left, temp next to it, description below temp
    if weather and weather.get("temp"):
        icon_name = weather.get("icon", "")
        desc = weather.get("desc", "")
        wx_icon_path = f"/tmp/redpro_emoji/wx_{icon_name}.png"
        if icon_name and not os.path.exists(wx_icon_path):
            try:
                resp = urlopen(f"{BRIDGE_BASE}/weather/{icon_name}.png", timeout=5)
                with open(wx_icon_path, 'wb') as wf:
                    wf.write(resp.read())
            except:
                pass
        wx = W // 2 - 30
        # Icon
        if icon_name and os.path.exists(wx_icon_path):
            try:
                wx_img = Image.open(wx_icon_path).convert("RGB")
                wx_img = wx_img.resize((28, 28), Image.LANCZOS)
                img.paste(wx_img, (wx, 4))
            except Exception as e:
                with open("/tmp/redpro_wx_err.txt", "w") as ef:
                    ef.write(str(e))
        # Temp to the right of icon
        tx = wx + 32
        draw.text((tx, 4), weather['temp'], fill=DIM, font=f_sbar)
        # Description below temp
        if desc:
            draw.text((tx, 19), desc, fill=MUTED, font=f_tiny)

    # Power / Battery (right)
    # Check if PiSugar is connected by looking for battery level in state
    bx, by = W - 54, 13
    if battery is not None and battery >= 0 and battery <= 100:
        # PiSugar connected — show battery
        draw.rectangle((bx, by, bx+22, by+11), outline=MUTED, width=1)
        draw.rectangle((bx+22, by+3, bx+24, by+8), fill=MUTED)
        fill_w = int(20 * battery / 100)
        fill_c = GREEN if battery > 30 else GOLD if battery > 15 else RED_C
        if fill_w > 0:
            draw.rectangle((bx+1, by+1, bx+1+fill_w, by+10), fill=fill_c)
        pct = f"{battery}%"
        bb = draw.textbbox((0,0), pct, font=f_tiny)
        draw.text((bx - (bb[2]-bb[0]) - 4, by), pct, fill=MUTED, font=f_tiny)
    else:
        # No battery — show plug icon (AC power)
        draw.text((bx, by-1), "AC", fill=GREEN, font=f_tiny)
        # Small plug symbol
        draw.rectangle((bx+20, by+2, bx+24, by+9), fill=GREEN)
        draw.rectangle((bx+24, by+4, bx+26, by+7), fill=GREEN)

    # Separator
    draw.line([(0, SBAR_H), (W, SBAR_H)], fill=LINE, width=1)

# ═══════════════════════════════════════
#  CALENDAR STRIP (shared)
# ═══════════════════════════════════════
def draw_calendar_strip(draw, calendar, x, max_y, max_items=3):
    if not calendar:
        return
    items = calendar[:max_items]
    strip_h = len(items) * 22 + 22
    cal_y = max_y - strip_h

    draw.line([(x, cal_y), (W-16, cal_y)], fill=LINE, width=1)
    cal_y += 6
    draw.text((x, cal_y), "UPCOMING", fill=MUTED, font=f_hdr)
    cal_y += 20

    for ev in items:
        # Blue dot
        draw.ellipse((x, cal_y+5, x+6, cal_y+11), fill=BLUE)
        # Time (fixed width)
        time_str = ev.get("time","")
        draw.text((x+14, cal_y), time_str, fill=MUTED, font=f_cal_time)
        # Title (right after time with small gap)
        draw.text((x+56, cal_y), ev.get("title","")[:22], fill=DIM, font=f_cal_title)
        # "in Xh" right-aligned
        until = ev.get("until", "")
        if until:
            until_str = f"in {until}" if not until.startswith("in") else until
            bb = draw.textbbox((0,0), until_str, font=f_cal_until)
            draw.text((W - (bb[2]-bb[0]) - 16, cal_y+1), until_str, fill=MUTED, font=f_cal_until)
        cal_y += 22

# ═══════════════════════════════════════
#  SCENARIO CONFIGS
# ═══════════════════════════════════════
SCENARIOS = {
    "idle":     {"hdr": "ALL CLEAR",         "color": GREEN,  "note": "Nothing to do.\nEnjoy the quiet."},
    "meeting":  {"hdr": "UPCOMING MEETING",  "color": ACCENT, "note": ""},
    "email":    {"hdr": "EMAIL",             "color": ACCENT, "note": ""},
    "teams":    {"hdr": "TEAMS",             "color": PURPLE, "note": ""},
    "urgent":   {"hdr": "URGENT",            "color": RED_C,  "note": ""},
    "working":  {"hdr": "WORKING",           "color": CYAN,   "note": ""},
    "done":     {"hdr": "DONE",              "color": GREEN,  "note": ""},
    "input":    {"hdr": "INPUT NEEDED",      "color": GOLD,   "note": ""},
    "flight":   {"hdr": "FLIGHT",            "color": BLUE,   "note": ""},
    "hydrate":  {"hdr": "HYDRATE",           "color": BLUE,   "note": "Time for water."},
    "late":     {"hdr": "RUNNING LATE",      "color": RED_C,  "note": ""},
    "focus":    {"hdr": "FOCUS MODE",        "color": GREEN,  "note": "Notifications paused."},
    "celebration":{"hdr":"NICE!",            "color": GOLD,   "note": ""},
}

# ═══════════════════════════════════════
#  MAIN RENDER
# ═══════════════════════════════════════
def render(state):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    now = datetime.now()

    weather  = state.get("weather", {}) if state else {}
    scenario = state.get("type", "idle") if state else "idle"
    note     = state.get("body", "") if state else ""
    title    = state.get("title", "") if state else ""
    battery  = state.get("battery", None) if state else None
    calendar = state.get("calendar", []) if state else []
    meeting  = state.get("meeting", {}) if state else {}
    prep     = state.get("prep", []) if state else []
    countdown_sec = state.get("countdown_sec", 0) if state else 0

    sc = SCENARIOS.get(scenario, SCENARIOS["idle"])

    # ── Status bar ──
    draw_sbar(draw, img, now, weather, battery)

    # ── Vertical divider ──
    draw.line([(COL_DIV, SBAR_H + 6), (COL_DIV, H - 6)], fill=LINE, width=1)

    # ══════════════════════════════════
    #  LEFT COLUMN
    # ══════════════════════════════════
    ly = SBAR_H + 26

    # Section header — centered in left pane
    hdr_text = sc["hdr"]
    scenario_key = scenario if scenario in SCENARIOS else "idle"
    hdr_emoji_path = f"/tmp/redpro_emoji/{scenario_key}.png"
    hdr_icon_w = 0
    if os.path.exists(hdr_emoji_path):
        hdr_icon_w = 22
    # Measure total header width to center it
    hdr_bb = draw.textbbox((0,0), hdr_text, font=f_hdr)
    hdr_total_w = hdr_icon_w + (hdr_bb[2] - hdr_bb[0])
    hdr_x = LEFT_X + (COL_DIV - LEFT_X - hdr_total_w) // 2
    # Draw emoji icon
    if hdr_icon_w and os.path.exists(hdr_emoji_path):
        try:
            hdr_emoji = Image.open(hdr_emoji_path).convert("RGBA")
            hdr_emoji = hdr_emoji.resize((18, 18), Image.LANCZOS)
            bg_patch = Image.new("RGBA", hdr_emoji.size, BG + (255,))
            composited = Image.alpha_composite(bg_patch, hdr_emoji).convert("RGB")
            img.paste(composited, (hdr_x, ly + 1))
        except:
            pass
    draw.text((hdr_x + hdr_icon_w, ly), hdr_text, fill=sc["color"], font=f_hdr)
    ly += 24

    # Countdown or title
    left_center = LEFT_X + (COL_DIV - LEFT_X) // 2  # center X of left pane
    if scenario == "meeting" and countdown_sec > 0:
        mins = countdown_sec // 60
        secs = countdown_sec % 60
        cd_str = f"{mins}m {secs:02d}s"
        bb = draw.textbbox((0,0), cd_str, font=f_countdown)
        draw.text((left_center - (bb[2]-bb[0])//2, ly), cd_str, fill=ACCENT, font=f_countdown)
        ly += (bb[3] - bb[1]) + 4
        bb2 = draw.textbbox((0,0), "until start", font=f_sublabel)
        draw.text((left_center - (bb2[2]-bb2[0])//2, ly), "until start", fill=MUTED, font=f_sublabel)
        ly += 18
    elif title:
        # For notifications: show title centered
        for line in wrap_text(draw, title, f_note_title, LEFT_W, 2):
            bb = draw.textbbox((0,0), line, font=f_note_title)
            draw.text((left_center - (bb[2]-bb[0])//2, ly), line, fill=WHITE, font=f_note_title)
            ly += 18
        ly += 4
        # Note body centered
        note_text = note or sc["note"]
        if note_text:
            for raw_line in note_text.split("\\n")[:3]:
                for line in wrap_text(draw, raw_line, f_note_body, LEFT_W, 2):
                    if ly < 200:
                        bb = draw.textbbox((0,0), line, font=f_note_body)
                        draw.text((left_center - (bb[2]-bb[0])//2, ly), line, fill=DIM, font=f_note_body)
                        ly += 17
    else:
        # Idle: show note centered
        note_text = note or sc["note"]
        if note_text:
            for raw_line in note_text.split("\\n")[:3]:
                for line in wrap_text(draw, raw_line, f_note_body, LEFT_W, 2):
                    if ly < 200:
                        bb = draw.textbbox((0,0), line, font=f_note_body)
                        draw.text((left_center - (bb[2]-bb[0])//2, ly), line, fill=DIM, font=f_note_body)
                        ly += 17

    # Indicator: colored emoji image in left column
    scenario_key = scenario if scenario in SCENARIOS else "idle"
    emoji_path = f"/tmp/redpro_emoji/{scenario_key}.png"
    # Download emoji if missing
    if not os.path.exists(emoji_path):
        os.makedirs("/tmp/redpro_emoji", exist_ok=True)
        try:
            resp = urlopen(f"http://192.168.1.155:8889/emoji/{scenario_key}.png", timeout=5)
            with open(emoji_path, 'wb') as ef:
                ef.write(resp.read())
        except:
            pass
    # Paste emoji onto image
    if os.path.exists(emoji_path):
        try:
            emoji_img = Image.open(emoji_path).convert("RGBA")
            emoji_img = emoji_img.resize((110, 110), Image.LANCZOS)
            cx = LEFT_X + (COL_DIV - LEFT_X - 110) // 2
            cy = H - 160
            # Composite onto dark background
            bg_patch = Image.new("RGBA", emoji_img.size, BG + (255,))
            composited = Image.alpha_composite(bg_patch, emoji_img).convert("RGB")
            img.paste(composited, (cx, cy))
        except:
            pass

    # ══════════════════════════════════
    #  RIGHT COLUMN
    # ══════════════════════════════════
    ry = SBAR_H + 10

    if meeting and meeting.get("title"):
        # Meeting title (big bold)
        mt = meeting["title"][:28]
        draw.text((RIGHT_X, ry), mt, fill=WHITE, font=f_meet_title)
        ry += 24

        # Clock icon + time + Teams logo if applicable
        mtime = meeting.get("time", "")
        is_teams = meeting.get("badge", "").lower().find("teams") >= 0

        ix = RIGHT_X
        # Clock icon
        clock_path = "/tmp/redpro_emoji/clock.png"
        if not os.path.exists(clock_path):
            try:
                resp = urlopen(f"{BRIDGE_BASE}/emoji/clock.png", timeout=5)
                with open(clock_path, 'wb') as cf:
                    cf.write(resp.read())
            except:
                pass
        if os.path.exists(clock_path):
            try:
                clk = Image.open(clock_path).convert("RGB")
                clk = clk.resize((16, 16), Image.LANCZOS)
                img.paste(clk, (ix, ry + 1))
                ix += 20
            except:
                pass

        # Time text
        if mtime:
            draw.text((ix, ry), mtime, fill=MUTED, font=f_meet_info)
            bb = draw.textbbox((0,0), mtime, font=f_meet_info)
            ix += (bb[2] - bb[0]) + 12

        # Teams logo
        if is_teams:
            teams_path = "/tmp/redpro_emoji/teams_logo.png"
            if not os.path.exists(teams_path):
                try:
                    resp = urlopen(f"{BRIDGE_BASE}/emoji/teams_logo.png", timeout=5)
                    with open(teams_path, 'wb') as tf:
                        tf.write(resp.read())
                except:
                    pass
            if os.path.exists(teams_path):
                try:
                    tms = Image.open(teams_path).convert("RGB")
                    tms = tms.resize((16, 16), Image.LANCZOS)
                    img.paste(tms, (ix, ry + 1))
                    ix += 20
                except:
                    pass
            draw.text((ix, ry), "Teams", fill=MUTED, font=f_meet_info)

        ry += 22
        # Underline
        draw.line([(RIGHT_X, ry), (W-16, ry)], fill=LINE, width=1)
        ry += 8

    elif scenario in ("email", "teams", "urgent"):
        # Notification: show title and body on right
        if title:
            draw.text((RIGHT_X, ry), title[:28], fill=WHITE, font=f_meet_title)
            ry += 22
        if note:
            for line in wrap_text(draw, note, f_prep_body, RIGHT_W, 4):
                draw.text((RIGHT_X, ry), line, fill=DIM, font=f_prep_body)
                ry += 17
            ry += 4
    else:
        draw.text((RIGHT_X, ry), "No upcoming meetings", fill=MUTED, font=f_meet_info)
        ry += 22

    # Attendee summary (compact: "3 accepted · 1 pending")
    if meeting and meeting.get("attendees"):
        atts = meeting["attendees"]
        accepted = sum(1 for a in atts if a.get("status") == "accepted")
        pending = len(atts) - accepted
        parts = []
        if accepted:
            parts.append(f"{accepted} accepted")
        if pending:
            parts.append(f"{pending} pending")
        if parts:
            att_str = " · ".join(parts)
            draw.text((RIGHT_X, ry), att_str, fill=MUTED, font=f_tiny)
            ry += 18

    # Prep section
    if prep:
        ry += 6
        draw.line([(RIGHT_X, ry), (W-16, ry)], fill=LINE, width=1)
        ry += 10
        draw.text((RIGHT_X, ry), "PREPARE", fill=ACCENT2, font=f_hdr)
        ry += 18

        prep_text = " ".join(prep[:2])
        prep_lines = wrap_text(draw, prep_text, f_prep_body, RIGHT_W, 3)
        for line in prep_lines:
            draw.text((RIGHT_X, ry), line, fill=DIM, font=f_prep_body)
            ry += 18

    # Calendar strip at bottom
    draw_calendar_strip(draw, calendar, RIGHT_X, H - 10)

    # ── Bottom status ──
    online = state is not None and state.get("type")
    draw.ellipse((LEFT_X, H-14, LEFT_X+6, H-8), fill=GREEN if online else RED_C)
    draw.text((LEFT_X+10, H-16), f"v{VERSION}", fill=MUTED, font=f_tiny)

    return img

def write_fb(img):
    px = img.tobytes()
    if BPP == 16:
        buf = bytearray(W * H * 2)
        for i in range(W * H):
            r, g, b = px[i*3], px[i*3+1], px[i*3+2]
            struct.pack_into('<H', buf, i*2, ((r>>3)<<11)|((g>>2)<<5)|(b>>3))
    elif BPP == 32:
        buf = bytearray(W * H * 4)
        for i in range(W * H):
            buf[i*4]=px[i*3+2]; buf[i*4+1]=px[i*3+1]; buf[i*4+2]=px[i*3]; buf[i*4+3]=255
    else:
        buf = px
    with open(FB, 'wb') as f:
        f.write(buf)

SCRIPT_URL = "http://192.168.1.155:8889/redpro.py"
SCRIPT_PATH = os.path.abspath(__file__)
VERSION = "0.40"

def check_update():
    try:
        resp = urlopen(SCRIPT_URL, timeout=5)
        remote = resp.read()
        with open(SCRIPT_PATH, 'rb') as f:
            local = f.read()
        if remote != local:
            print("Update found! Downloading and restarting...")
            with open(SCRIPT_PATH, 'wb') as f:
                f.write(remote)
            os.execlp("sudo", "sudo", sys.executable, SCRIPT_PATH)
    except:
        pass

def download_emojis():
    """Pre-download all emoji PNGs on startup"""
    os.makedirs("/tmp/redpro_emoji", exist_ok=True)
    for key in SCENARIOS:
        path = f"/tmp/redpro_emoji/{key}.png"
        if not os.path.exists(path):
            try:
                resp = urlopen(f"http://192.168.1.155:8889/emoji/{key}.png", timeout=5)
                with open(path, 'wb') as f:
                    f.write(resp.read())
                print(f"  Downloaded emoji: {key}")
            except Exception as e:
                print(f"  Emoji {key} failed: {e}")

print(f"Red Pro V1 (v{VERSION}) on {FB} ({W}x{H} @ {BPP}bpp)")
print(f"Polling bridge: {BRIDGE}")
print(f"Auto-update from: {SCRIPT_URL}")
print("Checking for updates...")
check_update()
print("Downloading emoji assets...")
download_emojis()
print("Starting... Press Ctrl+C to stop")

last_state = None
last_minute = None
last_state_json = None
update_counter = 0
try:
    while True:
        now_min = datetime.now().strftime("%H:%M")
        state = fetch_state()
        if state is None:
            state = last_state or {}
        else:
            last_state = state

        state_json = json.dumps(state, sort_keys=True)
        if now_min != last_minute or state_json != last_state_json:
            img = render(state)
            write_fb(img)
            last_minute = now_min
            last_state_json = state_json

        # Poll for remote commands every cycle
        poll_and_exec_cmd()

        # Auto-update disabled — use remote shell to update manually
        # update_counter += 1
        # if update_counter >= 6:
        #     check_update()
        #     update_counter = 0

        time.sleep(5)
except KeyboardInterrupt:
    with open(FB, 'wb') as f:
        f.write(b'\x00' * (W * H * (BPP // 8)))
    print("\nRed Pro V1 stopped")
