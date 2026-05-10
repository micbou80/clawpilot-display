# Setup Guide

## Prerequisites

- Raspberry Pi Zero 2 W (with headers)
- Waveshare 3.5" SPI IPS Display (480×320)
- microSD card (16GB+) with Raspberry Pi OS Trixie Lite (64-bit)
- WiFi network
- PC running Clawpilot

## Step 1: Flash the SD Card

Use Raspberry Pi Imager to flash **Debian Trixie Lite (64-bit)** with:
- Hostname: `redprov1`
- Username/password configured
- WiFi configured
- SSH enabled

## Step 2: Display Overlay

Copy `waveshare35a.dtbo` to the boot partition overlays folder, then edit boot config:

**`/boot/firmware/config.txt`**:
```ini
dtparam=spi=on
dtoverlay=waveshare35a

# Comment out or remove:
# dtoverlay=vc4-kms-v3d

[all]
hdmi_force_hotplug=1
hdmi_cvt=480 320 60 6 0 0 0
hdmi_group=2
hdmi_mode=87
```

**`/boot/firmware/cmdline.txt`** — append:
```
fbcon=map:10
```

## Step 3: Install Dependencies

```bash
sudo apt update && sudo apt install -y python3-pil
```

## Step 4: Install Fonts

```bash
sudo mkdir -p /usr/share/fonts/truetype/inter
# Copy Inter-Medium.ttf, Inter-Regular.ttf, Inter-SemiBold.ttf
```

## Step 5: Install the Renderer

```bash
wget -O ~/redpro.py http://<PC_IP>:8889/redpro.py
```

## Step 6: Create systemd Service

```bash
sudo cat > /etc/systemd/system/redpro.service << 'EOF'
[Unit]
Description=Red Pro V1 Display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/michel
ExecStartPre=/bin/bash -c "echo 0 > /sys/class/vtconsole/vtcon1/bind"
ExecStart=/usr/bin/python3 /home/michel/redpro.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable redpro
sudo systemctl start redpro
```

## Step 7: Start the Bridge (PC)

```bash
cd clawpilot-display
python bridge.py
```

The bridge runs on port 8889 and:
- Serves display state at `GET /status`
- Accepts state updates at `POST /push`
- Serves files (renderer, icons, fonts)
- Fetches weather from wttr.in every 15 minutes
- Provides remote shell via `/cmd` endpoints

### Auto-start on PC Login

Place a shortcut to `start-bridge.bat` in your Windows startup folder:
```
shell:startup
```

## Step 8: Configure Clawpilot Automation

Create a scheduled automation in Clawpilot that runs every 5 minutes to sync M365 data to the bridge. See the automation prompt in [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Troubleshooting

### Display shows console text instead of UI
```bash
sudo bash -c "echo 0 > /sys/class/vtconsole/vtcon1/bind"
```

### Display is blank
Check framebuffer: `ls /dev/fb*` — the Waveshare should be `/dev/fb1`.

### Script crashes on startup
Check logs: `journalctl -u redpro --no-pager -n 30`

### Can't SSH from PC
If using a Microsoft corporate device, MDE/SenseNdr blocks SSH protocol traffic via deep packet inspection. Use the HTTP remote shell instead:
```powershell
$body = '{"cmd": "your command here"}'
Invoke-RestMethod -Uri "http://<PI_IP>:8889/cmd" -Method POST -Body $body -ContentType "application/json"
```

### Weather icon not showing
Delete cached icons and restart:
```bash
rm -f /tmp/redpro_emoji/wx_*
sudo systemctl restart redpro
```
