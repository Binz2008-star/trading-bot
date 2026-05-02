#!/bin/bash
# Roben Trading AI Bot - Quick Setup Script

echo "========================================"
echo "    Roben Trading AI Bot Setup"
echo "========================================"
echo

# Check Python
echo "[1/5] Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found!"
    echo "Please install Python 3.8+ first"
    exit 1
fi
echo "SUCCESS: Python3 found"

# Check pip
echo "[2/5] Checking pip installation..."
if ! command -v pip3 &> /dev/null; then
    echo "ERROR: pip3 not found!"
    exit 1
fi
echo "SUCCESS: pip3 found"

# Create installation directory
INSTALL_DIR="$HOME/RobenTradingBot"
echo "[3/5] Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy files
echo "[4/5] Copying system files..."
if [ -d "src" ]; then cp -r src/* "$INSTALL_DIR/"; fi
if [ -d "config" ]; then cp -r config/* "$INSTALL_DIR/"; fi
if [ -d "docs" ]; then cp -r docs/* "$INSTALL_DIR/"; fi
cp -f *.py "$INSTALL_DIR/" 2>/dev/null || true
cp -f *.env "$INSTALL_DIR/" 2>/dev/null || true
cp -f *.json "$INSTALL_DIR/" 2>/dev/null || true

# Install requirements
echo "[5/5] Installing required packages..."
pip3 install python-dotenv flask flask-cors requests pandas numpy

# Create startup script
echo "Creating startup script..."
cat > "$INSTALL_DIR/start_roben_bot.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Roben Trading AI Bot..."
python3 roben_enhanced_trading_system.py
EOF

chmod +x "$INSTALL_DIR/start_roben_bot.sh"

# Create desktop shortcut (for Linux with desktop environment)
if [ -d "$HOME/Desktop" ]; then
    echo "Creating desktop shortcut..."
    cat > "$HOME/Desktop/Roben Trading AI Bot.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Roben Trading AI Bot
Comment=Advanced AI Trading System
Exec=$INSTALL_DIR/start_roben_bot.sh
Icon=$INSTALL_DIR/roben_icon.png
Terminal=true
Categories=Office;Finance;
EOF
    chmod +x "$HOME/Desktop/Roben Trading AI Bot.desktop"
fi

echo
echo "========================================"
echo "    Installation Complete!"
echo "========================================"
echo
echo "Installation Directory: $INSTALL_DIR"
echo "Desktop Shortcut: Created (if supported)"
echo
echo "Next Steps:"
echo "1. Edit .env file and add your API keys"
echo "2. Run: $INSTALL_DIR/start_roben_bot.sh"
echo "3. Open browser: http://localhost:8082"
echo
echo "Support: support@robentrading.ai"
echo
echo "WARNING: Start with small amounts for testing!"
echo

