# Quick Start Guide

## Installation

```bash
# 1. Run the installation script
bash install.sh

# 2. The installation will:
#    - Check for Python 3.8+
#    - Install pip and venv if needed
#    - Create virtual environment in ./venv
#    - Install all Python dependencies
#    - Set up directory structure

# 3. If Python is missing, install it first:
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
bash install.sh
```

## Running the Application

### Option 1: Using the launcher (with hardware access)
```bash
# For full GPIO/SPI/I2C access (recommended for Orange Pi/Raspberry Pi)
sudo ./cyberdeck
```

### Option 2: Running as regular user (UI testing only)
```bash
# Without hardware access - for UI testing
./cyberdeck
```

### Option 3: Manual activation
```bash
source venv/bin/activate
python core/main.py

# Or with sudo for hardware:
sudo ./venv/bin/python core/main.py
```

### Why sudo?

CyberDeck needs root access for:
- 🔌 GPIO pins (nRF24, CC1101 chip select)
- 📡 SPI devices (/dev/spidev*)
- 🔧 I2C devices (/dev/i2c*)
- 🖥️ USB Gadget (BadUSB module)
- 📻 Raw WiFi sockets (monitor mode)

**Alternative:** Add user to hardware groups (see [docs/ROOT_USAGE.md](docs/ROOT_USAGE.md))

## First Steps

1. **Launch the application**: `./cyberdeck`

2. **Navigate the menu**:
   - Use `j/k` or arrow keys to navigate
   - Press `Enter` to select
   - Press `q` to quit
   - Click with mouse or tap on touchscreen

3. **Try the modules**:
   - **[1] Sub-GHz Analyzer**: Demo of 433MHz signal capture
   - **[2] NFC Tools**: Demo of NFC card operations
   - **[3] WiFi Security**: 6 attack scenarios (demo)
   - **[4] System Tools**: System information and monitoring

4. **View system status**:
   - Top status bar shows battery, WiFi signal, temperature, time, IP

## Configuration

Edit `config/main.yaml` to:
- Enable/disable hardware modules
- Configure I2C, SPI, GPIO pins
- Set module priorities
- Configure WiFi scenarios

Example:
```yaml
hardware:
  nfc:
    enabled: true
    interface: "pn532_i2c"
    i2c_bus: 0
    i2c_address: 0x24
```

## Module Development

Create custom modules:

1. Create directory: `modules/mymodule/`
2. Add `__init__.py` and `mymodule.py`
3. Extend `BaseModule` class
4. See `docs/MODULE_API.md` for details

## Troubleshooting

**Problem**: urwid import error
```bash
source venv/bin/activate
pip install urwid
```

**Problem**: Permission denied for I2C/SPI
```bash
sudo usermod -a -G i2c,spi,gpio $USER
# Then logout and login again
```

**Problem**: Module not loading
- Check `logs/` directory for error messages
- Verify hardware is connected
- Check module configuration in `config/main.yaml`

## Hardware Integration

This is a **demo implementation**. To integrate real hardware:

1. **CC1101 (Sub-GHz)**:
   - Connect via SPI
   - Implement CC1101 register read/write in `modules/subghz/cc1101_driver.py`

2. **PN532 (NFC)**:
   - Install: `pip install nfcpy`
   - Connect via I2C or SPI
   - Uncomment nfcpy imports in `modules/nfc/nfc_module.py`

3. **WiFi Adapters**:
   - Ensure monitor mode capable adapters
   - Install: `apt install hcxtools hcxdumptool`

## Support

- **Documentation**: See `docs/` directory
- **Module API**: `docs/MODULE_API.md`
- **Issues**: https://github.com/shipmarty43/armbian-gui/issues

## Legal Notice

⚠️ **Use responsibly!** Only test networks you own or have explicit permission to test.

---

**Ready to hack!** 🚀
