# EvoFox Phantom Air — Linux Control Suite

Linux configuration tools for the **Amkette EvoFox Phantom Air** gaming mouse (USB VID:PID `30fa:1440`, Instant Microelectronics A825).

The project contains Python CLI and desktop interfaces, a C implementation and a Rust reference CLI. Communication uses reverse-engineered HID Feature Reports. Hardware behavior must be verified against the physical mouse before claiming support for additional revisions.

## Features

- Six configurable DPI stages (nominal hardware steps from 200 to 12,800 DPI)
- RGB effects and per-stage LED indicator colors
- Polling-rate selection (125, 250, 500 or 1000 Hz)
- Six-button remapping and presets in the Python/C tools
- Save supported settings to onboard memory

## Arch Linux and CachyOS

A VCS PKGBUILD is available at `packaging/arch/PKGBUILD`:

```bash
sudo pacman -S --needed base-devel git
cd packaging/arch
makepkg -si
```

The package installs `evofox-ctl`, `evofox-gui`, desktop integration, documentation and a udev rule. GTK is optional; install `gtk3` and `python-gobject` for the native interface. Without GTK, the launcher uses the browser-based GUI.

The package recipe currently tracks the `production/arch-cachyos` branch for review. Before an official stable/AUR release, pin it to an immutable release tag or source archive and publish a verified checksum.

## Manual setup

```bash
sudo ./fix-permissions.sh
./run-evofox
```

The permission script installs only the VID:PID-specific udev rule. It never runs chmod on hidraw nodes and never changes keyboard permissions. The rule uses `TAG+="uaccess"` so systemd-logind can grant access to the active local desktop seat; it does not grant global `0666` access.

After installing or changing the rule, reconnect the mouse. For headless or non-logind environments, configure a dedicated group-based udev policy appropriate to that system rather than making the device world-writable.

## CLI examples

```bash
evofox-ctl status
evofox-ctl dpi 6 12000
evofox-ctl rate 1000
evofox-ctl rgb 4
evofox-ctl remap 6 led
evofox-ctl save
```

## Development and tests

```bash
python3 -m py_compile evofox.py evofox-gtk.py evofox-gui.py
make -C tools clean all
cd tools/evofox-rs
cargo test
cargo build --release
```

GitHub Actions runs syntax checks, builds the C and Rust tools, and builds the Arch package.

## Security and limitations

- Device discovery matches USB VID/PID and requires the HID report descriptor marker for Feature Report ID `0x07`; fixed `/dev/hidrawN` names are not used.
- The launcher and GUI do not escalate privileges, install udev rules or change device-node modes.
- Udev access is limited to the matching mouse and the active local desktop seat.
- HID packet formats are reverse-engineered. The automated checks validate source/build quality, not physical hardware behavior or every firmware revision.
- Do not run the tools with `sudo` as a workaround for missing seat ACLs; install the udev rule and reconnect the mouse instead.

## License

MIT. See [LICENSE](LICENSE).
