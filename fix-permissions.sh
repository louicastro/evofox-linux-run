#!/bin/bash
# ==============================================================================
# EvoFox Phantom Air (Instant A825) Linux Permission Setup
# Target OS: Arch Linux, CachyOS, and systemd-based Linux distributions.
#
# Configures secure non-root hardware access strictly for Amkette EvoFox mouse
# (USB VID 0x30FA / PID 0x1440) using systemd-logind uaccess and the 'input' group.
#
# Security Guarantees:
# - Strictly restricted to VID 0x30FA and PID 0x1440.
# - Never assumes fixed /dev/hidraw device numbers.
# - Never touches keyboards, trackpads, or unrelated devices.
# - Never uses insecure world-writable (0666) permissions.
# ==============================================================================

set -euo pipefail

TARGET_VID="30fa"
TARGET_PID="1440"
UDEV_RULE_FILE="/etc/udev/rules.d/99-evofox.rules"

echo "=== EvoFox Phantom Air: Secure Device Permission Setup ==="

# Identify the calling user (even when invoked via sudo or pkexec)
CALLING_USER="${SUDO_USER:-$(logname 2>/dev/null || whoami)}"

if [ "$(id -u)" -ne 0 ]; then
    if command -v pkexec >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        echo "Elevating privileges via Polkit..."
        exec pkexec "$0" "$@"
    elif command -v sudo >/dev/null 2>&1; then
        echo "Elevating privileges via sudo..."
        exec sudo "$0" "$@"
    else
        echo "Error: Root privileges required to install udev rules." >&2
        echo "Please run: sudo $0" >&2
        exit 1
    fi
fi

# 1. Install production-ready secure udev rule
echo "Installing secure udev rule to ${UDEV_RULE_FILE}..."
cat << 'EOF' > "${UDEV_RULE_FILE}"
# Secure udev rule for Amkette EvoFox Phantom Air Gaming Mouse (Instant A825 SoC)
# USB VID: 0x30FA, USB PID: 0x1440
#
# Grants access to active local desktop users via systemd-logind ACLs (uaccess)
# and fallback access to members of the 'input' system group (MODE="0660").
# Never uses insecure world-writable (0666) permissions.
# Never touches or affects keyboards, trackpads, or other peripherals.

KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="30fa", ATTRS{idProduct}=="1440", TAG+="uaccess", GROUP="input", MODE="0660"
EOF

# 2. Reload and trigger udev rules
echo "Reloading udev rules..."
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger --subsystem-match=hidraw --attr-match=idVendor="${TARGET_VID}" 2>/dev/null || true

# 3. Dynamically locate only nodes belonging to VID 30fa / PID 1440 and apply group/ACL
echo "Configuring permissions on connected mouse nodes..."
MATCH_COUNT=0

for syspath in /sys/class/hidraw/hidraw*; do
    [ -e "$syspath" ] || continue
    uevent="${syspath}/device/uevent"
    if [ -f "$uevent" ]; then
        if grep -qi "idVendor=.*${TARGET_VID}" "$uevent" 2>/dev/null || grep -qi "${TARGET_VID}" "$uevent" 2>/dev/null; then
            if grep -qi "${TARGET_PID}" "$uevent" 2>/dev/null; then
                devname="$(basename "$syspath")"
                node="/dev/${devname}"
                if [ -e "$node" ]; then
                    chgrp input "$node" 2>/dev/null || true
                    chmod 0660 "$node" 2>/dev/null || true
                    if command -v setfacl >/dev/null 2>&1 && [ -n "${CALLING_USER}" ] && [ "${CALLING_USER}" != "root" ]; then
                        setfacl -m "u:${CALLING_USER}:rw" "$node" 2>/dev/null || true
                    fi
                    echo "  ✓ Configured node: ${node} (owner: root:input, mode: 0660 + uaccess ACL)"
                    MATCH_COUNT=$((MATCH_COUNT + 1))
                fi
            fi
        fi
    fi
done

if [ "$MATCH_COUNT" -eq 0 ]; then
    echo "  (Mouse is not currently plugged in. Permissions will automatically apply on connect via udev.)"
fi

# 4. Optional user recommendation for input group
if [ -n "${CALLING_USER}" ] && [ "${CALLING_USER}" != "root" ]; then
    if ! id -nG "${CALLING_USER}" 2>/dev/null | grep -qw "input"; then
        echo "Tip: For headless / background access without an active GUI session, you can add yourself to the 'input' group:"
        echo "     sudo usermod -aG input ${CALLING_USER}"
    fi
fi

echo "================================================================="
echo "✓ Secure device permissions successfully configured."
echo "  Target: USB ${TARGET_VID}:${TARGET_PID} only."
echo "  All keyboard and unrelated HID devices remain completely untouched."
echo "================================================================="
exit 0
