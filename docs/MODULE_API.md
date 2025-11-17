# Module API Documentation

## Overview

CyberDeck Interface uses a modular plugin architecture. All modules must extend the `BaseModule` class and implement required methods.

---

## Quick Start

### Minimal Module Example

```python
from core.base_module import BaseModule
from typing import List, Tuple, Callable

class MyModule(BaseModule):
    def __init__(self):
        super().__init__(
            name="My Module",
            version="1.0.0",
            priority=5  # 1-10, where 1 is highest
        )

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Return menu items for this module"""
        return [
            ("Action 1", self.action1),
            ("Action 2", self.action2),
        ]

    def action1(self):
        self.show_message("Action 1", "Hello from Action 1!")

    def action2(self):
        self.show_message("Action 2", "Hello from Action 2!")
```

---

## BaseModule Reference

### Constructor

```python
def __init__(self, name: str, version: str, priority: int = 5)
```

**Parameters:**
- `name`: Module display name (shown in UI)
- `version`: Module version (semver format)
- `priority`: Load priority (1-10, where 1 = highest)

---

### Lifecycle Methods

#### `on_load()`
Called when module is loaded during startup.

**Use for:**
- Hardware initialization
- Configuration loading
- Resource allocation

```python
def on_load(self):
    self.log_info("Initializing hardware...")
    # Initialize SPI, I2C, GPIO, etc.
```

#### `on_unload()`
Called when module is unloaded during shutdown.

**Use for:**
- Cleanup resources
- Close hardware connections
- Save state

```python
def on_unload(self):
    self.log_info("Cleaning up...")
    if hasattr(self, 'spi'):
        self.spi.close()
```

#### `on_enable()` / `on_disable()`
Called when module is enabled/disabled by user.

---

### UI Methods

#### `get_menu_items()` (Required)
Returns list of menu items for the module.

```python
def get_menu_items(self) -> List[Tuple[str, Callable]]:
    return [
        ("Read Card", self.read_card),
        ("Write Card", self.write_card),
        ("Settings", self.show_settings),
    ]
```

#### `get_status_widget()`
Returns text for status bar (optional).

```python
def get_status_widget(self) -> Optional[str]:
    return f"NFC: {self.status}"
```

#### `get_hotkeys()`
Returns module-specific hotkeys (optional).

```python
def get_hotkeys(self) -> Dict[str, Callable]:
    return {
        'r': self.read_card,
        'w': self.write_card,
    }
```

---

### UI Helper Methods

#### `show_message(message: str, title: str = "Info")`
Display an information dialog.

```python
self.show_message("Operation Complete", "Card read successfully!")
```

#### `show_error(message: str)`
Display an error dialog.

```python
self.show_error("Failed to initialize hardware")
```

#### `get_user_input(prompt: str, default: str = "") -> str`
Request text input from user.

```python
freq = self.get_user_input("Enter frequency (MHz):", "433.92")
```

#### `show_menu(title: str, items: List[str]) -> int`
Display a selection menu.

```python
choice = self.show_menu("Select Card Type", [
    "Mifare Classic 1K",
    "Mifare Classic 4K",
    "Ultralight"
])
```

#### `show_progress(current: int, total: int, message: str = "")`
Display a progress bar.

```python
for i in range(100):
    self.show_progress(i, 100, "Processing...")
    # do work
```

---

### Logging Methods

#### `log_info(message: str)`
Log informational message.

```python
self.log_info("Scanning for cards...")
```

#### `log_warning(message: str)`
Log warning message.

```python
self.log_warning("No hardware detected")
```

#### `log_error(message: str)`
Log error message.

```python
self.log_error(f"Failed to read sector: {e}")
```

#### `log_debug(message: str)`
Log debug message (only shown when log_level = DEBUG).

```python
self.log_debug(f"Raw data: {data}")
```

---

### Configuration Methods

#### `load_config(config_path: str) -> Dict[str, Any]`
Load YAML configuration file.

```python
def on_load(self):
    self.config = self.load_config("config/mymodule.yaml")
    self.enabled = self.config.get('enabled', True)
```

#### `save_config(config: Dict[str, Any], config_path: str)`
Save configuration to YAML file.

```python
self.save_config(self.config, "config/mymodule.yaml")
```

---

### Data Storage Methods

#### `save_data(filename: str, data: Any, format: str = "json")`
Save data to file.

**Formats:** `"json"`, `"binary"`, `"text"`

```python
# Save JSON
self.save_data("data.json", {"key": "value"}, format="json")

# Save binary
self.save_data("capture.bin", binary_data, format="binary")

# Save text
self.save_data("log.txt", "Log entry", format="text")
```

#### `load_data(filename: str, format: str = "json") -> Any`
Load data from file.

```python
data = self.load_data("data.json", format="json")
```

---

### Inter-Module Communication

#### `get_module(module_name: str) -> Optional[BaseModule]`
Get instance of another module.

```python
gps_module = self.get_module("GPS Tracker")
if gps_module:
    position = gps_module.get_position()
```

#### `subscribe_event(event_name: str, callback: Callable)`
Subscribe to events from other modules.

```python
def on_load(self):
    self.subscribe_event("gps.position_update", self.on_gps_update)

def on_gps_update(self, data):
    lat = data['latitude']
    lon = data['longitude']
    self.log_info(f"GPS: {lat}, {lon}")
```

#### `emit_event(event_name: str, data: Dict[str, Any])`
Emit events for other modules to receive.

```python
self.emit_event("nfc.card_detected", {
    'uid': "04:12:34:56",
    'type': 'Mifare Classic 1K'
})
```

---

## Complete Example: I2C Scanner Module

```python
from core.base_module import BaseModule
from typing import List, Tuple, Callable

try:
    from smbus2 import SMBus
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False


class I2CScannerModule(BaseModule):
    """Simple I2C bus scanner module"""

    def __init__(self):
        super().__init__(
            name="I2C Scanner",
            version="1.0.0",
            priority=8
        )
        self.devices = []

    def on_load(self):
        """Initialize module"""
        if not SMBUS_AVAILABLE:
            self.log_error("smbus2 not available")
            self.enabled = False
            return

        self.log_info("I2C Scanner module loaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Menu items"""
        return [
            ("Scan I2C Bus 0", lambda: self.scan_bus(0)),
            ("Scan I2C Bus 1", lambda: self.scan_bus(1)),
            ("View Devices", self.view_devices),
        ]

    def get_status_widget(self) -> str:
        """Status bar widget"""
        if self.devices:
            return f"I2C: {len(self.devices)} devices"
        return "I2C: Ready"

    def scan_bus(self, bus_num: int):
        """Scan I2C bus for devices"""
        self.log_info(f"Scanning I2C bus {bus_num}...")
        self.devices.clear()

        try:
            with SMBus(bus_num) as bus:
                for addr in range(0x03, 0x78):
                    try:
                        bus.read_byte(addr)
                        self.devices.append(hex(addr))
                        self.log_debug(f"Found device at {hex(addr)}")
                    except:
                        pass

            if self.devices:
                result = f"Found {len(self.devices)} devices:\n\n"
                result += ", ".join(self.devices)
                self.show_message(f"I2C Bus {bus_num}", result)
            else:
                self.show_message(f"I2C Bus {bus_num}", "No devices found")

        except Exception as e:
            self.show_error(f"Failed to scan bus {bus_num}: {e}")

    def view_devices(self):
        """View previously found devices"""
        if not self.devices:
            self.show_message("Devices", "No devices scanned yet")
            return

        device_list = "Last Scan Results:\n\n"
        for addr in self.devices:
            device_list += f"  • {addr}\n"

        self.show_message("I2C Devices", device_list)
```

---

## Event System

### Standard Events

Modules can emit and subscribe to these standard events:

**GPS Events:**
- `gps.position_update`: GPS position changed
  - Data: `{latitude: float, longitude: float, altitude: float}`

**NFC Events:**
- `nfc.card_detected`: NFC card detected
  - Data: `{uid: str, type: str}`

**WiFi Events:**
- `wifi.handshake_captured`: Handshake captured
  - Data: `{ssid: str, bssid: str, filename: str}`

**Custom Events:**
You can define custom events using the format: `module_name.event_name`

---

## Module Priority

Modules load in priority order (1 = first):

| Priority | Use Case                    | Examples           |
|----------|-----------------------------|--------------------|
| 1        | Critical hardware           | Sub-GHz, WiFi      |
| 2-3      | Important peripherals       | LoRa, NFC          |
| 4-6      | Optional hardware           | SDR, GPS           |
| 7-9      | Utilities                   | Bluetooth, RFID    |
| 10       | System tools                | File manager, etc. |

---

## Best Practices

1. **Always check hardware availability** in `on_load()`
2. **Use try/except** for hardware operations
3. **Log important actions** for debugging
4. **Clean up resources** in `on_unload()`
5. **Keep UI responsive** - don't block on long operations
6. **Use events** for loose coupling between modules
7. **Document your module** with docstrings

---

## Testing Your Module

Create a test file in `tests/test_mymodule.py`:

```python
import unittest
from modules.mymodule import MyModule

class TestMyModule(unittest.TestCase):
    def setUp(self):
        self.module = MyModule()

    def test_initialization(self):
        self.assertEqual(self.module.name, "My Module")
        self.assertTrue(self.module.enabled)

    def test_menu_items(self):
        items = self.module.get_menu_items()
        self.assertGreater(len(items), 0)
```

---

## Module Installation

1. Create module directory: `modules/mymodule/`
2. Add `__init__.py`:
   ```python
   from .mymodule import MyModule
   __all__ = ['MyModule']
   ```
3. Add main module file: `mymodule.py`
4. (Optional) Add config: `config/mymodule.yaml`
5. Update `config/main.yaml` to autoload your module

---

## Further Reading

- `core/base_module.py`: Full BaseModule source
- `modules/subghz/`: Example hardware module
- `modules/system/`: Example utility module
- `docs/DEVELOPMENT.md`: Development guide

---

**Happy module development!**
