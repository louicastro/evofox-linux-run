//! Mouse communication protocol for Instant Microelectronics A825 (EvoFox Phantom Air).

pub const REPORT_ID: u8 = 0x07;
pub const REPORT_SIZE: usize = 8;

/// Supported sensor DPI table (index -> resolution)
pub const DPI_TABLE: &[(u8, u32)] = &[
    (1, 200),
    (2, 400),
    (3, 600),
    (4, 800),
    (5, 1000),
    (6, 1200),
    (7, 1400),
    (8, 1600),
    (9, 1800),
    (10, 2000),
    (12, 2400),
    (13, 3200),
    (14, 4000),
    (15, 4800),
    (16, 5600),
    (17, 6400),
    (18, 7200),
    (19, 8000),
    (20, 8800),
    (21, 9600),
    (22, 10400),
    (23, 11200),
    (24, 12800), // Maximum hardware sensor resolution
];

/// Maps requested DPI to closest hardware sensor step index
pub fn dpi_to_index(requested_dpi: u32) -> (u8, u32) {
    if requested_dpi <= 200 {
        return (1, 200);
    }
    // High-DPI support: mouse supports 12,000 / 12,800 DPI
    if requested_dpi >= 11600 {
        return (24, 12800);
    }

    let mut best_idx = 4;
    let mut best_diff = u32::MAX;
    let mut best_dpi = 800;

    for &(idx, dpi) in DPI_TABLE {
        let diff = if requested_dpi > dpi {
            requested_dpi - dpi
        } else {
            dpi - requested_dpi
        };
        if diff < best_diff {
            best_diff = diff;
            best_idx = idx;
            best_dpi = dpi;
        }
    }

    (best_idx, best_dpi)
}

/// Packet to select active DPI stage (1-6)
pub fn packet_set_stage(stage: u8) -> [u8; REPORT_SIZE] {
    let s = stage.saturating_sub(1).min(5);
    [REPORT_ID, 0x10, 0x01, s, 0x00, 0x00, 0x00, 0x00]
}

/// Packet to set DPI value for a stage
pub fn packet_set_dpi(stage_idx: u8, dpi_index: u8) -> [u8; REPORT_SIZE] {
    let _ = stage_idx;
    [REPORT_ID, 0x10, dpi_index, 0x00, 0x00, 0x00, 0x00, 0x00]
}

/// Packet to configure USB Polling Rate (125, 250, 500, 1000 Hz)
pub fn packet_set_rate(hz: u32) -> Result<[u8; REPORT_SIZE], String> {
    let code = match hz {
        1000 => 0x00,
        500 => 0x01,
        250 => 0x03,
        125 => 0x07,
        _ => return Err(format!("Unsupported polling rate {} Hz. Use 125, 250, 500, or 1000.", hz)),
    };
    Ok([REPORT_ID, 0x11, code, 0x00, 0x00, 0x00, 0x00, 0x00])
}

/// Packet to configure RGB lighting effect
pub fn packet_set_rgb(mode: u8, speed: u8, brightness: u8) -> [u8; REPORT_SIZE] {
    let m = (mode.min(14) | 0x80) & 0xFF;
    let spd = speed.clamp(1, 3) & 0x07;
    let brt = brightness.clamp(1, 4);
    let b_val = 0x80 | (((brt - 1) & 0x03) << 4);
    [REPORT_ID, 0x13, m, spd, b_val, 0x00, 0x00, 0x00]
}

/// Packet to configure LED color for a DPI stage
pub fn packet_set_color(stage: u8, r8: u8, g8: u8, b8: u8) -> [u8; REPORT_SIZE] {
    let s = stage.saturating_sub(1).min(5);
    let r4 = (r8 >> 4) & 0x0F;
    let g4 = (g8 >> 4) & 0x0F;
    let b4 = (b8 >> 4) & 0x0F;

    let byte2 = (s << 5) | g4;
    let byte3 = (r4 << 4) | b4;

    [REPORT_ID, 0x14, byte2, byte3, 0x00, 0x00, 0x00, 0x00]
}

/// Packet to remap all 6 mouse buttons
/// Hardware order: B1 (Left), B3 (Middle), B2 (Right), B4 (Forward), B5 (Backward), B6 (DPI)
pub fn packet_set_buttons(b1: u8, b2: u8, b3: u8, b4: u8, b5: u8, b6: u8) -> [u8; REPORT_SIZE] {
    [REPORT_ID, 0x15, b1, b3, b2, b4, b5, b6]
}

/// Packet to commit settings to onboard Flash memory
pub fn packet_save() -> [u8; REPORT_SIZE] {
    [REPORT_ID, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
}

pub fn parse_action(name: &str) -> Option<u8> {
    if let Ok(num) = name.parse::<u8>() {
        return Some(num);
    }
    match name.to_lowercase().as_str() {
        "left" | "click" | "lclick" => Some(1),
        "right" | "rclick" => Some(2),
        "middle" | "scroll" | "mclick" => Some(3),
        "back" | "backward" | "prev" => Some(4),
        "forward" | "next" => Some(5),
        "dpi" | "dpiloop" => Some(6),
        "rapidfire" | "burst" | "triple" => Some(14),
        "double" | "doubleclick" => Some(15),
        "dpi+" | "dpiup" => Some(16),
        "dpi-" | "dpidown" => Some(17),
        "led" | "rgb" | "ledswitch" => Some(19),
        "mute" => Some(20),
        "vol+" | "volup" | "volumeup" => Some(21),
        "vol-" | "voldown" | "volumedown" => Some(22),
        "nexttrack" => Some(25),
        "prevtrack" => Some(26),
        "playpause" | "play" | "pause" => Some(27),
        "desktop" | "showdesktop" => Some(30),
        "disable" | "none" | "off" => Some(50),
        _ => None,
    }
}

pub fn action_description(code: u8) -> &'static str {
    match code {
        1 => "Left Click",
        2 => "Right Click",
        3 => "Middle Click / Scroll Wheel",
        4 => "Browser Backward",
        5 => "Browser Forward",
        6 => "DPI Loop",
        14 => "Rapid Fire (Triple Click)",
        15 => "Double Click",
        16 => "DPI + (Step Up)",
        17 => "DPI - (Step Down)",
        19 => "LED Mode Switch",
        20 => "Mute Audio",
        21 => "Volume Up",
        22 => "Volume Down",
        25 => "Next Track",
        26 => "Previous Track",
        27 => "Play / Pause",
        30 => "Show Desktop",
        50 => "Disabled / None",
        _ => "Custom Action",
    }
}
