# Claudius Vending Machine — Physical Build Guide

How to build the physical enclosure, wire all electronics, and connect the iPad + Raspberry Pi into a working AI vending machine.

---

## Table of Contents

1. [System Metrics (from Codebase)](#1-system-metrics-from-codebase)
2. [Skills You Need](#2-skills-you-need)
3. [Component Shopping List](#3-component-shopping-list)
4. [Enclosure / Cabinet](#4-enclosure--cabinet)
5. [Electronics Wiring](#5-electronics-wiring)
6. [iPad Integration](#6-ipad-integration)
7. [Raspberry Pi Setup](#7-raspberry-pi-setup)
8. [Assembly Steps](#8-assembly-steps)
9. [Testing & Commissioning](#9-testing--commissioning)

---

## 1. System Metrics (from Codebase)

These are the hard specs your physical build must satisfy, derived directly from the running code.

### GPIO Pin Map (BCM Numbering)

| BCM Pin | Component | Logic | Initial State |
|---------|-----------|-------|---------------|
| **17** | Door lock (electronic) | `active_high=False` — OFF = locked, ON = unlocked | Locked |
| **27** | Fridge relay | `active_high=True` — ON = fridge running | On |
| **22** | Status LED | `active_high=True` — ON = lit | On |

### Software Ports

| Service | Port | Protocol |
|---------|------|----------|
| FastAPI | `:8000` | HTTP + WebSocket |
| OpenClaw | `:18789` | HTTP (localhost only) |
| Nginx | `:80` | HTTP (iPad-facing) |

### iPad Connection

- Connects via **WiFi on same local network** as the Pi
- Resolves `http://claudius.local` via mDNS/Bonjour (built into iPad + Pi)
- WebSocket at `ws://claudius.local/ws/updates` for real-time stock pushes
- PWA (Progressive Web App) — add to home screen for full-screen kiosk mode

### Product Slot Scheme

The DB uses grid slots like `A1`, `A2`, `B1`, `B2` — design your shelf layout to match.

### Business Constraints (enforced by guardrails)

- Max single purchase: **$80**
- Pickup code: **6-character alphanumeric**
- Pickup window: **30 minutes** before auto-expiry

---

## 2. Skills You Need

### Essential

| Skill | Why | Can You Learn It? |
|-------|-----|-------------------|
| **Basic soldering** | Connect relay modules, LED, lock wires | Yes — YouTube "soldering for beginners" (1 hour) |
| **Wire crimping / terminal blocks** | Connect 12V lock, relay to Pi GPIO | Yes — pre-crimped jumper wires work too |
| **Linux command line** | SSH into Pi, run systemd services, edit configs | Yes — the CLAUDE.md covers all commands |
| **Networking basics** | Set up WiFi, static IP, mDNS | Yes — Pi and iPad auto-discover via Bonjour |

### Helpful But Not Required

| Skill | Why | Workaround |
|-------|-----|------------|
| Woodworking / metalworking | Custom enclosure | Buy a pre-made mini fridge or display case |
| 3D printing | Custom brackets, bezels | Use off-the-shelf mounting hardware |
| Python programming | Debug / extend the agent | The codebase is ready to run as-is |

---

## 3. Component Shopping List

### 3A. Raspberry Pi (Brain)

| Option | Model | RAM | Price (USD) | Pros | Cons |
|--------|-------|-----|-------------|------|------|
| **A (Recommended)** | Raspberry Pi 5 | 4GB | ~$60 | Fast, native PCIe, better thermals | Newer, slightly higher power draw |
| B | Raspberry Pi 5 | 8GB | ~$80 | Extra RAM for future features | Overkill for this project |
| C | Raspberry Pi 4 Model B | 4GB | ~$55 | Well-tested, huge community | Slower than Pi 5, harder to buy new |
| D | Raspberry Pi 4 Model B | 2GB | ~$45 | Cheapest viable option | Tight on memory if running all services |

**Also required for Pi:**

| Item | Price | Notes |
|------|-------|-------|
| microSD card (32GB+, A2 rated) | ~$10 | SanDisk Extreme recommended |
| USB-C power supply (5V 4A for Pi 5 / 5V 3A for Pi 4) | ~$12 | Use official Pi PSU to avoid brownouts |
| Pi case with fan/heatsink | ~$10-15 | Active cooling recommended for 24/7 operation |
| Ethernet cable (optional) | ~$5 | More reliable than WiFi for production |

---

### 3B. iPad (Customer POS)

| Option | Model | Price (USD) | Pros | Cons |
|--------|-------|-------------|------|------|
| **A (Recommended)** | iPad 10th gen (10.9") | ~$350 new / ~$200 used | Large screen, USB-C, current model | Higher cost |
| B | iPad 9th gen (10.2") | ~$250 new / ~$150 used | Cheapest current iPad, Lightning | Older chip, Lightning port |
| C | iPad mini 6th gen (8.3") | ~$400 new / ~$250 used | Compact, good for tight spaces | Smaller screen |
| D | Any used iPad (2018+) | ~$100-150 used | Lowest cost | Older hardware, may slow down |

**Also required for iPad:**

| Item | Price | Notes |
|------|-------|-------|
| iPad wall/surface mount | ~$30-80 | VESA mount or adhesive enclosure |
| Lightning or USB-C charging cable (long, 6ft+) | ~$15 | Keep iPad charged 24/7 |
| Screen protector (tempered glass) | ~$10 | Public-facing = fingerprints and abuse |

---

### 3C. Door Lock (GPIO 17)

The code uses `active_high=False` — the lock engages when the GPIO signal is LOW (default), and releases when HIGH.

| Option | Type | Voltage | Price | Pros | Cons |
|--------|------|---------|-------|------|------|
| **A (Recommended)** | 12V electromagnetic lock (mini) | 12V DC | ~$15-25 | Strong hold (60-100kg), fail-secure, silent | Needs 12V supply + MOSFET/relay driver |
| B | 12V solenoid lock (push-pull) | 12V DC | ~$8-15 | Cheap, simple, audible "click" | Weaker hold, mechanical wear |
| C | 5V solenoid lock | 5V DC | ~$5-10 | Can run from Pi 5V (with relay) | Very weak hold force |
| D | Servo-driven latch (SG90 servo) | 5V | ~$3-5 | No relay needed, PWM from GPIO | Mechanical, noisy, not secure |

**Driver circuit required for options A & B:**

| Item | Price | Notes |
|------|-------|-------|
| MOSFET module (IRF520 or IRLZ44N) | ~$3-5 | Switches 12V from 3.3V GPIO signal |
| OR: 5V relay module (1-channel) | ~$3-5 | Simpler but bulkier, has audible click |
| 12V DC power supply (2A) | ~$8-12 | Powers the lock (shared with fridge if 12V) |
| Flyback diode (1N4007) | ~$0.10 | Protects MOSFET from lock's back-EMF — often built into modules |

---

### 3D. Fridge / Cooling Unit (GPIO 27)

The code controls a relay on GPIO 27 to power the fridge on/off. You need a relay module that can switch mains AC (or a 12V compressor).

| Option | Type | Price | Pros | Cons |
|--------|------|-------|------|------|
| **A (Recommended)** | Mini fridge (repurposed, 20-35L) | ~$50-100 | Already insulated, has compressor, just control the plug | Larger, heavier |
| B | Peltier cooler module (TEC1-12706) | ~$15-30 (with heatsinks + fan) | Compact, no moving parts, silent | Low cooling capacity, high power draw, unreliable for <15C |
| C | Thermoelectric wine cooler (repurposed) | ~$60-120 | Quiet, glass door for display | Limited temp range |
| D | No cooling — ambient shelf | $0 | Simplest build | Only works for non-perishable snacks |

**Relay module for fridge control:**

| Item | Price | Notes |
|------|-------|-------|
| **5V relay module (1 or 2 channel, with optocoupler)** | ~$3-5 | Switches mains AC to the fridge compressor |
| 10A relay module (if controlling mains) | ~$5-8 | Higher current rating for compressor motors |

> **Safety warning:** If switching mains AC (120V/240V), use a properly rated relay module with optocoupler isolation. Enclose all mains wiring. If you're not comfortable with mains wiring, use a smart plug (Zigbee/WiFi) controlled via the Pi instead.

**Smart plug alternative (no mains wiring):**

| Item | Price | Notes |
|------|-------|-------|
| Zigbee smart plug + Zigbee USB dongle | ~$25 total | Control via zigbee2mqtt on Pi |
| WiFi smart plug (Tapo/Kasa with local API) | ~$12 | Control via HTTP, no mains wiring |

---

### 3E. Status LED (GPIO 22)

| Option | Type | Price | Notes |
|--------|------|-------|-------|
| **A (Recommended)** | 5mm green LED + 330 ohm resistor | ~$0.50 | Simple, wire directly to GPIO 22 |
| B | LED strip (WS2812B NeoPixel, 8-pixel) | ~$5-8 | Addressable RGB, fancier status display |
| C | LED panel / indicator light (12V) | ~$3-5 | Industrial look, needs MOSFET driver |

**For option A (simplest):**
- 1x green LED (or any color)
- 1x 330-ohm resistor (for 3.3V GPIO)
- 2x jumper wires

---

### 3F. Camera Module (CSI — Optional)

Currently available but not actively used in the main flows. Good for future inventory verification.

| Option | Type | Price | Pros | Cons |
|--------|------|-------|------|------|
| **A (Recommended)** | Raspberry Pi Camera Module v3 | ~$25 | Autofocus, 12MP, official support | CSI ribbon cable routing |
| B | Raspberry Pi Camera Module v2 | ~$20 | 8MP, well-tested, code uses picamera2 | Fixed focus |
| C | USB webcam (Logitech C270) | ~$20 | Easy mounting, no ribbon cable | Needs code change (OpenCV instead of picamera2) |
| D | Skip camera for now | $0 | Camera code is optional | No inventory verification |

**Note:** If using Pi Camera, you need a **CSI ribbon cable** (15-pin, comes with the camera module). Pi 5 uses a smaller connector — buy the correct cable or an adapter.

---

### 3G. NFC Reader (USB — Optional / Future)

Code has stub implementation. Not required for the current pickup-code workflow.

| Option | Type | Price | Pros | Cons |
|--------|------|-------|------|------|
| A | ACR122U USB NFC reader | ~$25-35 | Well-supported, plug-and-play USB | Desktop form factor |
| B | PN532 NFC module (I2C/SPI/UART) | ~$8-15 | Compact, embeddable, flexible protocol | Requires wiring and soldering |
| C | Skip NFC for now | $0 | Pickup codes work via iPad | No tap-to-pay |

---

### 3H. Networking

| Item | Price | Notes |
|------|-------|-------|
| WiFi router (or use existing home WiFi) | $0-50 | Pi and iPad must be on same LAN |
| **OR** Pi as WiFi hotspot | $0 | Use `hostapd` — iPad connects directly to Pi |
| Ethernet cable + USB-C Ethernet adapter for iPad (optional) | ~$20 | More reliable than WiFi |

**Recommended:** Use your existing WiFi network. Both Pi and iPad connect to it. mDNS (`claudius.local`) handles discovery automatically.

---

### 3I. Power Distribution

| Item | Price | Notes |
|------|-------|-------|
| 12V DC power supply (5A) | ~$12-15 | Powers lock + fridge relay (if 12V) |
| 5V USB-C supply for Pi | ~$12 | Official Pi PSU |
| Power strip / surge protector | ~$10 | Central power for everything |
| Buck converter 12V → 5V (optional) | ~$3-5 | Run Pi from single 12V supply |

---

### Total Cost Estimate

| Build Level | Components | Estimated Cost |
|-------------|-----------|----------------|
| **Minimal** (shelf, no cooling, used iPad) | Pi 5 + used iPad + solenoid lock + LED + wiring | **~$250-300** |
| **Standard** (mini fridge, new iPad) | Pi 5 + iPad 10 + mini fridge + EM lock + camera + LED | **~$500-600** |
| **Full featured** (everything) | Standard + NFC reader + LED strip + Ethernet + UPS | **~$650-800** |

---

## 4. Enclosure / Cabinet

### Option A: Repurposed Mini Fridge (Recommended)

Best bang for the buck — you get insulation, a compressor, shelving, and a door with a seal.

1. Buy a 20-35L countertop mini fridge ($50-100)
2. Remove the stock door latch mechanism
3. Mount the electronic lock in its place
4. Cut a slot in the top/side for the iPad mount
5. Route Pi + wiring through the back (drill a cable pass-through)

### Option B: Custom Wooden Cabinet

If you want a traditional vending-machine look:

- **Material:** 12mm plywood or MDF
- **Suggested dimensions:** 600mm W x 400mm D x 800mm H (countertop size)
- **Shelves:** Adjustable, matching your slot scheme (A-row top, B-row bottom, etc.)
- **Door:** Hinged with piano hinge, transparent acrylic panel for product visibility
- **Tools needed:** Drill, jigsaw, sandpaper, wood screws, hinges

### Option C: Acrylic Display Case

- Buy a lockable acrylic display case (~$40-80 on Amazon)
- Replace the stock lock with an electronic lock
- Good for snacks/non-perishable items
- Transparent = customers can see products

### Option D: 3D-Printed Enclosure (Small Scale)

- For a desk-sized demo unit holding 4-6 items
- Print panels and brackets on a standard FDM printer
- Good for presentations/demos, not production use

---

## 5. Electronics Wiring

### Wiring Diagram

```
                    Raspberry Pi 5 / 4
                   ┌──────────────────────┐
                   │                      │
                   │  GPIO 17 ────────────┼──► MOSFET/Relay Module ──► 12V Door Lock
                   │                      │         │
                   │  GPIO 27 ────────────┼──► Relay Module (AC) ──► Fridge Compressor Plug
                   │                      │
                   │  GPIO 22 ────────────┼──► 330Ω Resistor ──► LED ──► GND
                   │                      │
                   │  GND (Pin 6/14/etc) ─┼──► Common ground for all modules
                   │                      │
                   │  CSI Port ───────────┼──► Pi Camera (ribbon cable)
                   │                      │
                   │  USB-A ──────────────┼──► (Future: NFC reader)
                   │                      │
                   │  WiFi ───────────────┼──► Local network ──► iPad
                   │                      │
                   └──────────────────────┘
                          │
                    5V USB-C Power Supply
```

### Door Lock Circuit (GPIO 17 → 12V Lock)

Using a MOSFET module (recommended):

```
GPIO 17 (3.3V) ──► MOSFET Module SIG pin
Pi GND ──────────► MOSFET Module GND
12V Supply (+) ──► MOSFET Module V+
12V Supply (+) ──► Lock wire 1
MOSFET Module OUT ► Lock wire 2

(Flyback diode across lock terminals — usually built into the module)
```

Using a 5V relay module:

```
GPIO 17 (3.3V) ──► Relay IN
Pi 5V  ──────────► Relay VCC
Pi GND ──────────► Relay GND
12V Supply ──────► Relay COM
Lock ────────────► Relay NO (normally open — lock energizes when GPIO goes HIGH)
```

### Fridge Relay Circuit (GPIO 27 → Mains)

```
GPIO 27 (3.3V) ──► Relay Module IN
Pi 5V  ──────────► Relay Module VCC
Pi GND ──────────► Relay Module GND
Mains Live ──────► Relay COM
Fridge Plug Live ► Relay NO

(Neutral and Earth pass through directly — only switch Live)
```

> **Mains AC safety:** Use a relay rated for your voltage (120V/240V) and current (10A minimum for a fridge compressor). Fully enclose all mains connections. If unsure, use a WiFi smart plug instead.

### Status LED (GPIO 22)

```
GPIO 22 ──► 330Ω resistor ──► LED anode (+, longer leg)
                                LED cathode (-, shorter leg) ──► Pi GND
```

---

## 6. iPad Integration

### Physical Mounting

| Mount Type | Product Examples | Price | Best For |
|------------|-----------------|-------|----------|
| **Wall/surface mount (recommended)** | Loxone iPad mount, TabletWall | ~$30-50 | Flush-mounted on fridge/cabinet front |
| VESA arm + iPad adapter | RAM Mount + iPad holder | ~$40-60 | Adjustable angle |
| 3D-printed bezel | Custom STL | ~$5 filament | Exact fit to your enclosure |
| Adhesive tablet holder | Velcro Command strips | ~$5 | Quick and dirty, removable |

### Software Configuration

1. **Connect iPad to same WiFi** as the Raspberry Pi
2. Open Safari, navigate to `http://claudius.local`
3. **Add to Home Screen** (Share → Add to Home Screen) — this makes it a PWA running in full-screen kiosk mode
4. Enable **Guided Access** (Settings → Accessibility → Guided Access) to lock the iPad into the Claudius app
   - Triple-click home/side button to start Guided Access
   - Disable hardware buttons, touch areas outside the app
5. **Keep screen always on:** Settings → Display & Brightness → Auto-Lock → Never
6. **Keep charging:** Plug in a charging cable routed through the enclosure

### Network Setup

The Pi runs Nginx on port 80 serving the React PWA. The iPad connects to `claudius.local` which resolves via mDNS (Avahi/Bonjour — built into both Pi OS and iPad).

If mDNS doesn't work on your network:
- Set a **static IP** on the Pi (e.g., `192.168.1.100`)
- Use `http://192.168.1.100` on the iPad instead

---

## 7. Raspberry Pi Setup

### OS Installation

1. Download **Raspberry Pi OS (64-bit, Lite)** — no desktop needed
2. Flash to microSD with **Raspberry Pi Imager**
3. In Imager settings, configure:
   - Hostname: `claudius`
   - WiFi credentials
   - SSH enabled
   - Username: `pi`

### Software Installation

```bash
# SSH into Pi
ssh pi@claudius.local

# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv nginx git

# Clone project
git clone <your-repo-url> /home/pi/claudius-vend
cd /home/pi/claudius-vend

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gpiozero picamera2  # Pi-only hardware libraries

# Initialize database
python db/init_db.py
python scripts/seed_products.py

# Install Nginx config
sudo cp config/nginx.conf /etc/nginx/sites-available/claudius
sudo ln -s /etc/nginx/sites-available/claudius /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# Install systemd services
sudo cp config/claudius.service /etc/systemd/system/
sudo cp config/openclaw.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable claudius openclaw nginx
sudo systemctl start claudius openclaw

# Build frontend (on dev machine, then copy dist/)
# OR install Node.js on Pi:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
cd /home/pi/claudius-vend/frontend
npm install && npm run build
```

### Environment Variables

Create `/home/pi/claudius-vend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
WEBHOOK_SECRET=your-secret-here
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
DATABASE_URL=sqlite+aiosqlite:///./claudius.db
ENVIRONMENT=production
LOG_LEVEL=INFO
```

---

## 8. Assembly Steps

### Phase 1: Electronics (on workbench)

1. **Test the Pi** — boot it up, SSH in, verify software runs
2. **Wire the LED** — GPIO 22 → resistor → LED → GND. Run the mock test to verify
3. **Wire the door lock** — GPIO 17 → MOSFET/relay → lock. Test with:
   ```python
   from gpiozero import OutputDevice
   lock = OutputDevice(17, active_high=False)
   lock.on()   # should unlock
   lock.off()  # should lock
   ```
4. **Wire the fridge relay** — GPIO 27 → relay → fridge power. Test on/off
5. **Test all hardware together** — run the FastAPI server, use the admin API to trigger unlock

### Phase 2: Enclosure

6. **Prepare the cabinet/fridge** — clean, add shelves, label slots (A1, A2, B1, etc.)
7. **Mount the electronic lock** — on the door frame, aligned with the door
8. **Drill cable pass-throughs** — for power cables, Pi connections
9. **Mount the Pi** — inside the enclosure (back wall or top), use standoffs or a case
10. **Mount the iPad** — on the front face, at comfortable interaction height (~120-140cm from floor)
11. **Route all cables** — use cable ties, keep away from shelves/products

### Phase 3: Integration

12. **Connect everything** — Pi → lock, relay, LED, camera, power
13. **Boot the system** — `sudo systemctl start claudius`
14. **Open iPad PWA** — navigate to `http://claudius.local`, add to home screen
15. **Test the full flow:**
    - Browse products on iPad
    - Checkout on iPad → verify stock decrements
    - Send a Slack message → verify agent responds
    - Order via Slack → get pickup code → enter on iPad → door unlocks
16. **Enable Guided Access** on iPad for kiosk mode

---

## 9. Testing & Commissioning

### Checklist

| Test | Command / Action | Expected Result |
|------|-----------------|-----------------|
| Pi boots and connects to WiFi | `ping claudius.local` | Reply from Pi IP |
| FastAPI is running | `curl http://claudius.local/api/status` | `{"status": "ok"}` |
| iPad loads PWA | Open `http://claudius.local` on iPad | Product catalog displays |
| WebSocket works | Change a price via agent → check iPad | Price updates in real-time |
| Door lock unlocks | Agent tool `unlock_door` or admin API | Lock releases, LED/log confirms |
| Door lock re-locks | Wait for auto-lock timeout | Lock engages |
| Fridge relay toggles | Agent tool or admin API | Fridge compressor starts/stops |
| Status LED responds | Toggle via GPIO test script | LED turns on/off |
| Slack → Agent → Slack | @mention bot in #claudius | Agent responds with product info |
| Pickup flow end-to-end | Order via Slack → code → iPad → door | Full cycle completes |
| Guardrails block | Try to buy >$80 via agent | Agent reports blocked |

### Troubleshooting

| Problem | Check |
|---------|-------|
| iPad can't reach `claudius.local` | Same WiFi? Try Pi's IP directly. Check `avahi-daemon` is running on Pi |
| Door lock doesn't release | Multimeter on MOSFET/relay output. Check 12V supply. Check GPIO 17 waveform |
| Fridge relay clicks but fridge doesn't start | Check relay NO/NC wiring. Verify compressor draws < relay current rating |
| Agent doesn't respond to Slack | Check OpenClaw logs: `journalctl -u openclaw -f`. Verify tokens in `.env` |
| WebSocket disconnects | Check Nginx config has `proxy_http_version 1.1` and `Upgrade` headers |

---

## Quick Reference: Pin Summary

```
Raspberry Pi GPIO Header (relevant pins only)
──────────────────────────────
Pin 1  (3.3V)     Pin 2  (5V)
...
Pin 11 (GPIO 17) ← DOOR LOCK
Pin 13 (GPIO 27) ← FRIDGE RELAY
Pin 15 (GPIO 22) ← STATUS LED
...
Pin 6  (GND)     ← Common ground
Pin 14 (GND)     ← Common ground
Pin 9  (GND)     ← Common ground
──────────────────────────────
```

> **Physical pin numbers ≠ BCM numbers.** The code uses BCM numbering. GPIO 17 is physical pin 11, GPIO 27 is physical pin 13, GPIO 22 is physical pin 15. Always double-check with `pinout` command on the Pi.
