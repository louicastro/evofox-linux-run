# EvoFox Phantom Air — Linux Control Suite

Native Linux configuration tools for the **Amkette EvoFox Phantom Air Gaming Mouse** (Instant Microelectronics A825 SoC, USB `30FA:1440`).

Reverse-engineered HID Feature Report protocol — no vendor drivers or Wine needed.

## Features

- **DPI Control**: 200–12,800 DPI across 6 stages with real-time switching
- **RGB Lighting**: 8 LED effects (Static, Breathing, Rainbow Wave, Neon Cycle, etc.) with color picker, speed & brightness
- **Polling Rate**: 125 / 250 / 500 / 1000 Hz
- **Button Remapping**: All 6 buttons programmable — Rapid Fire, Double Click, Media Keys, DPI ±, LED Switch, Show Desktop, Disable
- **Flash Save**: Commit settings to onboard mouse memory

## Quick Start

```bash
# 1. Fix permissions (one-time, needs sudo)
sudo ./fix-permissions.sh

# 2. Launch GUI
./run-evofox

# Or use CLI
./evofox-ctl status
./evofox-ctl dpi 6 12000
./evofox-ctl preset gaming
./evofox-ctl remap 6 led
./evofox-ctl save
```

## Tools

| File | Description |
|------|-------------|
| `run-evofox` | Universal launcher (auto-selects GTK → Web → CLI) |
| `evofox-gtk.py` | Native GTK 3 GUI with real-time color picker |
| `evofox-gui.py` | Web GUI (localhost:8787, opens in browser) |
| `evofox.py` | Python CLI |
| `evofox-ctl` | Compiled C CLI (fastest, zero dependencies) |
| `fix-permissions.sh` | udev rule installer for non-root access |
| `tools/evofox-ctl.c` | C source code |
| `tools/evofox-rs/` | Rust implementation |

## Protocol

All communication uses **8-byte HID Feature Reports** via `ioctl(HIDIOCSFEATURE)` on the vendor control node (`/dev/hidrawX` with Report ID `0x07`).

| Opcode | Function |
|--------|----------|
| `0x10` | DPI / Stage Select |
| `0x11` | Polling Rate |
| `0x13` | RGB Effect Mode |
| `0x14` | Stage LED Color |
| `0x15` | Button Remapping |
| `0x20` | Save to Flash |

### Button Action IDs

| ID | Action | ID | Action |
|----|--------|----|--------|
| 1 | Left Click | 14 | Rapid Fire (Triple) |
| 2 | Right Click | 15 | Double Click |
| 3 | Middle Click | 16 | DPI + |
| 4 | Browser Back | 17 | DPI − |
| 5 | Browser Forward | 19 | LED Mode Switch |
| 6 | DPI Loop | 20 | Mute |
| 21 | Volume Up | 25 | Next Track |
| 22 | Volume Down | 26 | Previous Track |
| 27 | Play/Pause | 30 | Show Desktop |
| 50 | Disabled | | |

## Requirements

- Linux kernel with `hidraw` support
- Python 3 + PyGObject (GTK 3) for GUI, or just the C binary
- No proprietary drivers needed

## Safety

- **Zero keyboard interference** — strictly targets VID `30FA` / PID `1440`
- Uses `ioctl()` only, never `write()` on HID nodes
- Keyboard nodes (`/dev/hidraw4`, `/dev/hidraw5`) remain untouched at `0600`

## License

MIT
