#!/usr/bin/env python3
"""
evofox-gui: Real-Time Web GUI Control Center for EvoFox Phantom Air / Instant A825.
Features instant real-time color & DPI updates, dedicated Colour Change Interface,
12,000 DPI preset, and strictly isolates mouse communication without touching keyboards.
"""

import os
import sys
import json
import glob
import fcntl
import webbrowser
import threading
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8250
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
        # Strictly match only the mouse
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
    return candidates[-1] if candidates else None

def check_permission():
    dev = find_mouse_device()
    if not dev:
        return False, "Mouse Not Connected", None
    fd = None
    try:
        fd = os.open(dev, os.O_RDWR)
        return True, "Ready", dev
    except PermissionError:
        return False, "Permission Denied", dev
    except Exception as e:
        return False, str(e), dev
    finally:
        if fd is not None:
            os.close(fd)

def send_packet(packet):
    """Send 8-byte HID Feature Report strictly to the mouse control node via ioctl. Never calls write."""
    dev = find_mouse_device()
    if not dev:
        return False, "EvoFox Phantom Air (30FA:1440) not found."

    buf = bytearray(8)
    for i, b in enumerate(packet[:8]):
        buf[i] = b

    fd = None
    try:
        fd = os.open(dev, os.O_RDWR)
        fcntl.ioctl(fd, HIDIOCSFEATURE_8, buf)
        return True, "OK"
    except PermissionError:
        return False, f"Permission Denied on {dev}. Run fix-permissions.sh."
    except Exception as e:
        return False, str(e)
    finally:
        if fd is not None:
            os.close(fd)

def save_hardware():
    return send_packet([REPORT_ID, 0x20, 0, 0, 0, 0, 0, 0])

def fix_permissions_polkit():
    cmd = [
        'pkexec', 'sh', '-c',
        'cat << \'EOF\' > /etc/udev/rules.d/99-evofox.rules\n'
        'KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="30fa", ATTRS{idProduct}=="1440", TAG+="uaccess", GROUP="input", MODE="0660"\n'
        'EOF\n'
        'udevadm control --reload-rules && udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=30fa 2>/dev/null || true\n'
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return True, "Secure permissions configured strictly for mouse!"
        return False, res.stderr or "Authorization canceled."
    except Exception as e:
        return False, str(e)

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EvoFox Phantom Air - Real-Time Control Center</title>
  <style>
    :root {
      --bg: #0b0f19; --panel: #151d30; --panel-alt: #1a243c; --border: #23314f; --text: #f1f5f9;
      --muted: #94a3b8; --accent: #6366f1; --accent-glow: rgba(99, 102, 241, 0.4);
      --green: #10b981; --cyan: #06b6d4; --pink: #ec4899; --amber: #f59e0b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 20px; display: flex; justify-content: center; }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; max-width: 800px; width: 100%; box-shadow: 0 10px 30px rgba(0,0,0,0.5); overflow: hidden; }
    .header { padding: 18px 24px; background: linear-gradient(135deg, #1e1b4b, #2b103e); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
    .badge { font-size: 11px; padding: 5px 12px; border-radius: 20px; background: rgba(16,185,129,0.15); color: var(--green); border: 1px solid rgba(16,185,129,0.3); font-weight: 600; }
    .badge-warn { background: rgba(245,158,11,0.15); color: var(--amber); border-color: rgba(245,158,11,0.3); }
    .badge-err { background: rgba(239,68,68,0.15); color: #ef4444; border-color: rgba(239,68,68,0.3); }
    .content { padding: 22px; display: flex; flex-direction: column; gap: 18px; }
    .section { background: rgba(11,15,25,0.65); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }
    .sec-title { font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 8px; margin-bottom: 12px; color: #f8fafc; }
    .grid-6 { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
    .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
    button { background: #1e293b; border: 1px solid var(--border); color: var(--text); padding: 10px; border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; }
    button:hover { border-color: var(--accent); }
    button.active { background: rgba(99,102,241,0.25); border-color: var(--accent); color: #c7d2fe; box-shadow: 0 0 12px var(--accent-glow); }
    .btn-save { background: linear-gradient(135deg, #059669, #0d9488); border: none; padding: 10px 22px; color: white; border-radius: 8px; font-weight: 800; cursor: pointer; transition: 0.2s; }
    .btn-save:hover { opacity: 0.95; transform: scale(1.02); }
    .btn-unlock { background: #d97706; border: none; padding: 7px 14px; color: white; border-radius: 6px; font-size: 12px; font-weight: bold; cursor: pointer; }
    .slider { width: 100%; height: 6px; border-radius: 5px; background: #334155; outline: none; accent-color: var(--accent); }
    select { width: 100%; padding: 10px; border-radius: 8px; background: #1e293b; border: 1px solid var(--border); color: var(--text); font-size: 13px; outline: none; }
    .dpi-disp { font-family: monospace; font-size: 22px; font-weight: 900; color: #818cf8; background: rgba(0,0,0,0.4); padding: 6px 14px; border-radius: 8px; border: 1px solid #312e81; }
    .alert-bar { background: #3b1700; border: 1px solid #b45309; border-radius: 10px; padding: 12px 16px; display: none; align-items: center; justify-content: space-between; font-size: 12px; color: #fef3c7; }
    .toast { position: fixed; bottom: 20px; right: 20px; background: #064e3b; color: #6ee7b7; border: 1px solid #059669; padding: 12px 20px; border-radius: 8px; font-size: 13px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); opacity: 0; transition: 0.3s; pointer-events: none; }
    .toast.show { opacity: 1; transform: translateY(-5px); }
    .btn-12k { background: #311042; border-color: #a855f7; color: #e9d5ff; font-weight: bold; }
    .btn-12k:hover { background: #4a1564; }

    /* Colour Change Interface Styles */
    .color-swatch-btn {
      width: 38px; height: 38px; border-radius: 50%; border: 2px solid #334155; cursor: pointer; transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s; outline: none; padding: 0;
    }
    .color-swatch-btn:hover { transform: scale(1.15); border-color: #ffffff; }
    .color-swatch-btn.selected { transform: scale(1.15); border-color: #ffffff; box-shadow: 0 0 14px currentColor; }
    
    .color-preview-sphere {
      width: 54px; height: 54px; border-radius: 50%; border: 3px solid rgba(255,255,255,0.3); box-shadow: 0 0 20px rgba(99,102,241,0.6); transition: all 0.2s ease; flex-shrink: 0;
    }
    .stage-color-pill {
      display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: #1a243c; border: 1px solid var(--border); border-radius: 8px; font-size: 12px; cursor: pointer; transition: 0.2s;
    }
    .stage-color-pill:hover, .stage-color-pill.active { border-color: var(--accent); background: #223050; }
    .stage-dot { width: 14px; height: 14px; border-radius: 50%; border: 1px solid rgba(255,255,255,0.4); flex-shrink: 0; }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div>
        <h1 style="font-size: 18px; font-weight: 800;">EvoFox Phantom Air</h1>
        <div style="font-size: 12px; color: var(--muted); margin-top: 2px;">Instant A825 SoC &bull; Real-Time Linux Control</div>
      </div>
      <div style="display: flex; align-items: center; gap: 12px;">
        <span id="devBadge" class="badge">Checking connection...</span>
        <button class="btn-save" onclick="saveToHardware()">💾 Save to Flash</button>
      </div>
    </div>

    <div class="content">
      <!-- Permission Alert -->
      <div class="alert-bar" id="permBar">
        <div>
          <b>⚠️ Permission Required:</b> Mouse requires non-root access permissions. Click to unlock once.
        </div>
        <button class="btn-unlock" onclick="unlockPermissions()">🔓 Unlock with Password</button>
      </div>

      <!-- =================================================================== -->
      <!-- REAL-TIME COLOUR CHANGE INTERFACE                                   -->
      <!-- =================================================================== -->
      <div class="section" style="border-color: #4f46e5; background: linear-gradient(180deg, rgba(30, 27, 75, 0.4), rgba(11, 15, 25, 0.7));">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
          <div>
            <div class="sec-title" style="margin-bottom: 2px; color: #a5b4fc; font-size: 14px;">
              🎨 Colour Change Interface (Real-Time Live)
            </div>
            <div style="font-size: 11px; color: var(--muted);">
              Instant hardware illumination on click. Only mouse hardware is controlled.
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <div class="color-preview-sphere" id="colorPreviewSphere" style="background-color: #00ffff; box-shadow: 0 0 20px #00ffff;"></div>
            <div style="text-align: right;">
              <div id="colorHexText" style="font-family: monospace; font-size: 14px; font-weight: bold; color: #f8fafc;">#00FFFF</div>
              <div id="colorNameText" style="font-size: 11px; color: var(--muted);">Electric Cyan</div>
            </div>
          </div>
        </div>

        <!-- Color Palette Swatches -->
        <div style="margin-bottom: 14px;">
          <div style="font-size: 11px; color: var(--muted); font-weight: 600; margin-bottom: 8px;">INSTANT COLOR PALETTE:</div>
          <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
            <button class="color-swatch-btn" style="background-color: #ff0033;" onclick="selectColor('#ff0033', 'Crimson Red')" title="Crimson Red"></button>
            <button class="color-swatch-btn" style="background-color: #ff6600;" onclick="selectColor('#ff6600', 'Vivid Orange')" title="Vivid Orange"></button>
            <button class="color-swatch-btn" style="background-color: #ffd700;" onclick="selectColor('#ffd700', 'Electric Yellow')" title="Electric Yellow"></button>
            <button class="color-swatch-btn" style="background-color: #00ff33;" onclick="selectColor('#00ff33', 'Lime Green')" title="Lime Green"></button>
            <button class="color-swatch-btn" style="background-color: #00e5a3;" onclick="selectColor('#00e5a3', 'Emerald Mint')" title="Emerald Mint"></button>
            <button class="color-swatch-btn selected" style="background-color: #00ffff;" onclick="selectColor('#00ffff', 'Electric Cyan')" title="Electric Cyan"></button>
            <button class="color-swatch-btn" style="background-color: #0055ff;" onclick="selectColor('#0055ff', 'Royal Blue')" title="Royal Blue"></button>
            <button class="color-swatch-btn" style="background-color: #8800ff;" onclick="selectColor('#8800ff', 'Neon Purple')" title="Neon Purple"></button>
            <button class="color-swatch-btn" style="background-color: #ff00aa;" onclick="selectColor('#ff00aa', 'Hot Pink / Magenta')" title="Hot Pink"></button>
            <button class="color-swatch-btn" style="background-color: #ffffff;" onclick="selectColor('#ffffff', 'Crisp White')" title="Pure White"></button>
            
            <div style="display: flex; align-items: center; gap: 6px; margin-left: 8px; background: #1a243c; padding: 4px 8px; border-radius: 8px; border: 1px solid var(--border);">
              <input type="color" id="nativeColorPicker" value="#00ffff" oninput="onCustomColorPick(this.value)" style="border: none; width: 28px; height: 28px; background: transparent; cursor: pointer;">
              <span style="font-size: 11px; color: var(--muted); cursor: pointer;" onclick="document.getElementById('nativeColorPicker').click()">Custom RGB</span>
            </div>
          </div>
        </div>

        <!-- Lighting Mode Options -->
        <div class="grid-2" style="margin-bottom: 14px;">
          <div>
            <div style="font-size: 11px; color: var(--muted); font-weight: 600; margin-bottom: 6px;">LIGHTING STYLE:</div>
            <select id="rgbEffectSelect" onchange="sendLiveColor()">
              <option value="2" selected>🌟 Static Solid Glow (Steady Single Color)</option>
              <option value="1">🫁 Breathing Pulse (Smooth Single-Color Pulse)</option>
              <option value="4">🌈 Rainbow Wave Stream (Flowing Colors)</option>
              <option value="3">⚡ Neon Spectrum Cycle</option>
              <option value="5">🎯 Click Reaction</option>
              <option value="6">✨ Twinkle / Stars</option>
              <option value="7">🌊 Pulse Wave</option>
              <option value="0">🌑 Lights Off</option>
            </select>
          </div>
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); margin-bottom: 6px;">
              <span>Speed (1-3) &bull; Brightness (1-4)</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
              <input type="range" class="slider" id="effectSpeed" min="1" max="3" value="2" oninput="sendLiveColor()" title="Speed">
              <input type="range" class="slider" id="effectBright" min="1" max="4" value="4" oninput="sendLiveColor()" title="Brightness">
            </div>
          </div>
        </div>

        <!-- Per-Stage Color Map -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 11px; color: var(--muted); font-weight: 600;">PER-STAGE HARDWARE LED COLOR:</div>
            <button onclick="applyColorToAllStages()" style="padding: 4px 10px; font-size: 11px; background: #1a243c; border-color: var(--accent);">Copy Color to All Stages</button>
          </div>
          <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px;" id="stageColorList">
            <div class="stage-color-pill" onclick="selectStage(1)" id="scPill1"><div class="stage-dot" id="scDot1" style="background:#ff0033;"></div>S1: 800</div>
            <div class="stage-color-pill" onclick="selectStage(2)" id="scPill2"><div class="stage-dot" id="scDot2" style="background:#00ff33;"></div>S2: 1600</div>
            <div class="stage-color-pill" onclick="selectStage(3)" id="scPill3"><div class="stage-dot" id="scDot3" style="background:#0055ff;"></div>S3: 2400</div>
            <div class="stage-color-pill" onclick="selectStage(4)" id="scPill4"><div class="stage-dot" id="scDot4" style="background:#ff00aa;"></div>S4: 3200</div>
            <div class="stage-color-pill" onclick="selectStage(5)" id="scPill5"><div class="stage-dot" id="scDot5" style="background:#00ffff;"></div>S5: 4800</div>
            <div class="stage-color-pill active" onclick="selectStage(6)" id="scPill6"><div class="stage-dot" id="scDot6" style="background:#ffd700;"></div>S6: 12k</div>
          </div>
        </div>
      </div>

      <!-- DPI Sensitivity -->
      <div class="section">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <div class="sec-title" style="margin-bottom: 2px;">⚡ DPI Sensitivity (200 - 12,800 DPI)</div>
            <div style="font-size: 11px; color: var(--muted);">Real-time sensor sensitivity change. Instant A825.</div>
          </div>
          <div class="dpi-disp" id="dpiDisplay">12,000 DPI</div>
        </div>

        <div style="margin-bottom: 8px; font-size: 11px; color: var(--muted); font-weight: 600;">ACTIVE DPI STAGE:</div>
        <div class="grid-6" style="margin-bottom: 14px;">
          <button id="sbtn1" class="stage-btn" onclick="selectStage(1)">Stage 1<br><span style="font-size: 10px; opacity: 0.8;" id="sl1">800</span></button>
          <button id="sbtn2" class="stage-btn" onclick="selectStage(2)">Stage 2<br><span style="font-size: 10px; opacity: 0.8;" id="sl2">1600</span></button>
          <button id="sbtn3" class="stage-btn" onclick="selectStage(3)">Stage 3<br><span style="font-size: 10px; opacity: 0.8;" id="sl3">2400</span></button>
          <button id="sbtn4" class="stage-btn" onclick="selectStage(4)">Stage 4<br><span style="font-size: 10px; opacity: 0.8;" id="sl4">3200</span></button>
          <button id="sbtn5" class="stage-btn" onclick="selectStage(5)">Stage 5<br><span style="font-size: 10px; opacity: 0.8;" id="sl5">4800</span></button>
          <button id="sbtn6" class="stage-btn active" onclick="selectStage(6)">Stage 6<br><span style="font-size: 10px; opacity: 0.8;" id="sl6">12000</span></button>
        </div>

        <div style="margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); margin-bottom: 6px;">
            <span>200 DPI</span>
            <span style="color: #818cf8; font-weight: bold;">Real-Time Slider</span>
            <span>12,800 DPI</span>
          </div>
          <input type="range" class="slider" id="dpiSlider" min="0" max="23" value="22" oninput="onLiveSlider(this.value)">
        </div>

        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
          <button onclick="setDpiPreset(800)">800 DPI</button>
          <button onclick="setDpiPreset(1600)">1600 DPI</button>
          <button onclick="setDpiPreset(2400)">2400 DPI</button>
          <button onclick="setDpiPreset(3200)">3200 DPI</button>
          <button onclick="setDpiPreset(6400)">6400 DPI</button>
          <button onclick="setDpiPreset(7200)">7200 DPI</button>
          <button class="btn-12k" onclick="setDpiPreset(12000)">🔥 12,000 DPI Preset</button>
        </div>
      </div>

      <!-- USB Polling Rate -->
      <div class="section">
        <div class="sec-title">⏱️ USB Polling Rate</div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;">
          <button class="rate-btn" data-rate="125" onclick="selectRate(125)">125 Hz (8ms)</button>
          <button class="rate-btn" data-rate="250" onclick="selectRate(250)">250 Hz (4ms)</button>
          <button class="rate-btn" data-rate="500" onclick="selectRate(500)">500 Hz (2ms)</button>
          <button class="rate-btn active" data-rate="1000" onclick="selectRate(1000)">1000 Hz (1ms Ultra Fast)</button>
        </div>
      </div>

      <!-- Button Assignment (Key Programming) -->
      <div class="section" style="border-color: #0d9488; background: linear-gradient(180deg, rgba(13, 148, 136, 0.1), rgba(11, 15, 25, 0.7));">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <div class="sec-title" style="margin-bottom: 2px; color: #2dd4bf;">🎮 Button Assignment &amp; Key Remapping</div>
            <div style="font-size: 11px; color: var(--muted);">Program any of the 6 mouse buttons with gaming, media, or macro actions.</div>
          </div>
          <button onclick="resetDefaultButtons()" style="font-size: 11px; padding: 6px 12px; background: #1a243c; border-color: var(--border);">↺ Reset Defaults</button>
        </div>

        <div class="grid-2" style="margin-bottom: 12px;">
          <div>
            <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600;">BUTTON 1 (Left Click):</div>
            <select id="btn1Select" onchange="onButtonChange()">
              <option value="1" selected>🖱️ Left Click (Default)</option>
              <option value="2">🖱️ Right Click</option>
              <option value="3">🖱️ Middle Click</option>
              <option value="14">🔥 Rapid Fire (Triple Click)</option>
              <option value="15">⚡ Double Click</option>
              <option value="50">❌ Disabled</option>
            </select>
          </div>
          <div>
            <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600;">BUTTON 2 (Right Click):</div>
            <select id="btn2Select" onchange="onButtonChange()">
              <option value="2" selected>🖱️ Right Click (Default)</option>
              <option value="1">🖱️ Left Click</option>
              <option value="3">🖱️ Middle Click</option>
              <option value="5">🌐 Browser Forward</option>
              <option value="4">🌐 Browser Backward</option>
              <option value="6">⚡ DPI Loop</option>
              <option value="14">🔥 Rapid Fire (Triple Click)</option>
              <option value="15">⚡ Double Click</option>
              <option value="19">💡 LED Mode Switch</option>
              <option value="21">🔊 Volume Up</option>
              <option value="22">🔉 Volume Down</option>
              <option value="20">🔇 Mute</option>
              <option value="30">🖥️ Show Desktop</option>
              <option value="50">❌ Disabled</option>
            </select>
          </div>
          <div>
            <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600;">BUTTON 3 (Scroll Wheel Click):</div>
            <select id="btn3Select" onchange="onButtonChange()">
              <option value="3" selected>🖱️ Middle Click (Default)</option>
              <option value="1">🖱️ Left Click</option>
              <option value="2">🖱️ Right Click</option>
              <option value="5">🌐 Browser Forward</option>
              <option value="4">🌐 Browser Backward</option>
              <option value="6">⚡ DPI Loop</option>
              <option value="16">⚡ DPI + (Step Up)</option>
              <option value="17">⚡ DPI - (Step Down)</option>
              <option value="14">🔥 Rapid Fire (Triple Click)</option>
              <option value="15">⚡ Double Click</option>
              <option value="19">💡 LED Mode Switch</option>
              <option value="27">⏯️ Play / Pause</option>
              <option value="21">🔊 Volume Up</option>
              <option value="22">🔉 Volume Down</option>
              <option value="20">🔇 Mute</option>
              <option value="30">🖥️ Show Desktop</option>
              <option value="50">❌ Disabled</option>
            </select>
          </div>
          <div>
            <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600;">BUTTON 4 (Side Forward Button):</div>
            <select id="btn4Select" onchange="onButtonChange()">
              <option value="5" selected>🌐 Forward / Next (Default)</option>
              <option value="4">🌐 Backward / Previous</option>
              <option value="1">🖱️ Left Click</option>
              <option value="2">🖱️ Right Click</option>
              <option value="3">🖱️ Middle Click</option>
              <option value="14">🔥 Rapid Fire (Triple Click)</option>
              <option value="15">⚡ Double Click</option>
              <option value="6">⚡ DPI Loop</option>
              <option value="16">⚡ DPI + (Step Up)</option>
              <option value="17">⚡ DPI - (Step Down)</option>
              <option value="19">💡 LED Mode Switch</option>
              <option value="21">🔊 Volume Up</option>
              <option value="22">🔉 Volume Down</option>
              <option value="20">🔇 Mute</option>
              <option value="25">⏭️ Next Track</option>
              <option value="26">⏮️ Previous Track</option>
              <option value="27">⏯️ Play / Pause</option>
              <option value="30">🖥️ Show Desktop</option>
              <option value="50">❌ Disabled</option>
            </select>
          </div>
          <div>
            <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600;">BUTTON 5 (Side Backward Button):</div>
            <select id="btn5Select" onchange="onButtonChange()">
              <option value="4" selected>🌐 Backward / Prev (Default)</option>
              <option value="5">🌐 Forward / Next</option>
              <option value="1">🖱️ Left Click</option>
              <option value="2">🖱️ Right Click</option>
              <option value="3">🖱️ Middle Click</option>
              <option value="14">🔥 Rapid Fire (Triple Click)</option>
              <option value="15">⚡ Double Click</option>
              <option value="6">⚡ DPI Loop</option>
              <option value="16">⚡ DPI + (Step Up)</option>
              <option value="17">⚡ DPI - (Step Down)</option>
              <option value="19">💡 LED Mode Switch</option>
              <option value="22">🔉 Volume Down</option>
              <option value="21">🔊 Volume Up</option>
              <option value="20">🔇 Mute</option>
              <option value="26">⏮️ Previous Track</option>
              <option value="25">⏭️ Next Track</option>
              <option value="27">⏯️ Play / Pause</option>
              <option value="30">🖥️ Show Desktop</option>
              <option value="50">❌ Disabled</option>
            </select>
          </div>
          <div>
            <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px; font-weight: 600;">BUTTON 6 (Top DPI Button):</div>
            <select id="btn6Select" onchange="onButtonChange()">
              <option value="6" selected>⚡ DPI Loop (Default)</option>
              <option value="16">⚡ DPI + (Step Up)</option>
              <option value="17">⚡ DPI - (Step Down)</option>
              <option value="19">💡 LED Mode Switch</option>
              <option value="14">🔥 Rapid Fire (Triple Click)</option>
              <option value="15">⚡ Double Click</option>
              <option value="3">🖱️ Middle Click</option>
              <option value="20">🔇 Mute</option>
              <option value="21">🔊 Volume Up</option>
              <option value="22">🔉 Volume Down</option>
              <option value="27">⏯️ Play / Pause</option>
              <option value="30">🖥️ Show Desktop</option>
              <option value="50">❌ Disabled</option>
            </select>
          </div>
        </div>

        <div style="display: flex; gap: 8px;">
          <button onclick="setButtonPreset('gaming')" style="font-size: 11px; padding: 6px 12px; background: #1a243c;">🎯 Preset: Gaming (Rapid Fire on B4)</button>
          <button onclick="setButtonPreset('media')" style="font-size: 11px; padding: 6px 12px; background: #1a243c;">🎵 Preset: Media (Vol +/- on Side)</button>
          <button onclick="setButtonPreset('rgb')" style="font-size: 11px; padding: 6px 12px; background: #1a243c;">💡 Preset: LED Switcher (B6=LED)</button>
        </div>
      </div>

    </div>
  </div>

  <div class="toast" id="toast">Settings applied!</div>

  <script>
    const STEPS = [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000, 2400, 3200, 4000, 4800, 5600, 6400, 7200, 8000, 8800, 9600, 10400, 11200, 12000, 12800];
    let activeStage = 6;
    let activeDpi = 12000;
    let stageDpis = { 1: 800, 2: 1600, 3: 2400, 4: 3200, 5: 4800, 6: 12000 };
    let stageColors = { 1: '#ff0033', 2: '#00ff33', 3: '#0055ff', 4: '#ff00aa', 5: '#00ffff', 6: '#ffd700' };
    let currentColor = '#ffd700';
    let currentColorName = 'Electric Yellow';
    let activeRate = 1000;
    let currentButtons = { 1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 6 };

    function onButtonChange() {
      currentButtons[1] = parseInt(document.getElementById('btn1Select').value);
      currentButtons[2] = parseInt(document.getElementById('btn2Select').value);
      currentButtons[3] = parseInt(document.getElementById('btn3Select').value);
      currentButtons[4] = parseInt(document.getElementById('btn4Select').value);
      currentButtons[5] = parseInt(document.getElementById('btn5Select').value);
      currentButtons[6] = parseInt(document.getElementById('btn6Select').value);
      sendCommand('/api/buttons', currentButtons);
      showToast('Button mapping updated live! ✓');
    }

    function resetDefaultButtons() {
      currentButtons = { 1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 6 };
      for (let i = 1; i <= 6; i++) {
        document.getElementById(`btn${i}Select`).value = currentButtons[i];
      }
      onButtonChange();
    }

    function setButtonPreset(preset) {
      if (preset === 'gaming') {
        currentButtons = { 1: 1, 2: 2, 3: 3, 4: 14, 5: 4, 6: 6 }; // Rapid fire on B4
      } else if (preset === 'media') {
        currentButtons = { 1: 1, 2: 2, 3: 27, 4: 21, 5: 22, 6: 20 }; // Play/Pause B3, Vol+ B4, Vol- B5, Mute B6
      } else if (preset === 'rgb') {
        currentButtons = { 1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 19 }; // LED mode switch on B6
      }
      for (let i = 1; i <= 6; i++) {
        document.getElementById(`btn${i}Select`).value = currentButtons[i];
      }
      onButtonChange();
    }

    let debounceTimer = null;

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 1500);
    }

    function hexToRgb(hex) {
      let c = hex.replace('#', '');
      if (c.length === 3) c = c.split('').map(x => x + x).join('');
      const num = parseInt(c, 16);
      return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
    }

    function selectColor(hex, name) {
      currentColor = hex;
      currentColorName = name || hex;
      stageColors[activeStage] = hex;

      document.querySelectorAll('.color-swatch-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.getAttribute('style').includes(hex));
      });

      const sphere = document.getElementById('colorPreviewSphere');
      sphere.style.backgroundColor = hex;
      sphere.style.boxShadow = `0 0 22px ${hex}`;
      document.getElementById('colorHexText').innerText = hex.toUpperCase();
      document.getElementById('colorNameText').innerText = currentColorName;
      document.getElementById(`scDot${activeStage}`).style.backgroundColor = hex;
      document.getElementById('nativeColorPicker').value = hex;

      sendLiveColor();
    }

    function onCustomColorPick(hex) {
      selectColor(hex, 'Custom RGB');
    }

    function applyColorToAllStages() {
      for (let s = 1; s <= 6; s++) {
        stageColors[s] = currentColor;
        document.getElementById(`scDot${s}`).style.backgroundColor = currentColor;
      }
      sendLiveColor();
      showToast('Color set for all stages!');
    }

    function sendLiveColor() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(async () => {
        const rgb = hexToRgb(currentColor);
        const mode = parseInt(document.getElementById('rgbEffectSelect').value);
        const speed = parseInt(document.getElementById('effectSpeed').value);
        const bright = parseInt(document.getElementById('effectBright').value);

        await sendCommand('/api/color', {
          stage: activeStage,
          r: rgb.r,
          g: rgb.g,
          b: rgb.b,
          mode: mode,
          speed: speed,
          bright: bright
        });
      }, 40);
    }

    async function checkStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const b = document.getElementById('devBadge');
        const p = document.getElementById('permBar');
        if (data.connected && data.permission) {
          b.innerText = `● Connected (${data.node})`;
          b.className = 'badge';
          p.style.display = 'none';
        } else if (data.connected && !data.permission) {
          b.innerText = `● Mouse Detected (Permission Required)`;
          b.className = 'badge badge-warn';
          p.style.display = 'flex';
        } else {
          b.innerText = 'Disconnected (Mouse Not Found)';
          b.className = 'badge badge-err';
          p.style.display = 'none';
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function sendCommand(endpoint, body) {
      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        const data = await res.json();
        if (!data.success) {
          showToast('⚠️ ' + data.error);
        }
      } catch (e) {
        console.error('API error:', e);
      }
    }

    async function unlockPermissions() {
      showToast('Authenticating with Polkit...');
      try {
        const res = await fetch('/api/fix-permissions', { method: 'POST', body: '{}' });
        const data = await res.json();
        if (data.success) {
          showToast('Permissions unlocked! ✓');
          checkStatus();
        } else {
          alert('Could not unlock permissions: ' + data.error);
        }
      } catch (e) {
        alert('Polkit authentication error: ' + e);
      }
    }

    function selectStage(s) {
      activeStage = s;
      document.querySelectorAll('.stage-btn').forEach((b, idx) => {
        b.classList.toggle('active', (idx + 1) === s);
      });
      document.querySelectorAll('.stage-color-pill').forEach((p, idx) => {
        p.classList.toggle('active', (idx + 1) === s);
      });

      activeDpi = stageDpis[s];
      document.getElementById('dpiDisplay').innerText = activeDpi.toLocaleString() + ' DPI';
      const idx = STEPS.indexOf(activeDpi);
      if (idx !== -1) document.getElementById('dpiSlider').value = idx;

      // Update color preview to match stage's assigned color
      currentColor = stageColors[s] || '#ffd700';
      const sphere = document.getElementById('colorPreviewSphere');
      sphere.style.backgroundColor = currentColor;
      sphere.style.boxShadow = `0 0 22px ${currentColor}`;
      document.getElementById('colorHexText').innerText = currentColor.toUpperCase();

      sendCommand('/api/stage', { stage: s });
      sendLiveColor();
    }

    function onLiveSlider(val) {
      const dpi = STEPS[val];
      activeDpi = dpi;
      stageDpis[activeStage] = dpi;
      document.getElementById('sl' + activeStage).innerText = dpi;
      document.getElementById('dpiDisplay').innerText = dpi.toLocaleString() + ' DPI';

      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        sendCommand('/api/dpi', { stage: activeStage, dpi: dpi });
      }, 30);
    }

    function setDpiPreset(dpi) {
      activeDpi = dpi;
      stageDpis[activeStage] = dpi;
      document.getElementById('sl' + activeStage).innerText = dpi;
      document.getElementById('dpiDisplay').innerText = dpi.toLocaleString() + ' DPI';
      const idx = STEPS.indexOf(dpi);
      if (idx !== -1) document.getElementById('dpiSlider').value = idx;
      sendCommand('/api/dpi', { stage: activeStage, dpi: dpi });
    }

    function selectRate(r) {
      activeRate = r;
      document.querySelectorAll('.rate-btn').forEach(b => b.classList.toggle('active', parseInt(b.dataset.rate) === r));
      sendCommand('/api/rate', { rate: r });
    }

    async function saveToHardware() {
      await sendCommand('/api/save', {});
      showToast('Settings saved to mouse onboard flash memory! ✓');
    }

    checkStatus();
    setInterval(checkStatus, 2000);
  </script>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif self.path == '/api/status':
            dev = find_mouse_device()
            ok, pmsg, _ = check_permission()
            resp = {
                'connected': dev is not None,
                'permission': ok,
                'perm_msg': pmsg,
                'node': dev or 'None',
                'vid': f'0x{TARGET_VID:04X}',
                'pid': f'0x{TARGET_PID:04X}'
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        data = self.rfile.read(length)
        body = json.loads(data) if data else {}

        if self.path == '/api/buttons':
            b1 = int(body.get('1', body.get('b1', 1)))
            b2 = int(body.get('2', body.get('b2', 2)))
            b3 = int(body.get('3', body.get('b3', 3)))
            b4 = int(body.get('4', body.get('b4', 5)))
            b5 = int(body.get('5', body.get('b5', 4)))
            b6 = int(body.get('6', body.get('b6', 6)))
            # Instant A825 hardware format:
            # buf[2] = b1 (Left)
            # buf[3] = b3 (Middle)
            # buf[4] = b2 (Right)
            # buf[5] = b4 (Forward)
            # buf[6] = b5 (Backward)
            # buf[7] = b6 (DPI)
            pkt = [REPORT_ID, 0x15, b1, b3, b2, b4, b5, b6]
            ok, msg = send_packet(pkt)
            self.send_json_response(ok, "Button configuration updated" if ok else msg)

        elif self.path == '/api/fix-permissions':
            ok, msg = fix_permissions_polkit()
            self.send_json_response(ok, msg)

        elif self.path == '/api/color':
            stage = int(body.get('stage', 6))
            r = int(body.get('r', 255))
            g = int(body.get('g', 215))
            b = int(body.get('b', 0))
            mode = int(body.get('mode', 2))
            speed = int(body.get('speed', 2))
            bright = int(body.get('bright', 4))

            # 1. Stage LED Color packet (0x14):
            # Instant A825 hardware format:
            # byte 2: ((stage - 1) << 5) | (G >> 4)
            # byte 3: ((R >> 4) << 4) | (B >> 4)
            r4 = (r >> 4) & 0x0F
            g4 = (g >> 4) & 0x0F
            b4 = (b >> 4) & 0x0F
            pkt_color = [REPORT_ID, 0x14, ((stage - 1) << 5) | g4, (r4 << 4) | b4, 0, 0, 0, 0]
            ok1, msg1 = send_packet(pkt_color)

            # 2. Activate Stage in real time (0x10):
            pkt_stage = [REPORT_ID, 0x10, 0x01, stage - 1, 0, 0, 0, 0]
            send_packet(pkt_stage)

            # 3. RGB Mode (0x13):
            # In Instant A825: byte 2 = 0x80 | mode, byte 3 = speed & 7, byte 4 = 0x80 | ((bright & 3) << 4)
            b_val = 0x80 | (((bright - 1) & 0x03) << 4)
            pkt_rgb = [REPORT_ID, 0x13, (mode | 0x80) & 0xFF, speed & 0x07, b_val, 0, 0, 0]
            ok2, msg2 = send_packet(pkt_rgb)

            # No flash save during live preview to avoid MCU stall!
            success = ok1 and ok2
            self.send_json_response(success, "Color updated live" if success else (msg1 or msg2))

        elif self.path == '/api/stage':
            stage = int(body.get('stage', 1))
            pkt = [REPORT_ID, 0x10, 0x01, stage - 1, 0, 0, 0, 0]
            ok, msg = send_packet(pkt)
            self.send_json_response(ok, f"Activated Stage {stage}" if ok else msg)

        elif self.path == '/api/dpi':
            stage = int(body.get('stage', 1))
            dpi = int(body.get('dpi', 800))
            idx, actual_dpi = dpi_to_index(dpi)
            pkt_dpi = [REPORT_ID, 0x10, idx, 0, 0, 0, 0, 0]
            ok, msg = send_packet(pkt_dpi)
            pkt_stage = [REPORT_ID, 0x10, 0x01, stage - 1, 0, 0, 0, 0]
            send_packet(pkt_stage)
            self.send_json_response(ok, f"DPI set to {actual_dpi}" if ok else msg)

        elif self.path == '/api/rate':
            rate = int(body.get('rate', 1000))
            codes = {1000: 0x00, 500: 0x01, 250: 0x03, 125: 0x07}
            pkt = [REPORT_ID, 0x11, codes.get(rate, 0x00), 0, 0, 0, 0, 0]
            ok, msg = send_packet(pkt)
            self.send_json_response(ok, f"Polling rate set to {rate} Hz" if ok else msg)

        elif self.path == '/api/save':
            ok, msg = save_hardware()
            self.send_json_response(ok, "Settings saved to mouse onboard flash memory" if ok else msg)
        else:
            self.send_error(404)

    def send_json_response(self, success, message):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        resp = {'success': success, 'message': message if success else None, 'error': None if success else message}
        self.wfile.write(json.dumps(resp).encode('utf-8'))

    def log_message(self, format, *args):
        pass

def main():
    print(f"Starting EvoFox Real-Time Control Center on http://127.0.0.1:{PORT}")
    server = HTTPServer(('127.0.0.1', PORT), RequestHandler)
    threading.Thread(target=lambda: webbrowser.open(f"http://127.0.0.1:{PORT}"), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping EvoFox Control Center.")
        server.server_close()

if __name__ == '__main__':
    main()
