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
    println!("  status                         Show connection and hardware details");
    println!("  stage <1-6>                    Switch active DPI stage");
    println!("  dpi <stage 1-6> <dpi>          Set DPI for stage (e.g. dpi 1 800, dpi 6 12000)");
    println!("  rate <125|250|500|1000>        Set USB polling rate in Hz");
    println!("  rgb <mode 0-14> [spd] [bright] Set RGB lighting effect (0=Off, 1=Breathe, 2=Static, 3=Neon, 4=Wave)");
    println!("  color <1-6> <#RRGGBB>          Set LED indicator color for a DPI stage (e.g. color 1 '#FF0000')");
    println!("  save                           Commit current settings to onboard memory\n");
    println!("DPI Range:");
    println!("  200 to 12,800 DPI (supports requested 12,000 DPI via hardware step index 24)");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let program = args.get(0).map(|s| s.as_str()).unwrap_or("evofox-ctl");

    if args.len() < 2 {
        print_usage(program);
        process::exit(1);
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
            println!("RGB Modes:        14 effects (0=Off, 1=Breathing, 2=Static, 3=Neon, etc.)");
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
            let pkt = protocol::packet_set_dpi(stage, idx);

            if dev.send_feature_report(&pkt).is_ok() {
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
                Err(err) => {
                    eprintln!("Error: {}", err);
                    process::exit(1);
                }
            }
        }

        "rgb" => {
            if args.len() < 3 {
                eprintln!("Usage: {} rgb <mode 0-14> [speed 1-3] [brightness 1-4]", program);
                process::exit(1);
            }
            let mode: u8 = args[2].parse().unwrap_or(1);
            let speed: u8 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(2);
            let bright: u8 = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(3);

            let pkt = protocol::packet_set_rgb(mode, speed, bright);
            if dev.send_feature_report(&pkt).is_ok() {
                let _ = dev.send_feature_report(&protocol::packet_save());
                println!("✓ RGB effect set to Mode {} (Speed: {}, Brightness: {}).", mode, speed, bright);
            }
        }

        "color" => {
            if args.len() < 4 {
                eprintln!("Usage: {} color <stage 1-6> <#RRGGBB>", program);
                process::exit(1);
            }
            let stage: u8 = args[2].parse().unwrap_or(1);
            let hex_str = args[3].trim_start_matches('#');
            if hex_str.len() != 6 {
                eprintln!("Error: Color must be a 6-digit hex code like #FF0000");
                process::exit(1);
            }
            let r = u8::from_str_radix(&hex_str[0..2], 16).unwrap_or(0);
            let g = u8::from_str_radix(&hex_str[2..4], 16).unwrap_or(0);
            let b = u8::from_str_radix(&hex_str[4..6], 16).unwrap_or(0);

            let pkt = protocol::packet_set_color(stage, r, g, b);
            if dev.send_feature_report(&pkt).is_ok() {
                let _ = dev.send_feature_report(&protocol::packet_save());
                println!("✓ Stage {} LED color set to #{}.", stage, hex_str.to_uppercase());
            }
        }

        "save" => {
            if dev.send_feature_report(&protocol::packet_save()).is_ok() {
                println!("✓ Settings saved to onboard mouse memory.");
            }
        }

        _ => {
            eprintln!("Unknown command: {}\n", command);
            print_usage(program);
            process::exit(1);
        }
    }
}
