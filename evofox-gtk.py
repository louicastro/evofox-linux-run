#!/usr/bin/env python3
"""
evofox-gtk: Native GTK 3 Control Center for EvoFox Phantom Air / Instant A825.
Features real-time Colour Change Interface, live DPI adjustment with 12,000 DPI preset,
safe ioctl-only communication strictly targeting the mouse, with zero keyboard interference.
"""

import os
import sys
import glob
import time
import fcntl
import subprocess

TARGET_VID = 0x30FA
TARGET_PID = 0x1440
REPORT_ID = 0x07
HIDIOCSFEATURE_8 = 0xC0084806

DPI_STEPS = [
    200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2400, 3200,
    4000, 4800, 5600, 6400, 7200, 8000, 8800, 9600, 10400, 11200, 12000, 12800
]

DPI_TABLE = [
    (1, 200), (2, 400), (3, 600), (4, 800), (5, 1000), (6, 1200),
    (7, 1400), (8, 1600), (9, 1800), (10, 2000), (12, 2400), (13, 3200),
    (14, 4000), (15, 4800), (16, 5600), (17, 6400), (18, 7200), (19, 8000),
    (20, 8800), (21, 9600), (22, 10400), (23, 11200), (24, 12800)
]

PRESET_COLORS = [
    ("Red", "#ff0033", (255, 0, 51)),
    ("Orange", "#ff6600", (255, 102, 0)),
    ("Yellow", "#ffd700", (255, 215, 0)),
    ("Green", "#00ff33", (0, 255, 51)),
    ("Mint", "#00e5a3", (0, 229, 163)),
    ("Cyan", "#00ffff", (0, 255, 255)),
    ("Blue", "#0055ff", (0, 85, 255)),
    ("Purple", "#8800ff", (136, 0, 255)),
    ("Pink", "#ff00aa", (255, 0, 170)),
    ("White", "#ffffff", (255, 255, 255)),
]

BUTTON_ACTIONS = [
    (1, "🖱️ Left Click"),
    (2, "🖱️ Right Click"),
    (3, "🖱️ Middle Click / Scroll"),
    (4, "🌐 Browser Backward"),
    (5, "🌐 Browser Forward"),
    (6, "⚡ DPI Loop"),
    (14, "🔥 Rapid Fire (Triple Click)"),
    (15, "⚡ Double Click"),
    (16, "⚡ DPI + (Step Up)"),
    (17, "⚡ DPI - (Step Down)"),
    (19, "💡 LED Mode Switch"),
    (20, "🔇 Mute Audio"),
    (21, "🔊 Volume Up"),
    (22, "🔉 Volume Down"),
    (25, "⏭️ Next Track"),
    (26, "⏮️ Previous Track"),
    (27, "⏯️ Play / Pause"),
    (30, "🖥️ Show Desktop"),
    (50, "❌ Disabled / None"),
]

def dpi_to_index(target_dpi):
    if target_dpi <= 200:
        return 1, 200
    if target_dpi >= 11600:
        return 24, 12800
    best_idx, best_diff, best_dpi = 4, float('inf'), 800
    for idx, dpi in DPI_TABLE:
        diff = abs(target_dpi - dpi)
        if diff < best_diff:
            best_diff, best_idx, best_dpi = diff, idx, dpi
    return best_idx, best_dpi

def find_mouse_device():
    """Locate only the report-ID 0x07 control interface for VID:PID 30fa:1440."""
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
        # Strict match for mouse VID/PID
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

def check_permission():
    dev = find_mouse_device()
    if not dev:
        return False, "Not Connected", None
    fd = None
    try:
        fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
        return True, "Ready", dev
    except PermissionError:
        return False, "Permission Denied", dev
    except Exception as e:
        return False, str(e), dev
    finally:
        if fd is not None:
            os.close(fd)

def send_packet(packet):
    """
    Send 8-byte HID Feature Report strictly to the mouse control node via ioctl.
    NEVER touches Apple keyboards and NEVER calls os.write().
    """
    dev = find_mouse_device()
    if not dev:
        return False, "EvoFox Phantom Air (30FA:1440) not found."

    buf = bytearray(8)
    for i, b in enumerate(packet[:8]):
        buf[i] = b

    fd = None
    try:
        fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
        fcntl.ioctl(fd, HIDIOCSFEATURE_8, buf)
        return True, "OK"
    except PermissionError:
        return False, f"Permission Denied on {dev}. Run fix-permissions.sh."
    except Exception as e:
        return False, str(e)
    finally:
        if fd is not None:
            os.close(fd)

# System permissions are managed by the packaged udev rule, not from the GUI.

# Initialize GTK
try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gdk, GLib
except ImportError:
    print("PyGObject (GTK 3) not found. Falling back to Web GUI...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    web_gui = os.path.join(script_dir, 'evofox-gui.py')
    os.execv(sys.executable, [sys.executable, web_gui])

if not Gtk.init_check()[0]:
    print("Cannot connect to display server. Falling back to Web GUI...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    web_gui = os.path.join(script_dir, 'evofox-gui.py')
    os.execv(sys.executable, [sys.executable, web_gui])


class EvoFoxApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="EvoFox Phantom Air - Mouse Control Center")
        self.set_default_size(800, 820)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(12)

        self.active_stage = 6
        self.active_dpi = 12000
        self.stage_dpis = {1: 800, 2: 1600, 3: 2400, 4: 3200, 5: 4800, 6: 12000}
        self.stage_colors = {
            1: (255, 0, 51),    # Red
            2: (0, 255, 51),    # Lime
            3: (0, 85, 255),    # Blue
            4: (255, 0, 170),   # Pink
            5: (0, 255, 255),   # Cyan
            6: (255, 215, 0)    # Yellow
        }
        self.current_rgb = (255, 215, 0)
        self.active_rate = 1000
        self.button_mapping = {1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 6}
        self.button_combos = {}
        self._is_updating = False
        self._color_timer = None
        self._dpi_timer = None
        self._btn_timer = None

        self.apply_css()
        self.build_ui()
        self.refresh_status()

        # Periodic status refresh timer (every 2000 ms)
        GLib.timeout_add(2000, self.periodic_check)

    def apply_css(self):
        css = b"""
        window { background-color: #0b0f19; color: #f1f5f9; }
        .card { background-color: #151d30; border: 1px solid #23314f; border-radius: 12px; padding: 14px; margin-bottom: 4px; }
        .color-card { background-color: #131a2e; border: 1px solid #4f46e5; border-radius: 12px; padding: 16px; margin-bottom: 4px; }
        .title { font-weight: 800; font-size: 13px; color: #f8fafc; letter-spacing: 0.3px; }
        .subtitle { font-size: 11px; color: #94a3b8; }
        .dpi-display { font-family: monospace; font-size: 22px; font-weight: 900; color: #818cf8; background: #0c1222; padding: 4px 14px; border-radius: 8px; border: 1px solid #312e81; }
        .btn-active { background: #4f46e5; color: #ffffff; border-radius: 8px; font-weight: bold; box-shadow: 0 0 10px rgba(99,102,241,0.5); }
        .btn-preset { border-radius: 6px; font-size: 11px; padding: 6px 10px; background: #1e293b; color: #cbd5e1; border: 1px solid #334155; }
        .btn-preset:hover { border-color: #6366f1; }
        .btn-12k { background: #311042; border: 1px solid #a855f7; color: #e9d5ff; font-weight: bold; border-radius: 6px; padding: 6px 12px; }
        .btn-12k:hover { background: #4a1564; }
        .btn-save { background: linear-gradient(135deg, #059669, #0d9488); color: white; font-weight: 800; border-radius: 8px; padding: 8px 18px; border: none; font-size: 13px; }
        .btn-save:hover { opacity: 0.95; }
        .alert-box { background-color: #3b1700; border: 1px solid #b45309; border-radius: 10px; padding: 10px 14px; color: #fef3c7; }
        .btn-unlock { background-color: #d97706; color: white; font-weight: bold; border-radius: 6px; padding: 6px 14px; border: none; font-size: 12px; }
        .swatch-btn { border-radius: 6px; font-size: 11px; font-weight: 600; padding: 5px 8px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def build_ui(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.add(scrolled)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_border_width(12)
        scrolled.add(vbox)

        # Header bar
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox.pack_start(header, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_brand = Gtk.Label(xalign=0)
        lbl_brand.set_markup("<span size='large' weight='heavy' color='#ffffff'>EvoFox Phantom Air</span>")
        lbl_chip = Gtk.Label(xalign=0, label="Instant A825 SoC • Real-Time Linux Control")
        lbl_chip.get_style_context().add_class("subtitle")
        title_box.pack_start(lbl_brand, False, False, 0)
        title_box.pack_start(lbl_chip, False, False, 0)
        header.pack_start(title_box, True, True, 0)

        self.btn_save = Gtk.Button(label="💾 Save to Flash")
        self.btn_save.get_style_context().add_class("btn-save")
        self.btn_save.connect("clicked", self.on_save_clicked)
        header.pack_end(self.btn_save, False, False, 0)

        # Permission guidance only; the GUI never runs privileged commands.
        self.perm_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.perm_box.get_style_context().add_class("alert-box")
        lbl_perm = Gtk.Label(xalign=0)
        lbl_perm.set_line_wrap(True)
        lbl_perm.set_markup("<b>⚠️ Permission required:</b> Install the EvoFox udev rule, reload udev, then reconnect the mouse.")
        self.perm_box.pack_start(lbl_perm, True, True, 0)
        vbox.pack_start(self.perm_box, False, False, 0)

        # Live Status Line
        self.lbl_status = Gtk.Label(xalign=0)
        vbox.pack_start(self.lbl_status, False, False, 0)

        # =====================================================================
        # REAL-TIME COLOUR CHANGE INTERFACE CARD
        # =====================================================================
        color_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        color_card.get_style_context().add_class("color-card")
        vbox.pack_start(color_card, False, False, 0)

        color_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        c_title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        lbl_c_t = Gtk.Label(xalign=0, label="🎨 Colour Change Interface (Real-Time Live)")
        lbl_c_t.get_style_context().add_class("title")
        lbl_c_s = Gtk.Label(xalign=0, label="Instant hardware illumination on click. Only mouse hardware is controlled.")
        lbl_c_s.get_style_context().add_class("subtitle")
        c_title_box.pack_start(lbl_c_t, False, False, 0)
        c_title_box.pack_start(lbl_c_s, False, False, 0)
        color_head.pack_start(c_title_box, True, True, 0)

        self.lbl_active_color = Gtk.Label(label="● Current: #FFD700 (Yellow)")
        color_head.pack_end(self.lbl_active_color, False, False, 0)
        color_card.pack_start(color_head, False, False, 0)

        # Color Swatches Palette Box
        palette_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        color_card.pack_start(palette_box, False, False, 0)

        for name, hex_code, rgb in PRESET_COLORS:
            btn = Gtk.Button(label=f"● {name}")
            btn.get_style_context().add_class("swatch-btn")
            btn.connect("clicked", self.on_color_swatch_clicked, rgb, hex_code, name)
            palette_box.pack_start(btn, True, True, 0)

        # GTK Custom ColorChooserButton
        self.color_button = Gtk.ColorButton()
        color = Gdk.RGBA()
        color.parse("#ffd700")
        self.color_button.set_rgba(color)
        self.color_button.connect("color-set", self.on_custom_color_set)
        palette_box.pack_start(self.color_button, False, False, 0)

        # Mode Selector & Sliders
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        color_card.pack_start(mode_box, False, False, 0)

        self.rgb_combo = Gtk.ComboBoxText()
        effects = [
            ("2", "🌟 Static Solid Glow (Steady Single Color)"),
            ("1", "🫁 Breathing Pulse (Smooth Single-Color Pulse)"),
            ("4", "🌈 Rainbow Wave Stream (Flowing Colors)"),
            ("3", "⚡ Neon Spectrum Cycle"),
            ("5", "🎯 Click Reaction"),
            ("6", "✨ Twinkle Stars"),
            ("7", "🌊 Pulse Wave"),
            ("0", "🌑 Lights Off")
        ]
        for val, eff in effects:
            self.rgb_combo.append(val, eff)
        self.rgb_combo.set_active_id("2") # Static Solid Glow
        self.rgb_combo.connect("changed", self.on_rgb_param_changed)
        mode_box.pack_start(self.rgb_combo, True, True, 0)

        # Speed scale
        sp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        sp_box.pack_start(Gtk.Label(label="Speed:"), False, False, 0)
        self.scale_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 3, 1)
        self.scale_speed.set_value(2)
        self.scale_speed.connect("value-changed", self.on_rgb_param_changed)
        sp_box.pack_start(self.scale_speed, True, True, 0)
        mode_box.pack_start(sp_box, True, True, 0)

        # Brightness scale
        br_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        br_box.pack_start(Gtk.Label(label="Bright:"), False, False, 0)
        self.scale_bright = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 4, 1)
        self.scale_bright.set_value(4)
        self.scale_bright.connect("value-changed", self.on_rgb_param_changed)
        br_box.pack_start(self.scale_bright, True, True, 0)
        mode_box.pack_start(br_box, True, True, 0)

        # Action Buttons
        act_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_copy_all = Gtk.Button(label="Copy Color to All Stages")
        btn_copy_all.connect("clicked", self.on_copy_all_stages)
        act_box.pack_start(btn_copy_all, False, False, 0)

        color_card.pack_start(act_box, False, False, 0)

        # =====================================================================
        # DPI SENSITIVITY CARD
        # =====================================================================
        dpi_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        dpi_card.get_style_context().add_class("card")
        vbox.pack_start(dpi_card, False, False, 0)

        dpi_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        dpi_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        lbl_dpi_t = Gtk.Label(xalign=0, label="⚡ DPI Sensitivity (200 - 12,800 DPI)")
        lbl_dpi_t.get_style_context().add_class("title")
        lbl_dpi_s = Gtk.Label(xalign=0, label="Real-time optical sensor sensitivity. Amkette EvoFox Phantom Air.")
        lbl_dpi_s.get_style_context().add_class("subtitle")
        dpi_info.pack_start(lbl_dpi_t, False, False, 0)
        dpi_info.pack_start(lbl_dpi_s, False, False, 0)
        dpi_head.pack_start(dpi_info, True, True, 0)

        self.lbl_dpi_val = Gtk.Label(label="12,000 DPI")
        self.lbl_dpi_val.get_style_context().add_class("dpi-display")
        dpi_head.pack_end(self.lbl_dpi_val, False, False, 0)
        dpi_card.pack_start(dpi_head, False, False, 0)

        # Stage Buttons (1 to 6)
        stage_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.stage_btns = {}
        for s in range(1, 7):
            btn = Gtk.Button(label=f"Stage {s}\n{self.stage_dpis[s]}")
            btn.connect("clicked", self.on_stage_clicked, s)
            stage_box.pack_start(btn, True, True, 0)
            self.stage_btns[s] = btn
        dpi_card.pack_start(stage_box, False, False, 0)

        # DPI Slider
        self.dpi_slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, len(DPI_STEPS) - 1, 1)
        self.dpi_slider.set_draw_value(False)
        self.dpi_slider.set_value(len(DPI_STEPS) - 2) # 12,000 DPI (index 22)
        self.dpi_slider.connect("value-changed", self.on_slider_changed)
        dpi_card.pack_start(self.dpi_slider, False, False, 0)

        # Quick Presets
        presets_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for dpi in [800, 1600, 2400, 3200, 6400, 7200, 12000]:
            is_12k = (dpi == 12000)
            btn = Gtk.Button(label="🔥 12,000 DPI Preset" if is_12k else f"{dpi} DPI")
            btn.get_style_context().add_class("btn-12k" if is_12k else "btn-preset")
            btn.connect("clicked", self.on_preset_clicked, dpi)
            presets_box.pack_start(btn, True, True, 0)
        dpi_card.pack_start(presets_box, False, False, 0)

        # USB Polling Rate
        rate_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        rate_card.get_style_context().add_class("card")
        vbox.pack_start(rate_card, False, False, 0)

        lbl_rate_t = Gtk.Label(label="⏱️ Polling Rate:")
        lbl_rate_t.get_style_context().add_class("title")
        rate_card.pack_start(lbl_rate_t, False, False, 0)

        self.rate_btns = {}
        for rate in [125, 250, 500, 1000]:
            btn = Gtk.Button(label=f"{rate} Hz" if rate != 1000 else "1000 Hz (1ms)")
            btn.connect("clicked", self.on_rate_clicked, rate)
            rate_card.pack_start(btn, True, True, 0)
            self.rate_btns[rate] = btn

        # =====================================================================
        # BUTTON ASSIGNMENT & KEY REMAPPING CARD
        # =====================================================================
        btn_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        btn_card.get_style_context().add_class("card")
        vbox.pack_start(btn_card, False, False, 0)

        btn_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        b_title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        lbl_b_t = Gtk.Label(xalign=0, label="🎮 Button Assignment & Key Remapping")
        lbl_b_t.get_style_context().add_class("title")
        lbl_b_s = Gtk.Label(xalign=0, label="Remap all 6 buttons: Rapid Fire, Macros, Media, DPI, or Custom actions.")
        lbl_b_s.get_style_context().add_class("subtitle")
        b_title_box.pack_start(lbl_b_t, False, False, 0)
        b_title_box.pack_start(lbl_b_s, False, False, 0)
        btn_head.pack_start(b_title_box, True, True, 0)

        self.lbl_btn_status = Gtk.Label(label="● Ready")
        self.lbl_btn_status.get_style_context().add_class("subtitle")
        btn_head.pack_end(self.lbl_btn_status, False, False, 0)
        btn_card.pack_start(btn_head, False, False, 0)

        # 2-column Grid for Button Selectors
        grid = Gtk.Grid()
        grid.set_column_spacing(14)
        grid.set_row_spacing(8)
        grid.set_column_homogeneous(True)
        btn_card.pack_start(grid, False, False, 0)

        btn_layout = [
            (1, "Button 1 (Left Click)", 0, 0),
            (2, "Button 2 (Right Click)", 1, 0),
            (3, "Button 3 (Middle / Scroll)", 0, 1),
            (4, "Button 4 (Side Forward)", 1, 1),
            (5, "Button 5 (Side Backward)", 0, 2),
            (6, "Button 6 (Top DPI Button)", 1, 2),
        ]

        for btn_id, label_text, col, row in btn_layout:
            b_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            b_lbl = Gtk.Label(xalign=0, label=label_text)
            b_lbl.get_style_context().add_class("subtitle")
            b_box.pack_start(b_lbl, False, False, 0)

            combo = Gtk.ComboBoxText()
            for code, name in BUTTON_ACTIONS:
                combo.append(str(code), name)
            combo.set_active_id(str(self.button_mapping[btn_id]))
            combo.connect("changed", self.on_button_changed, btn_id)
            self.button_combos[btn_id] = combo
            b_box.pack_start(combo, True, True, 0)
            grid.attach(b_box, col, row, 1, 1)

        # Presets Bar
        preset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        presets = [
            ("↺ Default", "default"),
            ("🎯 Gaming (Rapid Fire on B4)", "gaming"),
            ("🎵 Media (Vol +/- & Play)", "media"),
            ("💡 LED Switcher (B6 = LED)", "rgb"),
        ]
        for name, p_id in presets:
            btn = Gtk.Button(label=name)
            btn.get_style_context().add_class("btn-preset")
            btn.connect("clicked", self.on_preset_button_clicked, p_id)
            preset_box.pack_start(btn, True, True, 0)
        btn_card.pack_start(preset_box, False, False, 0)

        self.update_styles()

    def periodic_check(self):
        self.refresh_status()
        return True

    def refresh_status(self):
        dev = find_mouse_device()
        ok, msg, _ = check_permission()
        if not dev:
            self.lbl_status.set_markup("<span color='#ef4444'>● Mouse Disconnected (30FA:1440 not found)</span>")
            self.perm_box.set_visible(False)
        elif not ok:
            self.lbl_status.set_markup(f"<span color='#f59e0b'>● Mouse Detected ({dev}) — Permission Required</span>")
            self.perm_box.set_visible(True)
        else:
            self.lbl_status.set_markup(f"<span color='#10b981'>● Mouse Connected &amp; Ready ({dev})</span>")
            self.perm_box.set_visible(False)

    def update_styles(self):
        for s, btn in self.stage_btns.items():
            btn.set_label(f"Stage {s}\n{self.stage_dpis[s]}")
            ctx = btn.get_style_context()
            if s == self.active_stage:
                ctx.add_class("btn-active")
            else:
                ctx.remove_class("btn-active")

        for r, btn in self.rate_btns.items():
            ctx = btn.get_style_context()
            if r == self.active_rate:
                ctx.add_class("btn-active")
            else:
                ctx.remove_class("btn-active")

    def on_color_swatch_clicked(self, _btn, rgb, hex_code, name):
        self.current_rgb = rgb
        self.stage_colors[self.active_stage] = rgb
        self.lbl_active_color.set_text(f"● Current: {hex_code.upper()} ({name})")
        color = Gdk.RGBA()
        color.parse(hex_code)
        self.color_button.set_rgba(color)
        self.queue_live_color()

    def on_custom_color_set(self, btn):
        rgba = btn.get_rgba()
        rgb = (int(rgba.red * 255), int(rgba.green * 255), int(rgba.blue * 255))
        hex_code = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        self.current_rgb = rgb
        self.stage_colors[self.active_stage] = rgb
        self.lbl_active_color.set_text(f"● Current: {hex_code} (Custom)")
        self.queue_live_color()

    def on_copy_all_stages(self, _btn):
        for s in range(1, 7):
            self.stage_colors[s] = self.current_rgb
        self.queue_live_color()

    def on_rgb_param_changed(self, *_args):
        self.queue_live_color()

    def queue_live_color(self):
        """Debounce real-time color packet transmission (30ms). Never saves to flash on live preview."""
        if self._color_timer:
            GLib.source_remove(self._color_timer)
        self._color_timer = GLib.timeout_add(30, self._send_live_color_now)

    def _send_live_color_now(self):
        self._color_timer = None
        r, g, b = self.current_rgb
        g4 = (g >> 4) & 0x0F
        r4 = (r >> 4) & 0x0F
        b4 = (b >> 4) & 0x0F

        # 1. Send Stage LED Color packet (0x14) - Instant A825 nibble layout:
        # byte 2 = ((stage - 1) << 5) | (G >> 4)
        # byte 3 = ((R >> 4) << 4) | (B >> 4)
        pkt_color = [REPORT_ID, 0x14, ((self.active_stage - 1) << 5) | g4, (r4 << 4) | b4, 0, 0, 0, 0]
        send_packet(pkt_color)

        # 2. Activate Stage in real time (0x10)
        pkt_stage = [REPORT_ID, 0x10, 0x01, self.active_stage - 1, 0, 0, 0, 0]
        send_packet(pkt_stage)

        # 3. Send RGB Mode (0x13)
        mode_id = self.rgb_combo.get_active_id() or "2"
        mode = int(mode_id)
        speed = int(self.scale_speed.get_value())
        bright = int(self.scale_bright.get_value())
        b_val = 0x80 | (((bright - 1) & 0x03) << 4)
        pkt_rgb = [REPORT_ID, 0x13, (mode | 0x80) & 0xFF, speed & 0x07, b_val, 0, 0, 0]
        send_packet(pkt_rgb)
        return False

    def on_stage_clicked(self, _btn, stage):
        self.active_stage = stage
        self.active_dpi = self.stage_dpis[stage]
        self.lbl_dpi_val.set_text(f"{self.active_dpi:,} DPI")

        self._is_updating = True
        if self.active_dpi in DPI_STEPS:
            self.dpi_slider.set_value(DPI_STEPS.index(self.active_dpi))
        self._is_updating = False

        self.current_rgb = self.stage_colors.get(stage, (255, 215, 0))
        hex_code = f"#{self.current_rgb[0]:02X}{self.current_rgb[1]:02X}{self.current_rgb[2]:02X}"
        self.lbl_active_color.set_text(f"● Stage {stage}: {hex_code}")
        self.update_styles()

        # Send activate stage in real time
        send_packet([REPORT_ID, 0x10, 0x01, stage - 1, 0, 0, 0, 0])
        self.queue_live_color()

    def on_slider_changed(self, scale):
        if self._is_updating:
            return
        idx = int(scale.get_value())
        dpi = DPI_STEPS[idx]
        self.active_dpi = dpi
        self.stage_dpis[self.active_stage] = dpi
        self.lbl_dpi_val.set_text(f"{dpi:,} DPI")
        self.update_styles()

        if self._dpi_timer:
            GLib.source_remove(self._dpi_timer)
        self._dpi_timer = GLib.timeout_add(30, lambda: self._send_live_dpi_now(dpi) or False)

    def _send_live_dpi_now(self, dpi):
        self._dpi_timer = None
        hw_idx, _ = dpi_to_index(dpi)
        send_packet([REPORT_ID, 0x10, hw_idx, 0, 0, 0, 0, 0])
        send_packet([REPORT_ID, 0x10, 0x01, self.active_stage - 1, 0, 0, 0, 0])
        return False

    def on_preset_clicked(self, _btn, dpi):
        self.active_dpi = dpi
        self.stage_dpis[self.active_stage] = dpi
        self.lbl_dpi_val.set_text(f"{dpi:,} DPI")

        self._is_updating = True
        if dpi in DPI_STEPS:
            self.dpi_slider.set_value(DPI_STEPS.index(dpi))
        self._is_updating = False

        self.update_styles()
        hw_idx, _ = dpi_to_index(dpi)
        send_packet([REPORT_ID, 0x10, hw_idx, 0, 0, 0, 0, 0])
        send_packet([REPORT_ID, 0x10, 0x01, self.active_stage - 1, 0, 0, 0, 0])

    def on_rate_clicked(self, _btn, rate):
        self.active_rate = rate
        self.update_styles()
        codes = {1000: 0x00, 500: 0x01, 250: 0x03, 125: 0x07}
        send_packet([REPORT_ID, 0x11, codes.get(rate, 0x00), 0, 0, 0, 0, 0])

    def on_button_changed(self, combo, btn_id):
        if self._is_updating:
            return
        act_id = int(combo.get_active_id() or 1)
        self.button_mapping[btn_id] = act_id
        self.queue_live_buttons()

    def on_preset_button_clicked(self, _btn, preset):
        self._is_updating = True
        if preset == "default":
            self.button_mapping = {1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 6}
        elif preset == "gaming":
            self.button_mapping = {1: 1, 2: 2, 3: 3, 4: 14, 5: 4, 6: 6}
        elif preset == "media":
            self.button_mapping = {1: 1, 2: 2, 3: 3, 4: 21, 5: 22, 6: 27}
        elif preset == "rgb":
            self.button_mapping = {1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 19}

        for btn_id, combo in self.button_combos.items():
            combo.set_active_id(str(self.button_mapping[btn_id]))
        self._is_updating = False
        self.queue_live_buttons()

    def queue_live_buttons(self):
        """Debounce button mapping packet transmission (30ms)."""
        if self._btn_timer:
            GLib.source_remove(self._btn_timer)
        self._btn_timer = GLib.timeout_add(30, self._send_live_buttons_now)

    def _send_live_buttons_now(self):
        self._btn_timer = None
        b1 = self.button_mapping.get(1, 1)
        b2 = self.button_mapping.get(2, 2)
        b3 = self.button_mapping.get(3, 3)
        b4 = self.button_mapping.get(4, 5)
        b5 = self.button_mapping.get(5, 4)
        b6 = self.button_mapping.get(6, 6)

        # Instant A825 hardware format:
        # buf[2] = b1 (Left)
        # buf[3] = b3 (Middle)
        # buf[4] = b2 (Right)
        # buf[5] = b4 (Forward)
        # buf[6] = b5 (Backward)
        # buf[7] = b6 (DPI)
        pkt = [REPORT_ID, 0x15, b1, b3, b2, b4, b5, b6]
        ok, msg = send_packet(pkt)
        if hasattr(self, 'lbl_btn_status'):
            if ok:
                self.lbl_btn_status.set_markup("<span color='#10b981'>● Live ✓</span>")
            else:
                self.lbl_btn_status.set_markup(f"<span color='#ef4444'>● {msg}</span>")
        return False

    def on_save_clicked(self, btn):
        """Explicitly commit settings to onboard Flash memory."""
        ok, msg = send_packet([REPORT_ID, 0x20, 0, 0, 0, 0, 0, 0])
        orig = btn.get_label()
        btn.set_label("✓ Saved to Flash!" if ok else "⚠️ Failed")
        GLib.timeout_add(1800, lambda: btn.set_label(orig) or False)


def main():
    win = EvoFoxApp()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == '__main__':
    main()
