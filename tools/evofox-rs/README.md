# evofox-ctl (Rust Edition)

High-performance, zero-dependency Linux CLI configuration tool for **Amkette EvoFox Phantom Air Gaming Mouse** (powered by Instant Microelectronics A825 SoC, USB ID `30fa:1440`).

## Features
- **Dynamic Device Detection**: Automatically scans `/sys/class/hidraw` to locate the mouse's vendor control interface (`Report ID 0x07`).
- **High DPI Support**: Complete 24-step hardware table (200 to 12,800 DPI, including requested 12,000 DPI mapping).
- **USB Polling Rate**: 125 Hz, 250 Hz, 500 Hz, 1000 Hz.
- **RGB Lighting Controls**: 14 lighting modes with speed (1-3) and brightness (1-4).
- **Per-Stage LED Color**: Customize indicator colors per DPI stage with hex codes (`#RRGGBB`).
- **Onboard Flash Memory Save**: Settings persist in the mouse hardware across reboots and across OSes.
- **Zero External Crates**: Compiles in ~1 second with no network dependencies.

## Building and Installing
```bash
cd tools/evofox-rs
cargo build --release
sudo cp target/release/evofox-ctl /usr/local/bin/
```

## Permissions (udev rule)
To configure the mouse without `sudo`:
```bash
sudo cp ../99-evofox.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Usage Examples
```bash
# Check mouse status and current control node
evofox-ctl status

# Switch active DPI stage to stage 2
evofox-ctl stage 2

# Set DPI for stage 6 to 12,000 DPI (mapped to max sensor step)
evofox-ctl dpi 6 12000

# Set USB polling rate to 1000 Hz
evofox-ctl rate 1000

# Set RGB lighting effect to Rainbow Wave (mode 4)
evofox-ctl rgb 4 2 3

# Set stage 1 indicator color to Cyan (#00FFFF)
evofox-ctl color 1 '#00FFFF'

# Save settings to mouse hardware
evofox-ctl save
```
