//! evofox-ctl: High-performance Linux CLI tool for Amkette EvoFox Phantom Air
//! (Instant Microelectronics A825, USB VID 30fa:1440).

mod device;
mod protocol;

use device::MouseDevice;
use std::env;
use std::process;

fn print_usage(program: &str) {
    println!("evofox-ctl (Rust Edition) - Linux Mouse Control Utility\n");
    println!("Usage: {} <command> [arguments]\n", program);
    println!("Commands:");
    println!("  status                               Show connection and hardware details");
    println!("  stage <1-6>                          Switch active DPI stage");
    println!("  dpi <stage 1-6> <dpi>                Set DPI for stage (e.g. dpi 6 12000)");
    println!("  rate <125|250|500|1000>              Set USB polling rate in Hz");
    println!("  rgb <mode 0-7> [speed] [bright]      Set RGB lighting effect");
    println!("  color <1-6> <#RRGGBB>                Set LED indicator color for a DPI stage");
    println!("  remap <1-6> <action> [--save]        Remap individual button");
    println!("  buttons <b1> <b2> <b3> <b4> <b5> <b6> Set all 6 buttons");
    println!("  preset <default|gaming|media|rgb>    Apply button preset");
    println!("  save                                 Commit current settings to onboard memory\n");
    println!("DPI Range:");
    println!("  200 to 12,800 DPI (supports 12,000 DPI via hardware step index 24)");
}

fn parse_color(hex_str: &str) -> Option<(u8, u8, u8)> {
    let clean = hex_str.trim_start_matches('#');
    if clean.len() != 6 {
        return None;
    }
    let r = u8::from_str_radix(&clean[0..2], 16).ok()?;
    let g = u8::from_str_radix(&clean[2..4], 16).ok()?;
    let b = u8::from_str_radix(&clean[4..6], 16).ok()?;
    Some((r, g, b))
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let program = args.get(0).map(|s| s.as_str()).unwrap_or("evofox-ctl");

    if args.len() < 2 || args[1] == "--help" || args[1] == "-h" || args[1] == "help" {
        print_usage(program);
        process::exit(0);
    }

    let dev = match MouseDevice::find() {
        Some(d) => d,
        None => {
            eprintln!("Error: EvoFox Phantom Air / Instant A825 mouse (30FA:1440) not found.");
            eprintln!("Please ensure the mouse is connected via USB ('lsusb').");
            process::exit(1);
        }
    };

    let command = args[1].as_str();

    match command {
        "status" => {
            println!("=================================================================");
            println!(" EvoFox Phantom Air / Instant A825 Linux Configuration Utility   ");
            println!("=================================================================");
            println!("Device Status:    CONNECTED");
            println!("Hardware ID:      USB VID 0x{:04X}, PID 0x{:04X}", device::TARGET_VID, device::TARGET_PID);
            println!("Sensor Model:     Instant Microelectronics Instant A825");
            println!("Control Node:     {:?}", dev.path);
            println!("Max Resolution:   12,800 DPI (Configurable steps 200 - 12800)");
            println!("Supported Rates:  125 Hz, 250 Hz, 500 Hz, 1000 Hz");
            println!("RGB Modes:        8 effects (0=Off, 1=Breathing, 2=Static, 3=Neon, etc.)");
            println!("Programmable:     6 Buttons (Rapid Fire, Double Click, Media, DPI, LED)");
            println!("Security State:   Strict isolation to 30fa:1440 (keyboards untouched)");
            println!("=================================================================");
        }

        "stage" => {
            if args.len() < 3 {
                eprintln!("Usage: {} stage <1-6>", program);
                process::exit(1);
            }
            let stage: u8 = match args[2].parse() {
                Ok(n) if (1..=6).contains(&n) => n,
                _ => {
                    eprintln!("Error: Stage must be between 1 and 6.");
                    process::exit(1);
                }
            };
            let pkt = protocol::packet_set_stage(stage);
            if dev.send_feature_report(&pkt).is_ok() {
                let _ = dev.send_feature_report(&protocol::packet_save());
                println!("✓ Activated DPI Stage {}.", stage);
            }
        }

        "dpi" => {
            if args.len() < 4 {
                eprintln!("Usage: {} dpi <stage 1-6> <dpi>", program);
                process::exit(1);
            }
            let stage: u8 = match args[2].parse() {
                Ok(n) if (1..=6).contains(&n) => n,
                _ => {
                    eprintln!("Error: Stage must be between 1 and 6.");
                    process::exit(1);
                }
            };
            let dpi_val: u32 = match args[3].parse() {
                Ok(n) => n,
                Err(_) => {
                    eprintln!("Error: Invalid DPI value.");
                    process::exit(1);
                }
            };

            let (idx, actual_dpi) = protocol::dpi_to_index(dpi_val);
            let pkt_dpi = protocol::packet_set_dpi(stage, idx);
            let pkt_stage = protocol::packet_set_stage(stage);

            if dev.send_feature_report(&pkt_dpi).is_ok() {
                let _ = dev.send_feature_report(&pkt_stage);
                let _ = dev.send_feature_report(&protocol::packet_save());
                println!("✓ Stage {} configured to {} DPI (hardware step index: {}).", stage, actual_dpi, idx);
            }
        }

        "rate" => {
            if args.len() < 3 {
                eprintln!("Usage: {} rate <125|250|500|1000>", program);
                process::exit(1);
            }
            let hz: u32 = match args[2].parse() {
                Ok(n) => n,
                Err(_) => {
                    eprintln!("Error: Invalid polling rate.");
                    process::exit(1);
                }
            };
            match protocol::packet_set_rate(hz) {
                Ok(pkt) => {
                    if dev.send_feature_report(&pkt).is_ok() {
                        let _ = dev.send_feature_report(&protocol::packet_save());
                        println!("✓ USB Polling Rate set to {} Hz.", hz);
                    }
                }
                Err(e) => eprintln!("Error: {}", e),
            }
        }

        "rgb" => {
            if args.len() < 3 {
                eprintln!("Usage: {} rgb <mode 0-7> [speed 1-3] [bright 1-4]", program);
                process::exit(1);
            }
            let mode: u8 = args[2].parse().unwrap_or(2);
            let speed: u8 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(2);
            let bright: u8 = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(4);

            let pkt = protocol::packet_set_rgb(mode, speed, bright);
            if dev.send_feature_report(&pkt).is_ok() {
                let _ = dev.send_feature_report(&protocol::packet_save());
                println!("✓ RGB mode set to {} (Speed: {}, Brightness: {}).", mode, speed, bright);
            }
        }

        "color" => {
            if args.len() < 4 {
                eprintln!("Usage: {} color <1-6> <#RRGGBB>", program);
                process::exit(1);
            }
            let stage: u8 = match args[2].parse() {
                Ok(n) if (1..=6).contains(&n) => n,
                _ => {
                    eprintln!("Error: Stage must be between 1 and 6.");
                    process::exit(1);
                }
            };
            let (r, g, b) = match parse_color(&args[3]) {
                Some(c) => c,
                None => {
                    eprintln!("Error: Invalid hex color format. Example: '#FF0055' or '00FF00'.");
                    process::exit(1);
                }
            };

            let pkt_color = protocol::packet_set_color(stage, r, g, b);
            let pkt_stage = protocol::packet_set_stage(stage);
            if dev.send_feature_report(&pkt_color).is_ok() {
                let _ = dev.send_feature_report(&pkt_stage);
                let _ = dev.send_feature_report(&protocol::packet_save());
                println!("✓ Stage {} LED color set to #{:02X}{:02X}{:02X}.", stage, r, g, b);
            }
        }

        "remap" => {
            if args.len() < 4 {
                eprintln!("Usage: {} remap <button 1-6> <action> [--save]", program);
                process::exit(1);
            }
            let button: usize = match args[2].parse() {
                Ok(n) if (1..=6).contains(&n) => n,
                _ => {
                    eprintln!("Error: Button must be between 1 and 6.");
                    process::exit(1);
                }
            };
            let action = match protocol::parse_action(&args[3]) {
                Some(a) => a,
                None => {
                    eprintln!("Error: Unknown action '{}'.", args[3]);
                    process::exit(1);
                }
            };
            let save = args.iter().any(|a| a == "--save");

            let mut buttons = [1, 2, 3, 5, 4, 6];
            buttons[button - 1] = action;

            let pkt = protocol::packet_set_buttons(buttons[0], buttons[1], buttons[2], buttons[3], buttons[4], buttons[5]);
            if dev.send_feature_report(&pkt).is_ok() {
                if save {
                    let _ = dev.send_feature_report(&protocol::packet_save());
                }
                println!("✓ Button {} remapped to '{}' (ID: {}).", button, protocol::action_description(action), action);
            }
        }

        "preset" => {
            if args.len() < 3 {
                eprintln!("Usage: {} preset <default|gaming|media|rgb> [--save]", program);
                process::exit(1);
            }
            let preset = args[2].to_lowercase();
            let save = args.iter().any(|a| a == "--save");

            let buttons = match preset.as_str() {
                "default" => [1, 2, 3, 5, 4, 6],
                "gaming" => [1, 2, 3, 14, 4, 6], // B4 = Rapid Fire
                "media" => [1, 2, 3, 21, 22, 27], // B4=Vol+, B5=Vol-, B6=Play/Pause
                "rgb" => [1, 2, 3, 5, 4, 19],     // B6 = LED Mode Switch
                _ => {
                    eprintln!("Error: Unknown preset '{}'. Options: default, gaming, media, rgb.", preset);
                    process::exit(1);
                }
            };

            let pkt = protocol::packet_set_buttons(buttons[0], buttons[1], buttons[2], buttons[3], buttons[4], buttons[5]);
            if dev.send_feature_report(&pkt).is_ok() {
                if save {
                    let _ = dev.send_feature_report(&protocol::packet_save());
                }
                println!("✓ Preset '{}' applied successfully.", preset);
            }
        }

        "save" => {
            let pkt = protocol::packet_save();
            if dev.send_feature_report(&pkt).is_ok() {
                println!("✓ Settings committed to mouse onboard Flash memory.");
            }
        }

        unknown => {
            eprintln!("Error: Unknown command '{}'.", unknown);
            print_usage(program);
            process::exit(1);
        }
    }
}
