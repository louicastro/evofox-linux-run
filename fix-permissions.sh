#!/usr/bin/env bash
# Install only the EvoFox-specific udev rule. Never chmod hidraw device nodes.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RULE="$ROOT/tools/99-evofox.rules"
DEST="/etc/udev/rules.d/99-evofox.rules"

if [[ $EUID -ne 0 ]]; then
    echo "Run as root: sudo $0" >&2
    exit 1
fi
command -v udevadm >/dev/null || { echo "udevadm is required (systemd-udev)." >&2; exit 1; }
[[ -r "$RULE" ]] || { echo "Cannot read $RULE" >&2; exit 1; }
install -Dm0644 "$RULE" "$DEST"
udevadm control --reload-rules
udevadm trigger --subsystem-match=hidraw
echo "Installed $DEST. Reconnect the mouse to apply the rule."
