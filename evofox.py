#!/usr/bin/env python3
"""
evofox.py: Standalone Linux CLI configuration tool for Amkette EvoFox Phantom Air
           (Instant Microelectronics A825, USB VID 30FA:1440).
Features real-time DPI, stage switching, dedicated color interface, and 12,000 DPI preset.
Strictly communicates via ioctl on /dev/hidraw1 without touching any keyboards.
"""

import sys
import os
import glob
import fcntl
import argparse

TARGET_VID = 0x30FA
TARGET_PID = 0x1440
REPORT_ID = 0x07
REPORT_SIZE = 8
HIDIOCSFEATURE_8 = 0xC0084806

DPI_TABLE = [
    (1, 200), (2, 400), (3, 600), (4, 800), (5, 1000), (6, 1200),
    (7, 1400), (8, 1600), (9, 1800), (10, 2000), (12, 2400), (13, 3200),
    (14, 4000), (15, 4800), (16, 5600), (17, 6400), (18, 7200), (19, 8000),
    (20, 8800), (21, 9600), (22, 10400), (23, 11200), (24, 12800)
]

ACTION_NAMES = {
    "left": 1, "click": 1, "lclick": 1,
    "right": 2, "rclick": 2,
    "middle": 3, "scroll": 3, "mclick": 3,
    "back": 4, "backward": 4, "prev": 4,
    "forward": 5, "next": 5,
    "dpi": 6, "dpiloop": 6,
    "rapidfire": 14, "burst": 14, "triple": 14,
    "double": 15, "doubleclick": 15,
    "dpi+": 16, "dpiup": 16,
    "dpi-": 17, "dpidown": 17,
    "led": 19, "rgb": 19, "ledswitch": 19,
    "mute": 20,
    "vol+": 21, "volup": 21, "volumeup": 21,
    "vol-": 22, "voldown": 22, "volumedown": 22,
    "nexttrack": 25,
    "prevtrack": 26,
    "playpause": 27, "play": 27, "pause": 27,
    "desktop": 30, "showdesktop": 30,
    "disable": 50, "none": 50, "off": 50,
}

ACTION_DESCRIPTIONS = {
    1: "Left Click",
    2: "Right Click",
    3: "Middle Click / Scroll Wheel",
    4: "Browser Backward",
    5: "Browser Forward",
    6: "DPI Loop",
    14: "Rapid Fire (Triple Click)",
    15: "Double Click",
    16: "DPI + (Step Up)",
    17: "DPI - (Step Down)",
    19: "LED Mode Switch",
    20: "Mute Audio",
    21: "Volume Up",
    22: "Volume Down",
    25: "Next Track",
    26: "Previous Track",
    27: "Play / Pause",
    30: "Show Desktop",
    50: "Disabled / None",
}

DEFAULT_BUTTONS = {1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 6}

def parse_action(val):
    if val is None:
        return None
    val_str = str(val).lower().strip()
    if val_str.isdigit():
        return int(val_str)
    if val_str in ACTION_NAMES:
        return ACTION_NAMES[val_str]
    raise ValueError(f"Unknown action '{val}'. Valid names: {', '.join(sorted(ACTION_NAMES.keys()))}")

def dpi_to_index(target_dpi):
    if not 200 <= target_dpi <= 12800:
        raise ValueError('DPI must be between 200 and 12800')
    if target_dpi <= 200:
        return 1, 200
    if target_dpi >= 11600:
        return 24, 12800

    best_idx = 4
    best_diff = float('inf')
    best_dpi = 800
    for idx, dpi in DPI_TABLE:
        diff = abs(target_dpi - dpi)
        if diff < best_diff:
            best_diff = diff
            best_idx = idx
            best_dpi = dpi
    return best_idx, best_dpi

def find_control_device():
    """Find the specific vendor control node for Amkette EvoFox mouse (VID 30FA, PID 1440)."""
    candidates = []
    for dev_path in sorted(glob.glob('/sys/class/hidraw/hidraw*')):
        name = os.path.basename(dev_path)
        uevent_file = os.path.join(dev_path, 'device', 'uevent')
        if not os.path.exists(uevent_file):
            continue
        try:
            with open(uevent_file, 'r', errors='ignore') as f:
                content = f.read()
        except:
            continue
        if ('30FA' in content or '30fa' in content) and '1440' in content:
            rdesc_file = os.path.join(dev_path, 'device', 'report_descriptor')
            is_control = False
            if os.path.exists(rdesc_file):
                try:
                    with open(rdesc_file, 'rb') as rf:
                        if b'\x85\x07' in rf.read():
                            is_control = True
                except:
                    pass
            node = f'/dev/{name}'
            if is_control:
                return node
            candidates.append(node)
    return None

def send_packet(dev_path, packet):
    """Send 8-byte HID Feature Report strictly via ioctl. Never calls write."""
    target = dev_path or find_control_device()
    if not target:
        print("Error: EvoFox Phantom Air (30FA:1440) not found.", file=sys.stderr)
        return False

    buf = bytearray(8)
    for i, b in enumerate(packet[:8]):
        buf[i] = b

    fd = None
    try:
        fd = os.open(target, os.O_RDWR | os.O_NONBLOCK)
        fcntl.ioctl(fd, HIDIOCSFEATURE_8, buf)
        return True
    except PermissionError:
        print(f"Error: Permission denied opening {target}.", file=sys.stderr)
        print("Hint: Run fix-permissions.sh to configure non-root access:", file=sys.stderr)
        print("      sudo ./fix-permissions.sh", file=sys.stderr)
        return False
    except OSError as e:
        print(f"Communication error on {target}: {e}", file=sys.stderr)
        return False
    finally:
        if fd is not None:
            os.close(fd)

def save_settings(dev_path):
    return send_packet(dev_path, [REPORT_ID, 0x20, 0, 0, 0, 0, 0, 0])

def main():
    parser = argparse.ArgumentParser(
        description="Amkette EvoFox Phantom Air (Instant A825) Linux Configuration Utility"
    )
    sub = parser.add_subparsers(dest="command", help="Command to execute")

    sub.add_parser("status", help="Show mouse connection status and device information")

    p_stage = sub.add_parser("stage", help="Select active DPI stage (1-6)")
    p_stage.add_argument("stage", type=int, choices=range(1, 7), help="DPI Stage number (1 to 6)")

    p_dpi = sub.add_parser("dpi", help="Configure DPI for a stage (200 - 12800)")
    p_dpi.add_argument("stage", type=int, choices=range(1, 7), help="DPI Stage number (1 to 6)")
    p_dpi.add_argument("value", type=int, help="Target DPI (e.g. 800, 1600, 2400, 12000, 12800)")

    p_rate = sub.add_parser("rate", help="Set USB polling rate in Hz")
    p_rate.add_argument("hz", type=int, choices=[125, 250, 500, 1000], help="Polling rate in Hz")

    p_rgb = sub.add_parser("rgb", help="Configure RGB lighting effect")
    p_rgb.add_argument("mode", type=int, choices=range(0, 15), help="0=Off, 1=Breathe, 2=Static, 3=Neon, 4=Wave")
    p_rgb.add_argument("--speed", type=int, choices=[1, 2, 3], default=2, help="Animation speed (1-3)")
    p_rgb.add_argument("--bright", type=int, choices=[1, 2, 3, 4], default=4, help="Brightness level (1-4)")

    p_color = sub.add_parser("color", help="Set LED color for a DPI stage")
    p_color.add_argument("stage", type=int, choices=range(1, 7), help="DPI Stage number (1 to 6)")
    p_color.add_argument("hex_color", type=str, help="Hex color code (e.g. #FF0000 or FF00FF)")

    p_remap = sub.add_parser("remap", help="Remap an individual button (1-6)")
    p_remap.add_argument("button", type=int, choices=range(1, 7), help="Button number (1 to 6)")
    p_remap.add_argument("action", type=str, help="Action name or ID (e.g. rapidfire, led, vol+, double, 14, 19)")
    p_remap.add_argument("--save", action="store_true", help="Save to onboard flash memory")

    p_btn = sub.add_parser("buttons", help="Configure button mappings or presets")
    p_btn.add_argument("--preset", choices=["default", "gaming", "media", "rgb"], help="Preset button configuration")
    p_btn.add_argument("--b1", type=str, help="Button 1 (Left)")
    p_btn.add_argument("--b2", type=str, help="Button 2 (Right)")
    p_btn.add_argument("--b3", type=str, help="Button 3 (Middle / Scroll)")
    p_btn.add_argument("--b4", type=str, help="Button 4 (Side Forward)")
    p_btn.add_argument("--b5", type=str, help="Button 5 (Side Backward)")
    p_btn.add_argument("--b6", type=str, help="Button 6 (Top DPI Button)")
    p_btn.add_argument("--save", action="store_true", help="Save to onboard flash memory")

    sub.add_parser("save", help="Commit current settings to mouse onboard flash memory")

    args = parser.parse_args()

    if args.command == 'dpi' and not 200 <= args.value <= 12800:
        parser.error('DPI must be between 200 and 12800')

    if args.command == 'color' and (len(args.hex_color.lstrip('#')) != 6 or any(c not in '0123456789abcdefABCDEF' for c in args.hex_color.lstrip('#'))):
        parser.error('color must be a six-digit hexadecimal value such as #ff00aa')

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dev_path = find_control_device()
    if not dev_path:
        print("Error: EvoFox Phantom Air / Instant A825 (30FA:1440) not found.", file=sys.stderr)
        print("Please verify the mouse is connected via USB ('lsusb').", file=sys.stderr)
        sys.exit(1)

    if args.command == "status":
        print("=" * 65)
        print(" EvoFox Phantom Air / Instant A825 Linux Configuration Utility")
        print("=" * 65)
        print("Device Status:    CONNECTED")
        print(f"Hardware ID:      USB VID 0x{TARGET_VID:04X}, PID 0x{TARGET_PID:04X}")
        print("Sensor Model:     Instant Microelectronics Instant A825")
        print(f"Control Node:     {dev_path}")
        print("Max Resolution:   12,800 DPI (Supported steps: 200 to 12800)")
        print("Supported Rates:  125 Hz, 250 Hz, 500 Hz, 1000 Hz")
        print("RGB Modes:        14 effects (0=Off, 1=Breathe, 2=Static, 3=Neon, 4=Wave, etc.)")
        print("Programmable:     6 Buttons (Rapid Fire, Double Click, Media, DPI, LED)")
        print("=" * 65)
        print("Supported Button Actions:")
        print("  1=Left, 2=Right, 3=Middle, 4=Backward, 5=Forward, 6=DPILoop")
        print("  14=RapidFire, 15=DoubleClick, 16=DPI+, 17=DPI-, 19=LEDModeSwitch")
        print("  20=Mute, 21=Vol+, 22=Vol-, 25=NextTrack, 26=PrevTrack, 27=Play/Pause")
        print("  30=ShowDesktop, 50=Disabled")
        print("=" * 65)

    elif args.command == "stage":
        pkt = [REPORT_ID, 0x10, 0x01, args.stage - 1, 0, 0, 0, 0]
        if send_packet(dev_path, pkt):
            save_settings(dev_path)
            print(f"✓ Activated DPI Stage {args.stage}.")

    elif args.command == "dpi":
        idx, actual_dpi = dpi_to_index(args.value)
        pkt_dpi = [REPORT_ID, 0x10, idx, 0, 0, 0, 0, 0]
        pkt_stage = [REPORT_ID, 0x10, 0x01, args.stage - 1, 0, 0, 0, 0]
        if send_packet(dev_path, pkt_dpi):
            send_packet(dev_path, pkt_stage)
            save_settings(dev_path)
            print(f"✓ Stage {args.stage} set to {actual_dpi} DPI (Hardware Step Index: {idx}).")

    elif args.command == "rate":
        codes = {1000: 0x00, 500: 0x01, 250: 0x03, 125: 0x07}
        pkt = [REPORT_ID, 0x11, codes[args.hz], 0, 0, 0, 0, 0]
        if send_packet(dev_path, pkt):
            save_settings(dev_path)
            print(f"✓ USB Polling Rate set to {args.hz} Hz.")

    elif args.command == "rgb":
        b_val = 0x80 | (((args.bright - 1) & 0x03) << 4)
        pkt = [REPORT_ID, 0x13, (args.mode | 0x80) & 0xFF, args.speed & 0x07, b_val, 0, 0, 0]
        if send_packet(dev_path, pkt):
            save_settings(dev_path)
            print(f"✓ RGB mode set to {args.mode} (Speed: {args.speed}, Brightness: {args.bright}).")

    elif args.command == "color":
        c = args.hex_color.lstrip('#')
        if len(c) != 6:
            print("Error: Hex color must be in format #RRGGBB (e.g. #FF0000)", file=sys.stderr)
            sys.exit(1)
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
        g4 = (g >> 4) & 0x0F
        r4 = (r >> 4) & 0x0F
        b4 = (b >> 4) & 0x0F
        # Instant A825 byte layout:
        # byte 2: ((stage - 1) << 5) | g4
        # byte 3: (r4 << 4) | b4
        pkt_color = [REPORT_ID, 0x14, ((args.stage - 1) << 5) | g4, (r4 << 4) | b4, 0, 0, 0, 0]
        pkt_stage = [REPORT_ID, 0x10, 0x01, args.stage - 1, 0, 0, 0, 0]
        if send_packet(dev_path, pkt_color):
            send_packet(dev_path, pkt_stage)
            save_settings(dev_path)
            print(f"✓ Stage {args.stage} LED color set to #{c.upper()}.")

    elif args.command == "remap":
        try:
            act_id = parse_action(args.action)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        mapping = dict(DEFAULT_BUTTONS)
        mapping[args.button] = act_id
        # Instant A825 hardware packet order: [ReportID, 0x15, b1, b3, b2, b4, b5, b6]
        pkt = [REPORT_ID, 0x15, mapping[1], mapping[3], mapping[2], mapping[4], mapping[5], mapping[6]]
        if send_packet(dev_path, pkt):
            if args.save:
                save_settings(dev_path)
            act_name = ACTION_DESCRIPTIONS.get(act_id, f"Action #{act_id}")
            print(f"✓ Button {args.button} remapped to '{act_name}' (Action ID: {act_id})." + (" [Saved to Flash]" if args.save else " [Live Preview]"))

    elif args.command == "buttons":
        mapping = dict(DEFAULT_BUTTONS)
        if args.preset == "gaming":
            mapping[4] = 14  # Rapid Fire on Button 4
        elif args.preset == "media":
            mapping[4] = 21  # Vol+
            mapping[5] = 22  # Vol-
            mapping[6] = 27  # Play/Pause
        elif args.preset == "rgb":
            mapping[6] = 19  # LED Mode Switch on DPI Button

        for b_num, b_arg in [(1, args.b1), (2, args.b2), (3, args.b3), (4, args.b4), (5, args.b5), (6, args.b6)]:
            if b_arg:
                try:
                    mapping[b_num] = parse_action(b_arg)
                except ValueError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    sys.exit(1)

        pkt = [REPORT_ID, 0x15, mapping[1], mapping[3], mapping[2], mapping[4], mapping[5], mapping[6]]
        if send_packet(dev_path, pkt):
            if args.save:
                save_settings(dev_path)
            print("✓ Button configuration applied:")
            for b_num in range(1, 7):
                code = mapping[b_num]
                name = ACTION_DESCRIPTIONS.get(code, f"Action #{code}")
                print(f"  • Button {b_num}: {name} (ID: {code})")
            if args.save:
                print("✓ Saved to onboard flash memory.")

    elif args.command == "save":
        if save_settings(dev_path):
            print("✓ Settings saved to onboard mouse memory.")

if __name__ == '__main__':
    main()
