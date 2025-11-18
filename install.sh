#!/bin/bash
# CyberDeck Interface - Installation Script

set -e

INSTALL_DIR="$(pwd)"
VENV_DIR="$INSTALL_DIR/venv"

echo "========================================"
echo "CyberDeck Interface v3.0 - Installation"
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
    echo "  sudo apt install python3.11 python3-pip python3-venv"
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
    echo "  sudo apt install python3.11 python3.11-venv"
    exit 1
fi

# 2. Check for pip and venv
echo ""
echo "[2/5] Checking for pip and venv..."
if ! python3 -m pip --version &> /dev/null; then
    echo "pip not found. Installing..."
    sudo apt update
    sudo apt install -y python3-pip
fi

if ! python3 -m venv --help &> /dev/null; then
    echo "venv not found. Installing..."
    sudo apt install -y python3-venv
fi

echo "pip version: $(python3 -m pip --version)"

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
    echo "ARM platform detected. Installing OPi.GPIO..."
    if pip install OPi.GPIO; then
        echo "OPi.GPIO installed successfully"
    else
        echo "WARNING: Failed to install OPi.GPIO"
        echo "You may need to install it manually for GPIO support"
    fi
fi

# 5. Create necessary directories
echo ""
echo "[5/5] Creating directories and setting permissions..."
mkdir -p logs
mkdir -p maps
mkdir -p scripts
mkdir -p iq_samples
mkdir -p badusb_payloads

# Make main.py executable
chmod +x core/main.py

# Make launcher script executable
if [ -f "cyberdeck" ]; then
    chmod +x cyberdeck
fi

# Installation complete
echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "Virtual environment created at: $VENV_DIR"
echo ""
echo "To run CyberDeck Interface:"
echo "  ./cyberdeck"
echo ""
echo "Or activate the virtual environment manually:"
echo "  source venv/bin/activate"
echo "  python core/main.py"
echo ""
echo "Configuration file: config/main.yaml"
echo "Edit this file to match your hardware setup."
echo ""
echo "For hardware interfaces (I2C, SPI, GPIO), you may need to:"
echo "  - Run as root: sudo ./cyberdeck"
echo "  - Add your user to groups: sudo usermod -a -G gpio,spi,i2c,dialout \$USER"
echo "  - Configure udev rules for USB devices"
echo ""
echo "See README.md for detailed documentation."
echo ""
