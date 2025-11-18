# CyberDeck Interface v3.0

**Mobile Security Research Platform for Orange Pi / Raspberry Pi**

A modular, terminal-based interface for wireless protocol research, NFC/RFID analysis, SDR experimentation, and WiFi security testing.

---

## 🚀 Features

### Core Capabilities
- **Sub-GHz Analysis (CC1101)**: Capture and replay 433MHz signals (300-928MHz range)
- **NFC/RFID Tools (PN532)**: Read, emulate, and bruteforce Mifare cards
- **WiFi Security**: 6 attack scenarios with hcxtools, wardriving with GPS
- **LoRa Mesh (SX1262)**: Meshtastic and Reticulum integration
- **SDR Analysis**: HackRF One and RTL-SDR support
- **BadUSB**: USB Gadget HID keyboard emulation
- **GPS Tracking**: Geolocation and wardriving maps

### Architecture
- **Modular Plugin System**: Dynamic module loading with priority-based initialization
- **Vim-Style Interface**: curses-based TUI with vim navigation
- **Event Bus**: Pub/sub system for inter-module communication
- **System Monitoring**: Battery (MAX17043), temperature, WiFi/LTE signal tracking
- **Session Logging**: Complete audit trail of all operations

---

## 📋 Requirements

### Hardware
- **Orange Pi Zero 2W** or **Orange Pi 3**
- Optional peripherals:
  - PN532 NFC/RFID module (I2C/SPI)
  - CC1101 Sub-GHz transceiver (SPI)
  - SX1262 LoRa module (SPI)
  - MAX17043 battery monitor (I2C)
  - GPS module (UART)
  - 2x WiFi adapters with monitor mode (e.g., RTL8812AU, MT7612U)
  - HackRF One or RTL-SDR (USB)
  - Proxmark3 V5.0 (USB)

### Software
- **OS**: Armbian (Ubuntu 22.04 base)
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
├── environment.yml       # Conda environment
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
conda activate cyberdeck
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

MIT License (see LICENSE file)

---

## 🛟 Support

- **Issues**: https://github.com/shipmarty43/armbian-gui/issues
- **Documentation**: https://cyberdeck-docs.example.com
- **Community**: Discord/Telegram (links TBD)

---

## 🙏 Acknowledgments

- **Flipper Zero**: Inspiration for Sub-GHz functionality
- **hcxtools**: WiFi attack framework
- **Meshtastic**: LoRa mesh networking
- **urwid**: Python TUI framework

---

## 🗺️ Roadmap

### v1.0 (Current)
- ✅ Core architecture
- ✅ Module system
- ✅ Sub-GHz, NFC, WiFi modules (demo)
- ✅ System monitors

### v1.1 (Planned)
- 🔲 Full hardware integration (CC1101, PN532)
- 🔲 LoRa/Meshtastic implementation
- 🔲 GPS wardriving
- 🔲 SDR support (HackRF/RTL-SDR)

### v2.0 (Future)
- 🔲 Web UI (remote access)
- 🔲 Bluetooth terminal control
- 🔲 CAN Bus support
- 🔲 ML signal classification

---

**Built with ❤️ for the security research community**

*Last updated: 2025-11-17*
