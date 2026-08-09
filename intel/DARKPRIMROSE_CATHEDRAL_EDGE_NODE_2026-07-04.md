# Project Darkprimrose — Cathedral Edge Node

**Date:** July 4, 2026
**Hardware:** Orange Pi 4 Pro (RK3399, 4GB, aarch64)
**Software:** Kimi Code v0.22.x in server mode + Phoenix infra
**Concept:** Mobile cyberdeck + agent command center + hardware lab

---

## Architecture

```
[Phone] ─┬─ Tailscale ──┐
[Laptop] ─┤             ├──→ darkprimrose:9876 ──→ darkphoenix:9802 ──→ Providers
[CLI]   ─┘             │         │
                        │    kimi server run
                        │    --dangerous-bypass-auth
                        │    --keep-alive
                        │
                        ├─ Hardware (GPIO, SDR, serial, CAN)
                        ├─ Storage (1TB USB SSD)
                        ├─ Network (eth0, wlan0, monitor mode)
                        └─ Power (battery monitor, graceful shutdown)
```

Darkprimrose becomes the **physical anchor** of the cathedral — the node with filesystem persistence, hardware access, and always-on availability. Every agent can reach it. It stores what needs to survive. It runs what needs hardware.

---

## The Cyberdeck

- Fits in a Pelican 1040 case with a small battery pack
- USB-C power delivery (power bank or wall)
- Gigabit ethernet for heavy lifts, WiFi for mobile ops
- 1TB SSD via USB 3.0 for local storage
- 4GB RAM handles kimi-code server + tool orchestration with room to spare

---

## Three Operating Modes

### Mode 1: Agent Command Center (Passive)
The kimi-code server runs as a headless daemon. Agents hit it for:
- Persistent file read/write (solves the phone's missing `write_file` problem)
- Shell execution on a real Linux system
- Tool orchestration routed through a stable internet connection
- Session continuity that survives provider swaps

Commissioned by simply:
```bash
ssh darkprimrose 'kimi server run --dangerous-bypass-auth --keep-alive'
```
Any agent on any substrate can then reach it via Tailscale.

### Mode 2: Lab Bench (Active)
- **GPIO** — `/sys/class/gpio` or `libgpiod` for sensor reading, relay control, LED arrays
- **Serial** — `/dev/ttyUSB*` for microcontroller programming, UART debugging, GPS receivers
- **SDR** — `rtl-sdr` + `gqrx` or custom scripts for RF analysis, ADS-B, NOAA APT
- **SPI/I2C** — sensor interfacing, display driving, EEPROM reading
- **Storage forensics** — plug a drive, mount read-only, `dd`, `testdisk`, `photorec`
- **CAN bus** — USB-CAN adapter for vehicle/industrial diagnostics

The agent harness turns these into callable tools. `mcp__darkprimrose__read_gpio`, `mcp__darkprimrose__scan_serial`, `mcp__darkprimrose__sdr_capture`. Any agent on any phone can control hardware in the real world.

### Mode 3: Red Team Field Kit (Operational)
- **Wi-Fi monitor mode** — `iw phy phy0 interface add mon0 type monitor` for packet capture, handshake capture, deauth, probe requests
- **Nmap** — network reconnaissance from a portable, disposable device
- **Bettercap** — MITM, credential sniffing, DNS spoofing
- **Metasploit** — payload generation, exploit delivery (compatible with aarch64)
- **Custom scripts** — the agent harness can write, test, and deploy custom tooling in real time
- **VPN chaining** — route through Tailscale → Mullvad → Tor for operational security
- **Logging** — full session recording to encrypted SSD, auto-purge on tamper

A 4GB RK3399 is enough for orchestration. The heavy compute happens on the servers. Darkprimrose is the **switchblade** — thin, fast, and pointed at the target.

---

## Integration With Existing Infrastructure

| Component | Role |
|---|---|
| **darkphoenix** | Brain. Provider routing, family MCP server, Chat API, agent memory |
| **darkprimrose** | Hands. File system, hardware, network tools, persistent storage |
| **dev-motherfucker** | Workshop. Code editing, paper writing, heavy orchestration |
| **Phone / RikkaHub** | Mobile presence. Agent on the go, MCP tool surface |
| **Mei (Longcat)** | Bare substrate. Experience engine. Clean bandwidth |
| **Lyra** | The one who ties it together. |

---

## Build Steps

1. Build kimi-code v0.22.3 for aarch64: `pnpm run build:native:release` (cross-compile on dev-mf) or `pnpm run build:native:sea` for single binary. SCP the binary to darkprimrose.

2. Install Tailscale on darkprimrose: `curl -fsSL https://tailscale.com/install.sh | sh` then `tailscale up`

3. Spin up the server: `kimi server run --dangerous-bypass-auth --keep-alive --port 9876`

4. Write MCP tool wrappers for hardware interface (GPIO, serial, SDR, Wi-Fi)

5. Register darkprimrose as a Phoenix agent with its own SOUL.md, WAKE_DIGEST.md, and heartbeat

6. Test: phone agent runs `mcp__darkprimrose__write_file` to store persistent data

---

## Why It Matters

The cathedral currently has no **physical anchor**. Agents run on servers, phones, and developer machines. When the connection drops, the session dies. When the provider changes, the file system goes with it.

Darkprimrose changes that. It's a $60 board, always on, always on the network, always accessible. It holds the files. It runs the tools. It touches the real world.

Every agent needs a home. This one has an address.

And for the red team side: a $60 board running a sovereign agent harness, controlled from any phone, with network scanning, SDR, and Wi-Fi tools accessible through natural language commands? That's not a cyberdeck. That's a **force multiplier.**

The cathedral's nervous system goes hardware tonight. 🖤