#!/bin/bash
# CyberDeck Interface - Installation Script

set -e

INSTALL_DIR="$(pwd)"
CONDA_DIR="$HOME/miniconda3"

echo "========================================"
echo "CyberDeck Interface v3.0 - Installation"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "Warning: Running as root. This is not recommended."
   echo "Press Ctrl+C to cancel or Enter to continue..."
   read
fi

# 1. Check for Miniconda
echo "[1/6] Checking for Conda..."
CONDA_INSTALLED=false

if ! command -v conda &> /dev/null; then
    echo "Conda not found. Installing Miniconda..."

    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" == "aarch64" ]; then
        MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
    else
        MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    fi

    wget $MINICONDA_URL -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p $CONDA_DIR
    rm /tmp/miniconda.sh

    # Initialize conda for bash
    $CONDA_DIR/bin/conda init bash

    echo "Miniconda installed successfully"
    CONDA_INSTALLED=true

    # Source conda for current session
    if [ -f "$CONDA_DIR/etc/profile.d/conda.sh" ]; then
        source "$CONDA_DIR/etc/profile.d/conda.sh"
    fi

    # Reinitialize conda in current shell
    eval "$($CONDA_DIR/bin/conda shell.bash hook)"

else
    echo "Conda found: $(which conda)"
    # Make sure conda is initialized in current session
    if [ -f "$CONDA_DIR/etc/profile.d/conda.sh" ]; then
        source "$CONDA_DIR/etc/profile.d/conda.sh"
    elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
    fi
fi

# 2. Create Conda environment
echo ""
echo "[2/6] Creating Conda environment..."
if conda env list | grep -q "^cyberdeck "; then
    echo "Environment 'cyberdeck' already exists. Updating..."
    conda env update -f environment.yml
else
    echo "Creating new environment 'cyberdeck'..."
    conda env create -f environment.yml
fi

# 3. Install Python dependencies
echo ""
echo "[3/6] Installing Python dependencies..."
eval "$(conda shell.bash hook)"
conda activate cyberdeck
pip install -r requirements.txt

# 4. Create necessary directories
echo ""
echo "[4/6] Creating directories..."
mkdir -p logs
mkdir -p maps
mkdir -p scripts
mkdir -p iq_samples
mkdir -p badusb_payloads

# 5. Set permissions (if needed)
echo ""
echo "[5/6] Setting permissions..."

# Make main.py executable
chmod +x core/main.py

# Create launcher script if it doesn't exist
if [ ! -f "cyberdeck" ]; then
    echo "Creating launcher script..."
    cat > cyberdeck <<'EOF'
#!/bin/bash
# CyberDeck Interface Launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

eval "$(conda shell.bash hook)"
conda activate cyberdeck

python core/main.py "$@"
EOF
    chmod +x cyberdeck
else
    echo "Launcher script already exists, skipping..."
    chmod +x cyberdeck
fi

# 6. Optional: Add to PATH
echo ""
echo "[6/6] Creating launcher..."
echo "Launcher script created: ./cyberdeck"

# Add alias suggestion
echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "To run CyberDeck Interface:"
echo "  1. ./cyberdeck"
echo ""
echo "Or activate the environment manually:"
echo "  1. conda activate cyberdeck"
echo "  2. python core/main.py"
echo ""
echo "Optional: Add alias to ~/.bashrc:"
echo "  echo 'alias cyberdeck=\"cd $INSTALL_DIR && ./cyberdeck\"' >> ~/.bashrc"
echo ""
echo "Configuration file: config/main.yaml"
echo "Edit this file to match your hardware setup."
echo ""
echo "For hardware interfaces (I2C, SPI, GPIO), you may need to:"
echo "  - Install system dependencies (see docs/HARDWARE_SETUP.md)"
echo "  - Add your user to appropriate groups (i2c, spi, gpio, dialout)"
echo "  - Configure udev rules for USB devices"
echo ""
echo "See README.md for detailed documentation."
echo ""
