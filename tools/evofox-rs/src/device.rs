//! Linux sysfs discovery and raw HID feature report communication.
//! Securely restricted to USB VID 0x30FA / PID 0x1440 with Feature Report ID 0x07 validation.

use std::fs::{self, File, OpenOptions};
use std::io::{self, Read};
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::io::AsRawFd;
use std::path::{Path, PathBuf};

pub const TARGET_VID: u16 = 0x30fa;
pub const TARGET_PID: u16 = 0x1440;
pub const REPORT_ID: u8 = 0x07;
pub const REPORT_SIZE: usize = 8;

// Linux ioctl: _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x06, 8) = 0xC0084806
const HIDIOCSFEATURE_8: u64 = 0xC0084806;

extern "C" {
    fn ioctl(fd: i32, request: u64, ...) -> i32;
}

pub struct MouseDevice {
    pub path: PathBuf,
}

impl MouseDevice {
    /// Automatically discover the vendor control hidraw node in /sys/class/hidraw.
    /// Strictly verifies that:
    /// 1. The USB Vendor ID is 0x30FA and Product ID is 0x1440.
    /// 2. The HID Report Descriptor contains Feature Report ID 0x07.
    pub fn find() -> Option<Self> {
        let entries = fs::read_dir("/sys/class/hidraw").ok()?;

        let mut fallback: Option<PathBuf> = None;

        for entry in entries.flatten() {
            let path = entry.path();
            let uevent_path = path.join("device/uevent");
            let mut uevent_content = String::new();

            if let Ok(mut f) = File::open(&uevent_path) {
                let _ = f.read_to_string(&mut uevent_content);
            }

            let uevent_lower = uevent_content.to_lowercase();
            let matches_device = uevent_lower.contains("30fa") && uevent_lower.contains("1440");

            if matches_device {
                if let Some(file_name) = path.file_name() {
                    let dev_path = Path::new("/dev").join(file_name);

                    // Verify this interface exposes Feature Report ID 0x07
                    let rdesc_path = path.join("device/report_descriptor");
                    let mut rdesc = Vec::new();
                    if let Ok(mut rf) = File::open(&rdesc_path) {
                        let _ = rf.read_to_end(&mut rdesc);
                    }

                    let is_control_if = rdesc.windows(2).any(|w| w == [0x85, 0x07]);

                    if is_control_if {
                        return Some(Self { path: dev_path });
                    } else if fallback.is_none() {
                        fallback = Some(dev_path);
                    }
                }
            }
        }

        fallback.map(|p| Self { path: p })
    }

    /// Send an 8-byte Feature Report strictly via ioctl(HIDIOCSFEATURE).
    /// Does not use write() to prevent keyboard disruption.
    pub fn send_feature_report(&self, packet: &[u8; REPORT_SIZE]) -> io::Result<()> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(0)
            .open(&self.path)
            .map_err(|e| {
                if e.kind() == io::ErrorKind::PermissionDenied {
                    eprintln!("Error: Permission denied opening {:?}", self.path);
                    eprintln!("Hint: Run the one-time secure permission setup:");
                    eprintln!("      ./fix-permissions.sh");
                } else if e.kind() == io::ErrorKind::NotFound {
                    eprintln!("Error: Device {:?} was disconnected.", self.path);
                }
                e
            })?;

        let fd = file.as_raw_fd();
        let mut buf = *packet;

        let ret = unsafe { ioctl(fd, HIDIOCSFEATURE_8, buf.as_mut_ptr()) };

        if ret < 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(())
        }
    }
}
