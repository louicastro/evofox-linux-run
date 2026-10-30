/*
 * evofox-ctl: High-performance Linux control utility for Amkette EvoFox Phantom Air /
 *             Instant Microelectronics A825 Gaming Mice (USB VID 0x30FA / PID 0x1440)
 *
 * Reverse-engineered protocol:
 * - Device Interface 1 (/dev/hidrawX with Report ID 0x07)
 * - 8-byte Feature Reports strictly via HIDIOCSFEATURE ioctl
 * - Zero write() calls to prevent keyboard input disruption
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <linux/hidraw.h>

#define TARGET_VID 0x30fa
#define TARGET_PID 0x1440
#define REPORT_ID 0x07
#define REPORT_SIZE 8

/* Sensor DPI table mapping index -> Hardware DPI */
typedef struct {
    uint8_t index;
    uint32_t dpi;
} DpiMapping;

static const DpiMapping DPI_TABLE[] = {
    { 1,   200 },
    { 2,   400 },
    { 3,   600 },
    { 4,   800 },
    { 5,  1000 },
    { 6,  1200 },
    { 7,  1400 },
    { 8,  1600 },
    { 9,  1800 },
    { 10, 2000 },
    { 12, 2400 },
    { 13, 3200 },
    { 14, 4000 },
    { 15, 4800 },
    { 16, 5600 },
    { 17, 6400 },
    { 18, 7200 },
    { 19, 8000 },
    { 20, 8800 },
    { 21, 9600 },
    { 22, 10400 },
    { 23, 11200 },
    { 24, 12800 }, // Max hardware sensor resolution (EvoFox Phantom Air 12000/12800)
    { 0,  0 }
};

/* Convert user DPI number to closest hardware sensor step index */
static uint8_t dpi_to_index(uint32_t dpi, uint32_t *actual_dpi) {
    if (dpi <= 200) {
        if (actual_dpi) *actual_dpi = 200;
        return 1;
    }
    if (dpi >= 11600) {
        if (actual_dpi) *actual_dpi = 12800;
        return 24;
    }

    uint8_t best_idx = 4; // default 800
    uint32_t best_diff = 0xFFFFFFFF;
    uint32_t closest_dpi = 800;

    for (int i = 0; DPI_TABLE[i].dpi > 0; i++) {
        uint32_t diff = (dpi > DPI_TABLE[i].dpi) ? (dpi - DPI_TABLE[i].dpi) : (DPI_TABLE[i].dpi - dpi);
        if (diff < best_diff) {
            best_diff = diff;
            best_idx = DPI_TABLE[i].index;
            closest_dpi = DPI_TABLE[i].dpi;
        }
    }

    if (actual_dpi) *actual_dpi = closest_dpi;
    return best_idx;
}

/* Locate the control hidraw node for VID 0x30fa / PID 0x1440 */
static char *find_device_path(void) {
    DIR *dir = opendir("/sys/class/hidraw");
    if (!dir) return NULL;

    struct dirent *entry;
    char path_buf[512];
    char uevent_buf[1024];
    char candidates[4][280];
    int count = 0;
    char *control_node = NULL;

    while ((entry = readdir(dir)) != NULL && count < 4) {
        if (entry->d_name[0] == '.') continue;

        snprintf(path_buf, sizeof(path_buf), "/sys/class/hidraw/%s/device/uevent", entry->d_name);
        FILE *f = fopen(path_buf, "r");
        if (!f) continue;

        size_t len = fread(uevent_buf, 1, sizeof(uevent_buf) - 1, f);
        fclose(f);
        uevent_buf[len] = '\0';

        if (strstr(uevent_buf, "30FA") && strstr(uevent_buf, "1440")) {
            char rdesc_path[512];
            snprintf(rdesc_path, sizeof(rdesc_path), "/sys/class/hidraw/%s/device/report_descriptor", entry->d_name);
            FILE *rf = fopen(rdesc_path, "rb");
            if (rf) {
                uint8_t rdesc[256];
                size_t rlen = fread(rdesc, 1, sizeof(rdesc), rf);
                fclose(rf);
                for (size_t i = 0; i + 1 < rlen; i++) {
                    if (rdesc[i] == 0x85 && rdesc[i+1] == 0x07) {
                        snprintf(candidates[count], sizeof(candidates[count]), "/dev/%s", entry->d_name);
                        control_node = strdup(candidates[count]);
                        break;
                    }
                }
            }
            snprintf(candidates[count], sizeof(candidates[count]), "/dev/%s", entry->d_name);
            count++;
        }
    }

    closedir(dir);
    if (control_node) return control_node;
    if (count > 0) return strdup(candidates[count - 1]);
    return NULL;
}

/* Send 8-byte HID Feature Report strictly via ioctl. Never calls write. */
static int send_packet(const char *dev_path, const uint8_t *packet) {
    const char *target = dev_path;
    char *autopath = NULL;
    if (!target) {
        autopath = find_device_path();
        target = autopath;
    }

    if (!target) {
        fprintf(stderr, "Error: EvoFox Phantom Air (30FA:1440) not found.\n");
        return -1;
    }

    uint8_t buf[REPORT_SIZE];
    memcpy(buf, packet, REPORT_SIZE);

    int fd = open(target, O_RDWR | O_NONBLOCK);
    if (fd < 0) {
        if (errno == EACCES) {
            fprintf(stderr, "Error: Permission denied opening %s.\n", target);
            fprintf(stderr, "Hint: Run fix-permissions.sh to configure non-root access:\n");
            fprintf(stderr, "      sudo ./fix-permissions.sh\n");
        } else {
            fprintf(stderr, "Error opening %s: %s\n", target, strerror(errno));
        }
        if (autopath) free(autopath);
        return -1;
    }

    int ret = ioctl(fd, HIDIOCSFEATURE(REPORT_SIZE), buf);
    close(fd);
    if (autopath) free(autopath);

    return (ret >= 0) ? 0 : -1;
}

/* Save settings to onboard EEPROM/flash memory */
static int cmd_save(const char *dev_path) {
    uint8_t pkt[8] = { REPORT_ID, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
    if (send_packet(dev_path, pkt) == 0) {
        printf("✓ Settings saved to onboard mouse memory.\n");
        return 0;
    }
    return 1;
}

/* Set Active DPI Stage (1 - 6) */
static int cmd_set_stage(const char *dev_path, int stage) {
    if (stage < 1 || stage > 6) {
        fprintf(stderr, "Error: DPI stage must be between 1 and 6 (got %d).\n", stage);
        return 1;
    }
    // Protocol: 0x07, 0x10, 0x01, (stage - 1)
    uint8_t pkt[8] = { REPORT_ID, 0x10, 0x01, (uint8_t)(stage - 1), 0x00, 0x00, 0x00, 0x00 };
    if (send_packet(dev_path, pkt) == 0) {
        printf("✓ Activated DPI Stage %d.\n", stage);
        cmd_save(dev_path);
        return 0;
    }
    return 1;
}

/* Configure DPI for a specific stage */
static int cmd_set_dpi(const char *dev_path, int stage, uint32_t target_dpi) {
    if (stage < 1 || stage > 6) {
        fprintf(stderr, "Error: DPI stage must be between 1 and 6 (got %d).\n", stage);
        return 1;
    }
    uint32_t actual_dpi = 0;
    uint8_t idx = dpi_to_index(target_dpi, &actual_dpi);

    // Protocol: 0x07, 0x10, idx, 0x00...
    uint8_t pkt_dpi[8] = { REPORT_ID, 0x10, idx, 0x00, 0x00, 0x00, 0x00, 0x00 };
    uint8_t pkt_stage[8] = { REPORT_ID, 0x10, 0x01, (uint8_t)(stage - 1), 0x00, 0x00, 0x00, 0x00 };

    if (send_packet(dev_path, pkt_dpi) == 0) {
        send_packet(dev_path, pkt_stage);
        printf("✓ Stage %d configured to %u DPI (hardware step index: %d).\n", stage, actual_dpi, idx);
        cmd_save(dev_path);
        return 0;
    }
    return 1;
}

/* Configure USB Polling Rate (125, 250, 500, 1000 Hz) */
static int cmd_set_rate(const char *dev_path, int hz) {
    uint8_t code;
    switch (hz) {
        case 1000: code = 0x00; break;
        case 500:  code = 0x01; break;
        case 250:  code = 0x03; break;
        case 125:  code = 0x07; break;
        default:
            fprintf(stderr, "Error: Invalid polling rate %d Hz. Supported: 125, 250, 500, 1000.\n", hz);
            return 1;
    }

    uint8_t pkt[8] = { REPORT_ID, 0x11, code, 0x00, 0x00, 0x00, 0x00, 0x00 };
    if (send_packet(dev_path, pkt) == 0) {
        printf("✓ USB Polling Rate set to %d Hz.\n", hz);
        cmd_save(dev_path);
        return 0;
    }
    return 1;
}

/* Configure RGB Lighting Effect */
static int cmd_set_rgb(const char *dev_path, int mode, int speed, int brightness) {
    if (mode < 0 || mode > 14) {
        fprintf(stderr, "Error: RGB mode must be between 0 and 14.\n");
        return 1;
    }
    if (speed < 1) speed = 1;
    if (speed > 3) speed = 3;
    if (brightness < 1) brightness = 1;
    if (brightness > 4) brightness = 4;

    uint8_t b_val = 0x80 | (((brightness - 1) & 0x03) << 4);
    uint8_t pkt[8] = {
        REPORT_ID,
        0x13,
        (uint8_t)((mode | 0x80) & 0xFF),
        (uint8_t)(speed & 0x07),
        b_val,
        0x00,
        0x00,
        0x00
    };

    if (send_packet(dev_path, pkt) == 0) {
        const char *mode_names[] = {
            "Off", "Breathing", "Static Solid", "Neon / Spectrum Cycle",
            "Rainbow Wave / Streaming", "Click Reaction", "Twinkle",
            "Pulse Wave"
        };
        const char *mname = (mode < 8) ? mode_names[mode] : "Custom";
        printf("✓ RGB effect set to: %s (Mode %d, Speed %d, Brightness %d).\n", mname, mode, speed, brightness);
        cmd_save(dev_path);
        return 0;
    }
    return 1;
}

/* Set LED color for a DPI stage */
static int cmd_set_color(const char *dev_path, int stage, uint8_t r8, uint8_t g8, uint8_t b8) {
    if (stage < 1 || stage > 6) {
        fprintf(stderr, "Error: DPI stage must be between 1 and 6 (got %d).\n", stage);
        return 1;
    }

    // Hardware uses 4-bit nibbles (0 to 15) for R, G, B
    // Instant A825 format: byte 2 = ((stage - 1) << 5) | G4, byte 3 = (R4 << 4) | B4
    uint8_t r4 = (r8 >> 4) & 0x0F;
    uint8_t g4 = (g8 >> 4) & 0x0F;
    uint8_t b4 = (b8 >> 4) & 0x0F;

    uint8_t pkt_color[8] = {
        REPORT_ID,
        0x14,
        (uint8_t)(((stage - 1) << 5) | g4),
        (uint8_t)((r4 << 4) | b4),
        0x00, 0x00, 0x00, 0x00
    };

    uint8_t pkt_stage[8] = {
        REPORT_ID,
        0x10,
        0x01,
        (uint8_t)(stage - 1),
        0x00, 0x00, 0x00, 0x00
    };

    if (send_packet(dev_path, pkt_color) == 0) {
        send_packet(dev_path, pkt_stage);
        printf("✓ Stage %d LED color set to RGB(%u, %u, %u).\n", stage, r8, g8, b8);
        cmd_save(dev_path);
        return 0;
    }
    return 1;
}

/* Action ID mappings for Instant A825 Button Remapping */
typedef struct {
    const char *name;
    uint8_t code;
} ActionMapping;

static const ActionMapping ACTION_LIST[] = {
    { "left", 1 }, { "click", 1 }, { "lclick", 1 },
    { "right", 2 }, { "rclick", 2 },
    { "middle", 3 }, { "scroll", 3 }, { "mclick", 3 },
    { "back", 4 }, { "backward", 4 }, { "prev", 4 },
    { "forward", 5 }, { "next", 5 },
    { "dpi", 6 }, { "dpiloop", 6 },
    { "rapidfire", 14 }, { "burst", 14 }, { "triple", 14 },
    { "double", 15 }, { "doubleclick", 15 },
    { "dpi+", 16 }, { "dpiup", 16 },
    { "dpi-", 17 }, { "dpidown", 17 },
    { "led", 19 }, { "rgb", 19 }, { "ledswitch", 19 },
    { "mute", 20 },
    { "vol+", 21 }, { "volup", 21 }, { "volumeup", 21 },
    { "vol-", 22 }, { "voldown", 22 }, { "volumedown", 22 },
    { "nexttrack", 25 },
    { "prevtrack", 26 },
    { "playpause", 27 }, { "play", 27 }, { "pause", 27 },
    { "desktop", 30 }, { "showdesktop", 30 },
    { "disable", 50 }, { "none", 50 }, { "off", 50 },
    { NULL, 0 }
};

static uint8_t parse_action_str(const char *str) {
    if (!str || !*str) return 0;
    char *endptr = NULL;
    long val = strtol(str, &endptr, 10);
    if (endptr && *endptr == '\0') {
        return (uint8_t)val;
    }
    for (int i = 0; ACTION_LIST[i].name != NULL; i++) {
        if (strcasecmp(ACTION_LIST[i].name, str) == 0) {
            return ACTION_LIST[i].code;
        }
    }
    return 0;
}

static const char *get_action_desc(uint8_t code) {
    switch (code) {
        case 1: return "Left Click";
        case 2: return "Right Click";
        case 3: return "Middle Click / Scroll Wheel";
        case 4: return "Browser Backward";
        case 5: return "Browser Forward";
        case 6: return "DPI Loop";
        case 14: return "Rapid Fire (Triple Click)";
        case 15: return "Double Click";
        case 16: return "DPI + (Step Up)";
        case 17: return "DPI - (Step Down)";
        case 19: return "LED Mode Switch";
        case 20: return "Mute Audio";
        case 21: return "Volume Up";
        case 22: return "Volume Down";
        case 25: return "Next Track";
        case 26: return "Previous Track";
        case 27: return "Play / Pause";
        case 30: return "Show Desktop";
        case 50: return "Disabled / None";
        default: return "Custom Action";
    }
}

/* Set all 6 mouse buttons via Feature Report 0x15 */
static int cmd_set_buttons(const char *dev_path, uint8_t b1, uint8_t b2, uint8_t b3, uint8_t b4, uint8_t b5, uint8_t b6, bool save) {
    // Instant A825 hardware format:
    // buf[2] = b1 (Left)
    // buf[3] = b3 (Middle)
    // buf[4] = b2 (Right)
    // buf[5] = b4 (Forward)
    // buf[6] = b5 (Backward)
    // buf[7] = b6 (DPI)
    uint8_t pkt[8] = {
        REPORT_ID,
        0x15,
        b1,
        b3,
        b2,
        b4,
        b5,
        b6
    };

    if (send_packet(dev_path, pkt) == 0) {
        printf("✓ Button configuration applied successfully:\n");
        printf("  • Button 1 (Left):      %s (ID: %u)\n", get_action_desc(b1), b1);
        printf("  • Button 2 (Right):     %s (ID: %u)\n", get_action_desc(b2), b2);
        printf("  • Button 3 (Middle):    %s (ID: %u)\n", get_action_desc(b3), b3);
        printf("  • Button 4 (Forward):   %s (ID: %u)\n", get_action_desc(b4), b4);
        printf("  • Button 5 (Backward):  %s (ID: %u)\n", get_action_desc(b5), b5);
        printf("  • Button 6 (Top DPI):   %s (ID: %u)\n", get_action_desc(b6), b6);
        if (save) {
            cmd_save(dev_path);
        }
        return 0;
    }
    return 1;
}

/* Remap single button (defaults: 1:1, 2:2, 3:3, 4:5, 5:4, 6:6) */
static int cmd_remap_button(const char *dev_path, int button, uint8_t action, bool save) {
    if (button < 1 || button > 6) {
        fprintf(stderr, "Error: Button number must be between 1 and 6 (got %d).\n", button);
        return 1;
    }
    if (action == 0) {
        fprintf(stderr, "Error: Invalid or unknown action specified.\n");
        return 1;
    }

    uint8_t b[7] = { 0, 1, 2, 3, 5, 4, 6 }; // 1-indexed defaults
    b[button] = action;

    return cmd_set_buttons(dev_path, b[1], b[2], b[3], b[4], b[5], b[6], save);
}

/* Print device info */
static int cmd_status(const char *dev_path) {
    char *path = dev_path ? strdup(dev_path) : find_device_path();
    if (!path) {
        printf("EvoFox Phantom Air (30FA:1440): NOT CONNECTED\n");
        return 1;
    }

    printf("=================================================================\n");
    printf(" EvoFox Phantom Air / Instant A825 Linux Configuration Utility\n");
    printf("=================================================================\n");
    printf("Status:           CONNECTED\n");
    printf("USB Vendor/Prod:  VID 0x%04X, PID 0x%04X\n", TARGET_VID, TARGET_PID);
    printf("Sensor Model:     Instant Microelectronics A825 Optical\n");
    printf("Control Node:     %s\n", path);
    printf("Max Resolution:   12,800 DPI (Supported steps: 200 - 12800)\n");
    printf("Polling Rates:    125 Hz, 250 Hz, 500 Hz, 1000 Hz\n");
    printf("RGB Modes:        Off(0), Breathe(1), Static(2), Neon(3), Wave(4), etc.\n");
    printf("Programmable:     6 Buttons (Rapid Fire, Double Click, Media, DPI, LED)\n");
    printf("Protocol:         Strict ioctl(HIDIOCSFEATURE) on Report 0x07\n");
    printf("=================================================================\n");
    printf("Supported Button Actions:\n");
    printf("  1=Left, 2=Right, 3=Middle, 4=Backward, 5=Forward, 6=DPILoop\n");
    printf("  14=RapidFire, 15=DoubleClick, 16=DPI+, 17=DPI-, 19=LEDModeSwitch\n");
    printf("  20=Mute, 21=Vol+, 22=Vol-, 25=NextTrack, 26=PrevTrack, 27=Play/Pause\n");
    printf("  30=ShowDesktop, 50=Disabled\n");
    printf("=================================================================\n");

    free(path);
    return 0;
}

static void print_usage(const char *prog) {
    printf("Amkette EvoFox Phantom Air (Instant A825) Linux Configuration Utility\n\n");
    printf("Usage: %s <command> [arguments]\n\n", prog);
    printf("Commands:\n");
    printf("  status                               Show connection and device info\n");
    printf("  stage <1-6>                          Activate DPI Stage (1 to 6)\n");
    printf("  dpi <stage> <dpi>                    Set DPI for stage (e.g. dpi 6 12000)\n");
    printf("  rate <125|250|500|1000>              Set USB polling rate in Hz\n");
    printf("  rgb <mode> [speed] [bright]          Set RGB lighting effect (mode 0-7, speed 1-3, bright 1-4)\n");
    printf("  color <stage> <hex_or_r g b>         Set LED color (e.g. color 6 #00FFFF or color 6 0 255 255)\n");
    printf("  remap <1-6> <action> [--save]        Remap individual button (e.g. remap 4 rapidfire)\n");
    printf("  buttons <b1> <b2> <b3> <b4> <b5> <b6> Set all 6 buttons\n");
    printf("  preset <default|gaming|media|rgb>    Apply button preset\n");
    printf("  save                                 Commit settings to mouse onboard flash memory\n");
    printf("\nExamples:\n");
    printf("  %s remap 4 rapidfire                 Set Side Forward button to Rapid Fire (Triple Click)\n", prog);
    printf("  %s remap 6 led                       Set DPI button to switch LED effects\n", prog);
    printf("  %s preset gaming                     Apply Gaming preset (Rapid Fire on Button 4)\n", prog);
    printf("  %s dpi 6 12000                       Set Stage 6 to 12,000 DPI\n", prog);
    printf("  %s color 6 #00FFFF                   Set Stage 6 LED color to Electric Cyan\n", prog);
    printf("  %s rgb 2 2 4                         Set RGB to Static Glow, speed 2, brightness 4\n", prog);
    printf("  %s rate 1000                         Set 1000 Hz (1ms ultra-fast)\n", prog);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    const char *cmd = argv[1];

    if (strcmp(cmd, "help") == 0 || strcmp(cmd, "--help") == 0 || strcmp(cmd, "-h") == 0) {
        print_usage(argv[0]);
        return 0;
    }

    if (strcmp(cmd, "status") == 0) {
        return cmd_status(NULL);
    }

    if (strcmp(cmd, "save") == 0) {
        return cmd_save(NULL);
    }

    if (strcmp(cmd, "stage") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s stage <1-6>\n", argv[0]);
            return 1;
        }
        return cmd_set_stage(NULL, atoi(argv[2]));
    }

    if (strcmp(cmd, "dpi") == 0) {
        if (argc < 4) {
            fprintf(stderr, "Usage: %s dpi <stage 1-6> <dpi_value>\n", argv[0]);
            return 1;
        }
        int stage = atoi(argv[2]);
        uint32_t dpi = (uint32_t)strtoul(argv[3], NULL, 10);
        return cmd_set_dpi(NULL, stage, dpi);
    }

    if (strcmp(cmd, "rate") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s rate <125|250|500|1000>\n", argv[0]);
            return 1;
        }
        return cmd_set_rate(NULL, atoi(argv[2]));
    }

    if (strcmp(cmd, "rgb") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s rgb <mode 0-7> [speed 1-3] [bright 1-4]\n", argv[0]);
            return 1;
        }
        int mode = atoi(argv[2]);
        int speed = (argc >= 4) ? atoi(argv[3]) : 2;
        int bright = (argc >= 5) ? atoi(argv[4]) : 4;
        return cmd_set_rgb(NULL, mode, speed, bright);
    }

    if (strcmp(cmd, "color") == 0) {
        if (argc < 4) {
            fprintf(stderr, "Usage: %s color <stage 1-6> <#RRGGBB | R G B>\n", argv[0]);
            return 1;
        }
        int stage = atoi(argv[2]);
        uint8_t r = 0, g = 0, b = 0;
        if (argv[3][0] == '#' || strlen(argv[3]) == 6) {
            const char *hex = (argv[3][0] == '#') ? argv[3] + 1 : argv[3];
            unsigned int rgb_val = 0;
            if (sscanf(hex, "%x", &rgb_val) == 1) {
                r = (rgb_val >> 16) & 0xFF;
                g = (rgb_val >> 8) & 0xFF;
                b = rgb_val & 0xFF;
            }
        } else if (argc >= 6) {
            r = (uint8_t)atoi(argv[3]);
            g = (uint8_t)atoi(argv[4]);
            b = (uint8_t)atoi(argv[5]);
        }
        return cmd_set_color(NULL, stage, r, g, b);
    }

    if (strcmp(cmd, "remap") == 0) {
        if (argc < 4) {
            fprintf(stderr, "Usage: %s remap <button 1-6> <action_id_or_name> [--save]\n", argv[0]);
            return 1;
        }
        int btn = atoi(argv[2]);
        uint8_t action = parse_action_str(argv[3]);
        bool save = (argc >= 5 && strcmp(argv[4], "--save") == 0);
        return cmd_remap_button(NULL, btn, action, save);
    }

    if (strcmp(cmd, "buttons") == 0) {
        if (argc < 8) {
            fprintf(stderr, "Usage: %s buttons <b1> <b2> <b3> <b4> <b5> <b6> [--save]\n", argv[0]);
            return 1;
        }
        uint8_t b1 = parse_action_str(argv[2]);
        uint8_t b2 = parse_action_str(argv[3]);
        uint8_t b3 = parse_action_str(argv[4]);
        uint8_t b4 = parse_action_str(argv[5]);
        uint8_t b5 = parse_action_str(argv[6]);
        uint8_t b6 = parse_action_str(argv[7]);
        bool save = (argc >= 9 && strcmp(argv[8], "--save") == 0);
        return cmd_set_buttons(NULL, b1, b2, b3, b4, b5, b6, save);
    }

    if (strcmp(cmd, "preset") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Usage: %s preset <default|gaming|media|rgb> [--save]\n", argv[0]);
            return 1;
        }
        const char *p = argv[2];
        bool save = (argc >= 4 && strcmp(argv[3], "--save") == 0);
        if (strcasecmp(p, "default") == 0) {
            return cmd_set_buttons(NULL, 1, 2, 3, 5, 4, 6, save);
        } else if (strcasecmp(p, "gaming") == 0) {
            return cmd_set_buttons(NULL, 1, 2, 3, 14, 4, 6, save); // B4 = Rapid Fire
        } else if (strcasecmp(p, "media") == 0) {
            return cmd_set_buttons(NULL, 1, 2, 3, 21, 22, 27, save); // B4=Vol+, B5=Vol-, B6=Play/Pause
        } else if (strcasecmp(p, "rgb") == 0) {
            return cmd_set_buttons(NULL, 1, 2, 3, 5, 4, 19, save); // B6 = LED Mode Switch
        } else {
            fprintf(stderr, "Unknown preset '%s'. Options: default, gaming, media, rgb\n", p);
            return 1;
        }
    }

    fprintf(stderr, "Unknown command: %s\n", cmd);
    print_usage(argv[0]);
    return 1;
}
