# Arch Linux / CachyOS packaging

This repository provides a VCS PKGBUILD in `packaging/arch`. It is intended
for local review and AUR-style packaging; the Git source is pinned to the
`production/arch-cachyos` branch. A published release should switch the
recipe to an immutable release tag or source archive with a verified checksum.

Build locally:

```bash
sudo pacman -S --needed base-devel git
cd packaging/arch
makepkg -si
```

The package installs `evofox-ctl` (the Python CLI), `evofox-gui`, the GUI
modules, the udev rule, desktop entry, documentation and license.

GTK is optional. Install `gtk3` and `python-gobject` for the native desktop
interface. Without them the launcher uses the browser-based GUI.

The udev rule uses `TAG+="uaccess"` and does not set global 0666 permissions.
It grants access to the active local desktop seat through systemd-logind.
