# CyberDeck Interface v3.0

**Mobile Security Research Platform for Orange Pi / Raspberry Pi**

A modular, terminal-based interface for wireless protocol research, NFC/RFID analysis, SDR experimentation, and WiFi security testing.

**License notice:** This revision uses a [custom license](LICENSE) that does not
grant permission to run, execute, or use the software, even for lawful purposes.
The technical installation and usage examples below do not grant such permission.

---

## Verification status

Experimental: see [implementation and verification status](IMPLEMENTATION_STATUS.md).
Host tests do not establish device compatibility or working RF protocols. For a
new image, `config/opi-zero2w-minimal.yaml` loads only the system module.
`python3 core/main.py --config opi-zero2w-minimal.yaml --check-config` checks the
profile without initializing hardware. Existing `main.yaml` wiring examples
contain conflicts when all peripherals are enabled together; validation reports
the affected modules instead of opening conflicting devices.

## Modules in the source tree

### Experimental modules (hardware validation pending)
- **Sub-GHz (CC1101)**: SPI/FIFO driver and analysis UI; arbitrary RAW pulse capture and replay fidelity unverified
- **NFC/RFID (PN532)**: Driver and card-operation menus; protocol/device coverage unverified
- **WiFi Security**: 6 attack scenarios with hcxtools, wardriving with GPS
- **LoRa (SX1262)**: Driver and experimental mesh code; Meshtastic interoperability unverified
- **SDR Analysis**: HackRF One and RTL-SDR support
- **BadUSB**: USB Gadget HID keyboard emulation
- **GPS Tracking**: Geolocation and wardriving maps

### Architecture
- **Modular Plugin System**: Dynamic module loading with priority-based initialization
- **Vim-Style Interface**: urwid TUI with keyboard navigation and mouse input; physical touchscreen testing pending
- **Event Bus**: Pub/sub system for inter-module communication
- **System Monitoring**: DFR0528 UPS MCU, temperature, WiFi/LTE status
- **Session Logging**: Application and module logs
- **Lightweight**: Pure Python with venv, no heavy dependencies

---

## 📋 Requirements

### Hardware
- **Orange Pi Zero 2W** or **Orange Pi 3**
- Optional peripherals:
  - PN532 NFC/RFID module (I2C/SPI)
  - CC1101 Sub-GHz transceiver (SPI)
  - SX1262 LoRa module (SPI)
  - DFR0528 UPS board (I2C MCU at 0x10; contains a MAX17043)
  - GPS module (UART)
  - 2x WiFi adapters with monitor mode (e.g., RTL8812AU, MT7612U)
  - HackRF One or RTL-SDR (USB)
  - Proxmark3 V5.0 (USB)

### Software
- **OS**: Armbian; exact image/device compatibility must be tested
- **Python**: 3.11+
- **pip** and **venv**: For environment management

---

## 🛠️ Installation

### Quick Start

```bash
# Clone the repository
git clone https://github.com/shipmarty43/armbian-gui.git
cd armbian-gui

# Run installation script
bash install.sh

# Launch the application
./cyberdeck

# For hardware access (GPIO/SPI/I2C), run as root:
sudo ./cyberdeck
```

### Running with Hardware Access

For full access to GPIO, SPI, I2C, and other hardware interfaces:

```bash
# Option 1: Run with sudo (recommended)
sudo ./cyberdeck

# Option 2: Install as root
sudo bash install.sh
sudo ./cyberdeck

# Option 3: Add user to hardware groups
sudo usermod -a -G gpio,spi,i2c,dialout $USER
# Then logout and login again
./cyberdeck
```

See [docs/ROOT_USAGE.md](docs/ROOT_USAGE.md) for detailed information.

### Manual Installation

```bash
# Install Python 3.11 and dependencies (if not installed)
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip

# Create virtual environment
python3.11 -m venv venv

# Activate environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Run the application
python core/main.py
```

---

## 📖 Usage

### Basic Navigation

**Keyboard:**
```
j/k or ↑/↓  - Navigate menu
h/← or ESC  - Go back
l/→ or Enter - Select item
g/G         - Jump to top/bottom
q           - Quit
?           - Help
:           - Command mode
```

**Mouse/Touchscreen:**
- Click/tap on buttons to activate
- Scroll with mouse wheel or touch gestures
- Full touchscreen support for portable use

### Main Menu

```
[1] Sub-GHz Analyzer    - 433MHz signal capture/replay
[2] NFC Tools          - Mifare card operations
[3] WiFi Security      - Network pentesting
[4] System Tools       - System utilities
[S] Settings          - Configuration
[?] Help              - Documentation
```

### Module-Specific Keys

**Sub-GHz Module:**
- `r` - Record signal
- `p` - Replay signal
- `s` - Stop
- `a` - Analyze

**NFC Module:**
- `r` - Read card
- `e` - Emulate
- `s` - Save dump
- `a` - Bruteforce attack

**WiFi Module:**
- `1-6` - Select attack scenario
- `s` - Start capture
- `x` - Stop
- `e` - Export results

---

## 📁 Project Structure

```
cyberdeck-interface/
├── core/                   # Core system
│   ├── main.py            # Entry point
│   ├── base_module.py     # Module API
│   ├── module_loader.py   # Dynamic module loader
│   ├── config_loader.py   # YAML config parser
│   ├── event_bus.py       # Event system
│   ├── logger.py          # Logging system
│   ├── ui_manager.py      # urwid UI framework
│   ├── battery_monitor.py # Battery monitoring
│   ├── thermal_monitor.py # Temperature monitoring
│   └── network_monitor.py # Network monitoring
│
├── modules/               # Plugins
│   ├── subghz/           # Sub-GHz module
│   ├── nfc/              # NFC module
│   ├── wifi/             # WiFi module
│   └── system/           # System utilities
│
├── config/               # Configuration
│   ├── main.yaml         # Main config
│   └── keybindings.yaml  # Hotkeys
│
├── logs/                 # Session logs
├── maps/                 # Wardriving maps
├── scripts/              # Macros
├── docs/                 # Documentation
├── tests/                # Tests
│
├── install.sh            # Installation script
├── requirements.txt      # Python dependencies
├── cyberdeck             # Launcher script
└── README.md             # This file
```

---

## ⚙️ Configuration

Edit `config/main.yaml` to configure:

```yaml
hardware:
  battery:
    enabled: true
    i2c_bus: 1
    i2c_address: 0x36

  nfc:
    enabled: true
    interface: "pn532_i2c"
    i2c_address: 0x24

  subghz:
    enabled: true
    spi_bus: 0
    default_freq: 433.92

modules:
  autoload:
    - "subghz"
    - "nfc"
    - "wifi"
    - "system"
```

---

## 🔌 Module Development

Create custom modules by extending `BaseModule`:

```python
from core.base_module import BaseModule

class MyModule(BaseModule):
    def __init__(self):
        super().__init__(
            name="My Module",
            version="1.0.0",
            priority=5
        )

    def get_menu_items(self):
        return [
            ("Action 1", self.action1),
            ("Action 2", self.action2),
        ]

    def action1(self):
        self.show_message("Action 1", "Executed!")
```

See `docs/MODULE_API.md` for complete API documentation.

---

## 📊 WiFi Attack Scenarios

### Scenario 1: Passive Monitor
- Passive handshake capture
- PMKID extraction
- No active attacks

### Scenario 2: Active Handshake Capture
- Deauthentication attacks
- WPA/WPA2 handshake capture
- Hashcat export

### Scenario 3: Dual Adapter Attack
- 2-adapter mode for efficiency
- Simultaneous passive/active

### Scenario 4: Wardriving
- GPS-synced network mapping
- Wigle CSV export
- Interactive HTML maps

### Scenario 5: Rogue AP
- Fake access point
- Captive portal
- Credential capture

### Scenario 6: PMKID Attack
- Clientless attack
- WPA2/WPA3 PMKID extraction

---

## 🗺️ Wardriving Maps

Generate interactive maps with GPS-tagged networks:

```bash
# Maps are saved to maps/ directory
# Open HTML files in browser for visualization
firefox maps/wardriving_20251117.html
```

Features:
- Color-coded by security (Open, WPA2, WPA3)
- Signal strength indicators
- Network details on click
- Distance/coverage statistics

---

## 🧪 Testing

Run the test suite:

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
pytest tests/ -v --cov=core --cov=modules
```

---

## 🔒 Security & Legal Notice

**⚠️ IMPORTANT: Use Responsibly**

This tool is designed for:
- **Authorized security testing** on networks you own or have explicit permission to test
- **Educational purposes** in controlled environments
- **CTF competitions** and security research
- **Defensive security** operations

**Illegal use is prohibited.** Unauthorized access to computer networks is a crime in most jurisdictions.

The developers assume no liability for misuse of this software.

---

## 📚 Documentation

- **User Guide**: `docs/USER_GUIDE.md`
- **Module API**: `docs/MODULE_API.md`
- **Hardware Setup**: `docs/HARDWARE_SETUP.md`
- **Development Guide**: `docs/DEVELOPMENT.md`

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## 📜 License

[armbian-gui Custom License — No Execution or Use](LICENSE).

Copyright (c) 2025-2026 shipmarty43. This is a custom source-available license,
not the MIT License or GPL. It allows copying, modification and redistribution
subject to its terms, but does not grant permission to run, execute or use the
software or binaries. It also prohibits dealing in the project in connection
with acts that violate applicable local law.

The author describes the project as a hobby and educational toy for a narrow
circle of specialists, not as malware or equipment for covert acquisition of
information. This statement is not a legal classification or an exception to
the no-use restriction. Third-party licenses and rights already granted for
earlier copies remain unaffected. See [LICENSE](LICENSE) for the complete terms.

---

## 🛟 Support

- **Issues**: https://github.com/shipmarty43/armbian-gui/issues
- **Documentation**: See `docs/` directory for detailed guides
- **Quick Start**: `QUICKSTART.md`
- **Root Usage**: `docs/ROOT_USAGE.md`

---

## 🙏 Acknowledgments

- **Flipper Zero**: Inspiration for Sub-GHz functionality
- **hcxtools**: WiFi attack framework
- **Meshtastic**: LoRa mesh networking
- **urwid**: Python TUI framework

---

## 🗺️ Roadmap

### v3.0 (Released - Current Stable)
- ✅ Core architecture with event bus
- ✅ Modular plugin system
- ✅ Full mouse and touchscreen support
- ✅ System monitors (battery, thermal, network)
- ✅ Root user support for hardware access
- ✅ Python 3.11+ with venv (no conda required)
- ✅ Hardware config: nRF24L01+ and CC1101 on shared SPI

### v3.1 (Released - Hardware Integration Complete)
- ✅ Full CC1101 hardware integration (Sub-GHz TX/RX)
- ✅ PN532 NFC/RFID driver (I2C/SPI)
- ✅ LoRa mesh networking (Meshtastic + Reticulum)
- ✅ SX1262 LoRa driver for Waveshare HAT
- ✅ GPS wardriving with NMEA parser
- ✅ SDR support (HackRF One + RTL-SDR via SoapySDR)

### v4.0 (Released - Advanced Features)
- ✅ Web UI (Flask-based remote access)
- ✅ Real-time API for all modules
- 🔲 Bluetooth terminal control (framework ready)
- 🔲 CAN Bus support (framework ready)
- 🔲 ML signal classification (framework ready)

### v4.1 (Planned)
- 🔲 Protocol decoders (Princeton, Came, Nice, KeeLoq)
- 🔲 NDEF record parsing
- 🔲 Audio demodulation (FM/AM)
- 🔲 LTE/5G modem integration

---

**Built with ❤️ for the security research community**

*Last updated: 2025-11-18 | Version 3.0*
