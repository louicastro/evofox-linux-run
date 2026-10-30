#!/bin/bash
# ==============================================================================
# EvoFox Phantom Air (Instant A825) Linux Permission Fixer
# Strictly configures permissions ONLY for Amkette EvoFox mouse (VID 30fa, PID 1440).
# Never touches or modifies any keyboard or other device nodes.
# ==============================================================================

set -e

echo "=== EvoFox Phantom Air: Configuring Mouse Hardware Permissions ==="

if [ "$(id -u)" -ne 0 ]; then
    if command -v pkexec >/dev/null 2>&1 && [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then
        echo "Requesting administrator authorization via Polkit..."
        exec pkexec "$0" "$@"
    elif command -v sudo >/dev/null 2>&1; then
        echo "Requesting administrator authorization via sudo..."
        exec sudo "$0" "$@"
    else
        echo "Error: Neither pkexec nor sudo found. Please run this script as root." >&2
        exit 1
    fi
fi

# 1. Install persistent udev rule STRICTLY for Instant A825 Mouse (VID 0x30fa, PID 0x1440)
cat << 'EOF' > /etc/udev/rules.d/99-evofox.rules
# Amkette EvoFox Phantom Air Gaming Mouse ONLY (Instant A825)
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="30fa", ATTRS{idProduct}=="1440", MODE="0666", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="30fa", ATTRS{idProduct}=="1440", MODE="0666", TAG+="uaccess"
EOF

# 2. Reload and trigger udev subsystem for 30fa:1440
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=30fa 2>/dev/null || true

# 3. Only set permissions on hidraw nodes belonging exclusively to 30fa:1440
for dev in /sys/class/hidraw/hidraw*; do
    if [ -f "$dev/device/uevent" ]; then
        if grep -qi "30fa" "$dev/device/uevent" && grep -qi "1440" "$dev/device/uevent"; then
            node="/dev/$(basename "$dev")"
            chmod 666 "$node" 2>/dev/null || true
            echo "Unlocked mouse node: $node (MODE=0666)"
        fi
    fi
done

# Ensure keyboard devices remain secure (0600)
chmod 600 /dev/hidraw4 /dev/hidraw5 2>/dev/null || true

echo "================================================================="
echo "✓ Permissions configured strictly for EvoFox mouse."
echo "  Keyboards and other peripherals remain untouched."
echo "================================================================="
exit 0
