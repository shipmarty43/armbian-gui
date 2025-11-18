#!/bin/bash
# CyberDeck Interface - Installation Script

set -e

INSTALL_DIR="$(pwd)"
VENV_DIR="$INSTALL_DIR/venv"

echo "========================================"
echo "CyberDeck Interface v4.0 - Installation"
echo "Enhanced Mobile Security Platform"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "Running as root - Hardware access enabled"
   echo "Note: Virtual environment will be created in: $VENV_DIR"
else
   echo "Running as user: $USER"
   echo "Note: You may need root privileges for hardware access (GPIO/SPI/I2C)"
fi

# 1. Check for Python 3
echo "[1/5] Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3.11 or higher:"
    echo "  sudo apt update"
    echo "  sudo apt install python3.11 python3.11-dev python3.11-venv python3-pip build-essential"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Python found: $PYTHON_VERSION"

# Check Python version (need 3.11+)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "ERROR: Python 3.11 or higher required, found $PYTHON_VERSION"
    echo "Please install Python 3.11:"
    echo "  sudo apt update"
    echo "  sudo apt install python3.11 python3.11-dev python3.11-venv python3-pip build-essential"
    exit 1
fi

# 2. Install system dependencies
echo ""
echo "[2/5] Installing system dependencies..."

# Check if running as root or can use sudo
if [ "$EUID" -eq 0 ]; then
    PKG_INSTALL="apt install -y"
    APT_UPDATE="apt update"
else
    PKG_INSTALL="sudo apt install -y"
    APT_UPDATE="sudo apt update"
fi

echo "Updating package lists..."
$APT_UPDATE

# Install Python development packages and build tools
echo "Installing Python 3.11 development packages..."
$PKG_INSTALL python3.11-dev python3.11-venv python3-pip build-essential

# Verify pip
if ! python3 -m pip --version &> /dev/null; then
    echo "ERROR: pip installation failed"
    exit 1
fi

echo "System dependencies installed:"
echo "  - python3.11-dev (for building C extensions)"
echo "  - python3.11-venv (for virtual environments)"
echo "  - build-essential (for compiling packages)"
echo "  - pip version: $(python3 -m pip --version)"

# 3. Create virtual environment
echo ""
echo "[3/5] Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at: $VENV_DIR"
    echo "Removing old virtual environment..."
    rm -rf "$VENV_DIR"
fi

echo "Creating new virtual environment..."
python3 -m venv "$VENV_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
python -m pip install --upgrade pip

# 4. Install Python dependencies
echo ""
echo "[4/5] Installing Python dependencies..."
echo "This may take a few minutes..."

pip install -r requirements.txt

# Install OPi.GPIO if on ARM platform
ARCH=$(uname -m)
if [ "$ARCH" == "aarch64" ] || [ "$ARCH" == "armv7l" ]; then
    echo ""
    echo "ARM platform detected ($ARCH). Installing OPi.GPIO..."
    if pip install OPi.GPIO; then
        echo "✓ OPi.GPIO installed successfully"
    else
        echo "⚠ WARNING: Failed to install OPi.GPIO"
        echo "  You may need to install it manually for GPIO support"
    fi
else
    echo "⚠ Non-ARM platform detected ($ARCH). Skipping OPi.GPIO installation."
    echo "  Hardware modules may not work without ARM platform."
fi

# Optional dependencies installation
echo ""
read -p "Install optional dependencies? (GPS, SDR, LoRa mesh) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Installing optional dependencies..."

    # SDR support (SoapySDR)
    echo "  - Installing SoapySDR for HackRF/RTL-SDR support..."
    $PKG_INSTALL soapysdr-tools python3-soapysdr libsoapysdr-dev || echo "    ⚠ SoapySDR installation failed"

    # Install optional Python packages
    echo "  - Installing optional Python packages..."
    pip install meshtastic rns || echo "    ⚠ Some optional packages failed to install"

    echo "✓ Optional dependencies installed"
else
    echo "Skipping optional dependencies. You can install them later by editing requirements.txt"
fi

# 5. Create necessary directories
echo ""
echo "[5/5] Creating directories and setting permissions..."
mkdir -p logs
mkdir -p maps
mkdir -p scripts
mkdir -p iq_samples
mkdir -p badusb_payloads
mkdir -p modules/captures
mkdir -p modules/recordings

# Make main.py executable
chmod +x core/main.py

# Make launcher script executable
if [ -f "cyberdeck" ]; then
    chmod +x cyberdeck
fi

echo "✓ Directories created"

# Configure hardware interfaces (Orange Pi specific)
echo ""
echo "Configuring hardware interfaces..."

# Enable SPI
if [ -f "/boot/orangepiEnv.txt" ]; then
    echo "  - Orange Pi detected. Checking SPI configuration..."
    if grep -q "overlays=spi-spidev" /boot/orangepiEnv.txt 2>/dev/null; then
        echo "    ✓ SPI already enabled"
    else
        read -p "    Enable SPI interface? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if [ "$EUID" -eq 0 ]; then
                echo "overlays=spi-spidev" >> /boot/orangepiEnv.txt
                echo "    ✓ SPI enabled (reboot required)"
            else
                echo "    ⚠ Need root to enable SPI. Run: sudo bash -c 'echo overlays=spi-spidev >> /boot/orangepiEnv.txt'"
            fi
        fi
    fi
fi

# Add user to hardware groups
if [ "$EUID" -ne 0 ]; then
    echo ""
    read -p "Add current user to hardware groups (gpio, spi, i2c, dialout)? [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo usermod -a -G gpio,spi,i2c,dialout $USER 2>/dev/null || echo "  ⚠ Some groups may not exist"
        echo "  ✓ User added to hardware groups (re-login required)"
    fi
fi

# Post-installation verification
echo ""
echo "Running post-installation checks..."

# Check virtual environment
if [ -f "$VENV_DIR/bin/python" ]; then
    echo "  ✓ Virtual environment created successfully"
else
    echo "  ✗ ERROR: Virtual environment not found!"
    exit 1
fi

# Check main script
if [ -f "core/main.py" ]; then
    echo "  ✓ Main application found"
    # Try to import modules
    if "$VENV_DIR/bin/python" -c "import urwid, numpy, yaml" 2>/dev/null; then
        echo "  ✓ Core dependencies verified"
    else
        echo "  ⚠ WARNING: Some core dependencies may not be installed correctly"
    fi
else
    echo "  ✗ ERROR: Main application not found!"
    exit 1
fi

# Check hardware interfaces
echo ""
echo "Hardware interface status:"
[ -e /dev/spidev0.0 ] && echo "  ✓ SPI: Available (/dev/spidev0.0)" || echo "  ✗ SPI: Not available"
[ -e /dev/i2c-0 ] && echo "  ✓ I2C: Available (/dev/i2c-0)" || echo "  ✗ I2C: Not available"
[ -e /dev/gpiochip0 ] && echo "  ✓ GPIO: Available" || echo "  ⚠ GPIO: Not detected"
[ -e /dev/ttyUSB0 ] || [ -e /dev/ttyACM0 ] && echo "  ✓ Serial: USB devices found" || echo "  ⚠ Serial: No USB serial devices"

# Installation complete
echo ""
echo "========================================"
echo "✓ Installation Complete!"
echo "========================================"
echo ""
echo "Virtual environment: $VENV_DIR"
echo ""
echo "QUICK START:"
echo "------------"
echo "1. Run main interface:"
echo "   source venv/bin/activate"
echo "   python core/main.py"
echo ""
echo "2. Run web UI (remote access):"
echo "   source venv/bin/activate"
echo "   python webui_server.py"
echo "   # Access at http://[orange-pi-ip]:5000"
echo ""
echo "3. Use launcher script (recommended):"
echo "   ./cyberdeck"
echo ""
echo "HARDWARE CONFIGURATION:"
echo "----------------------"
echo "Configuration file: config/main.yaml"
echo "Edit this file to match your hardware setup:"
echo "  - GPIO pins for LoRa module (SX1262)"
echo "  - Serial ports for GPS"
echo "  - I2C/SPI devices"
echo ""
echo "FEATURES AVAILABLE:"
echo "------------------"
echo "  • Sub-GHz: CC1101 transceiver (300-928 MHz)"
echo "  • LoRa Mesh: Meshtastic protocol on SX1262"
echo "  • GPS: Wardriving with NMEA parser"
echo "  • SDR: HackRF One / RTL-SDR support"
echo "  • NFC/RFID: PN532 reader"
echo "  • Web UI: Remote access interface"
echo ""
echo "PERMISSIONS:"
echo "-----------"
if [ "$EUID" -eq 0 ]; then
    echo "  ✓ Running as root - full hardware access"
else
    echo "  For hardware access without root:"
    echo "    sudo usermod -a -G gpio,spi,i2c,dialout $USER"
    echo "    # Then logout and login again"
fi
echo ""
echo "NEXT STEPS:"
echo "----------"
echo "  1. Edit config/main.yaml for your hardware"
echo "  2. If you enabled SPI, reboot: sudo reboot"
echo "  3. Connect your hardware (LoRa HAT, GPS, etc.)"
echo "  4. Run the application!"
echo ""
echo "DOCUMENTATION:"
echo "-------------"
echo "  README.md       - Full documentation"
echo "  config/*.yaml   - Configuration examples"
echo "  modules/        - Module-specific docs"
echo ""
echo "For issues and updates:"
echo "  https://github.com/yourusername/armbian-gui"
echo ""
echo "Happy hacking! 🔧📡"
echo ""
