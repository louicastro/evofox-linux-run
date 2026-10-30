//! Linux sysfs discovery and raw HID feature report communication.

use std::fs::{self, File, OpenOptions};
use std::io::{self, Read};
use std::os::unix::fs::OpenOptionsExt;
use std::os::unix::io::AsRawFd;
use std::path::{Path, PathBuf};

pub const TARGET_VID: u16 = 0x30fa;
pub const TARGET_PID: u16 = 0x1440;

// Linux ioctl: _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x06, 8) = 0xC0084806
const HIDIOCSFEATURE_8: u64 = 0xC0084806;

extern "C" {
    fn ioctl(fd: i32, request: u64, ...) -> i32;
}

pub struct MouseDevice {
    pub path: PathBuf,
}

impl MouseDevice {
    /// Automatically discover the control hidraw node in /sys/class/hidraw
    pub fn find() -> Option<Self> {
        let entries = fs::read_dir("/sys/class/hidraw").ok()?;

        for entry in entries.flatten() {
            let path = entry.path();
            let uevent_path = path.join("device/uevent");
            let mut uevent_content = String::new();

            if let Ok(mut f) = File::open(&uevent_path) {
                let _ = f.read_to_string(&mut uevent_content);
            }

            let matches_device = (uevent_content.contains("30FA") || uevent_content.contains("30fa"))
                && uevent_content.contains("1440");

            if matches_device {
                // Ensure this is Interface 1 (Vendor Control with Report ID 0x07)
                let rdesc_path = path.join("device/report_descriptor");
                let mut rdesc = Vec::new();
                if let Ok(mut rf) = File::open(&rdesc_path) {
                    let _ = rf.read_to_end(&mut rdesc);
                }

                let is_control_if = rdesc.windows(2).any(|w| w == [0x85, 0x07]);

                if is_control_if {
                    if let Some(file_name) = path.file_name() {
                        let dev_path = Path::new("/dev").join(file_name);
                        return Some(Self { path: dev_path });
                    }
                }
            }
        }

        None
    }

    /// Send an 8-byte Feature Report to the device
    pub fn send_feature_report(&self, packet: &[u8; 8]) -> io::Result<()> {
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .custom_flags(0)
            .open(&self.path)
            .map_err(|e| {
                if e.kind() == io::ErrorKind::PermissionDenied {
                    eprintln!("Error: Permission denied opening {:?}", self.path);
                    eprintln!("Hint: Run with sudo or install the udev rule:");
                    eprintln!("      sudo cp 99-evofox.rules /etc/udev/rules.d/");
                    eprintln!("      sudo udevadm control --reload-rules && sudo udevadm trigger");
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
