"""
USB Gadget Controller - управление USB Gadget для BadUSB
"""

import os
import time
import logging
from typing import Optional, Dict, List


class USBGadgetController:
    """Controller for USB Gadget (HID Keyboard)"""

    # HID Report Descriptor for standard keyboard
    HID_REPORT_DESCRIPTOR = bytes([
        0x05, 0x01,  # Usage Page (Generic Desktop)
        0x09, 0x06,  # Usage (Keyboard)
        0xA1, 0x01,  # Collection (Application)
        0x05, 0x07,  #   Usage Page (Key Codes)
        0x19, 0xE0,  #   Usage Minimum (224)
        0x29, 0xE7,  #   Usage Maximum (231)
        0x15, 0x00,  #   Logical Minimum (0)
        0x25, 0x01,  #   Logical Maximum (1)
        0x75, 0x01,  #   Report Size (1)
        0x95, 0x08,  #   Report Count (8)
        0x81, 0x02,  #   Input (Data, Variable, Absolute)
        0x95, 0x01,  #   Report Count (1)
        0x75, 0x08,  #   Report Size (8)
        0x81, 0x01,  #   Input (Constant)
        0x95, 0x05,  #   Report Count (5)
        0x75, 0x01,  #   Report Size (1)
        0x05, 0x08,  #   Usage Page (LEDs)
        0x19, 0x01,  #   Usage Minimum (1)
        0x29, 0x05,  #   Usage Maximum (5)
        0x91, 0x02,  #   Output (Data, Variable, Absolute)
        0x95, 0x01,  #   Report Count (1)
        0x75, 0x03,  #   Report Size (3)
        0x91, 0x01,  #   Output (Constant)
        0x95, 0x06,  #   Report Count (6)
        0x75, 0x08,  #   Report Size (8)
        0x15, 0x00,  #   Logical Minimum (0)
        0x25, 0x65,  #   Logical Maximum (101)
        0x05, 0x07,  #   Usage Page (Key Codes)
        0x19, 0x00,  #   Usage Minimum (0)
        0x29, 0x65,  #   Usage Maximum (101)
        0x81, 0x00,  #   Input (Data, Array)
        0xC0         # End Collection
    ])

    # USB HID Keycodes
    KEYCODES = {
        'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
        'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
        'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
        's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
        'y': 0x1C, 'z': 0x1D,
        '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22,
        '6': 0x23, '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
        'ENTER': 0x28, 'ESC': 0x29, 'BACKSPACE': 0x2A, 'TAB': 0x2B,
        'SPACE': 0x2C, '-': 0x2D, '=': 0x2E, '[': 0x2F, ']': 0x30,
        '\\': 0x31, ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36,
        '.': 0x37, '/': 0x38,
        'F1': 0x3A, 'F2': 0x3B, 'F3': 0x3C, 'F4': 0x3D, 'F5': 0x3E,
        'F6': 0x3F, 'F7': 0x40, 'F8': 0x41, 'F9': 0x42, 'F10': 0x43,
        'F11': 0x44, 'F12': 0x45,
        'UP': 0x52, 'DOWN': 0x51, 'LEFT': 0x50, 'RIGHT': 0x4F,
        'GUI': 0xE3,  # Windows/Super key
    }

    # Modifier keys (bit positions in modifier byte)
    MODIFIERS = {
        'CTRL': 0x01,
        'SHIFT': 0x02,
        'ALT': 0x04,
        'GUI': 0x08,  # Windows/Super key
    }

    def __init__(self, gadget_name: str = "cyberdeck_hid"):
        """
        Initialize USB Gadget controller.

        Args:
            gadget_name: Name of USB gadget
        """
        self.logger = logging.getLogger("cyberdeck.badusb")
        self.gadget_name = gadget_name
        self.gadget_path = f"/sys/kernel/config/usb_gadget/{gadget_name}"
        self.hid_dev = None
        self.enabled = False

    def setup_gadget(self, vendor_id: str = "0x1d6b", product_id: str = "0x0104",
                    manufacturer: str = "CyberDeck", product: str = "BadUSB HID") -> bool:
        """
        Setup USB Gadget as HID keyboard.

        Args:
            vendor_id: USB vendor ID
            product_id: USB product ID
            manufacturer: Manufacturer string
            product: Product string

        Returns:
            bool: True if successful
        """
        try:
            # Check if configfs is mounted
            if not os.path.exists("/sys/kernel/config/usb_gadget"):
                self.logger.error("USB Gadget configfs not mounted")
                self.logger.info("Try: modprobe libcomposite")
                return False

            # Create gadget directory
            os.makedirs(self.gadget_path, exist_ok=True)

            # Set USB device descriptor
            self._write_file(f"{self.gadget_path}/idVendor", vendor_id)
            self._write_file(f"{self.gadget_path}/idProduct", product_id)
            self._write_file(f"{self.gadget_path}/bcdDevice", "0x0100")
            self._write_file(f"{self.gadget_path}/bcdUSB", "0x0200")

            # Create English strings
            strings_path = f"{self.gadget_path}/strings/0x409"
            os.makedirs(strings_path, exist_ok=True)
            self._write_file(f"{strings_path}/serialnumber", "cyberdeck001")
            self._write_file(f"{strings_path}/manufacturer", manufacturer)
            self._write_file(f"{strings_path}/product", product)

            # Create configuration
            config_path = f"{self.gadget_path}/configs/c.1"
            os.makedirs(config_path, exist_ok=True)
            config_strings_path = f"{config_path}/strings/0x409"
            os.makedirs(config_strings_path, exist_ok=True)
            self._write_file(f"{config_strings_path}/configuration", "HID Keyboard")
            self._write_file(f"{config_path}/MaxPower", "250")

            # Create HID function
            func_path = f"{self.gadget_path}/functions/hid.usb0"
            os.makedirs(func_path, exist_ok=True)
            self._write_file(f"{func_path}/protocol", "1")  # Keyboard
            self._write_file(f"{func_path}/subclass", "1")  # Boot interface subclass
            self._write_file(f"{func_path}/report_length", "8")

            # Write HID report descriptor
            with open(f"{func_path}/report_desc", "wb") as f:
                f.write(self.HID_REPORT_DESCRIPTOR)

            # Link function to configuration
            func_link = f"{config_path}/hid.usb0"
            if not os.path.exists(func_link):
                os.symlink(func_path, func_link)

            # Find UDC (USB Device Controller)
            udc_list = os.listdir("/sys/class/udc")
            if not udc_list:
                self.logger.error("No UDC found")
                return False

            udc = udc_list[0]

            # Enable gadget
            self._write_file(f"{self.gadget_path}/UDC", udc)

            # Wait for device to appear
            time.sleep(1)

            # Find HID device
            self.hid_dev = self._find_hid_device()

            if self.hid_dev:
                self.logger.info(f"USB Gadget HID keyboard enabled: {self.hid_dev}")
                self.enabled = True
                return True
            else:
                self.logger.error("HID device not found")
                return False

        except Exception as e:
            self.logger.error(f"Failed to setup USB Gadget: {e}")
            return False

    def _write_file(self, path: str, content: str):
        """Write content to file"""
        with open(path, 'w') as f:
            f.write(content)

    def _find_hid_device(self) -> Optional[str]:
        """Find HID device path"""
        hidg_devices = [f"/dev/hidg{i}" for i in range(10)]

        for dev in hidg_devices:
            if os.path.exists(dev):
                return dev

        return None

    def send_key(self, key: str, modifiers: List[str] = None) -> bool:
        """
        Send single keystroke.

        Args:
            key: Key to send (character or keycode name)
            modifiers: List of modifiers (CTRL, SHIFT, ALT, GUI)

        Returns:
            bool: True if successful
        """
        if not self.enabled or not self.hid_dev:
            return False

        # Calculate modifier byte
        modifier_byte = 0
        if modifiers:
            for mod in modifiers:
                if mod in self.MODIFIERS:
                    modifier_byte |= self.MODIFIERS[mod]

        # Get keycode
        if len(key) == 1 and key.islower():
            keycode = self.KEYCODES.get(key, 0)
        elif len(key) == 1 and key.isupper():
            keycode = self.KEYCODES.get(key.lower(), 0)
            modifier_byte |= self.MODIFIERS['SHIFT']
        else:
            keycode = self.KEYCODES.get(key, 0)

        # HID report: [modifier, reserved, key1, key2, key3, key4, key5, key6]
        report = bytes([modifier_byte, 0, keycode, 0, 0, 0, 0, 0])

        try:
            # Send key press
            with open(self.hid_dev, 'wb') as hid:
                hid.write(report)

            # Small delay
            time.sleep(0.01)

            # Send key release (all zeros)
            release_report = bytes([0, 0, 0, 0, 0, 0, 0, 0])
            with open(self.hid_dev, 'wb') as hid:
                hid.write(release_report)

            return True

        except Exception as e:
            self.logger.error(f"Failed to send key: {e}")
            return False

    def type_string(self, text: str, delay: float = 0.05) -> bool:
        """
        Type a string of text.

        Args:
            text: Text to type
            delay: Delay between keystrokes (seconds)

        Returns:
            bool: True if successful
        """
        for char in text:
            if char == '\n':
                self.send_key('ENTER')
            else:
                self.send_key(char)

            time.sleep(delay)

        return True

    def cleanup(self) -> bool:
        """
        Cleanup USB Gadget.

        Returns:
            bool: True if successful
        """
        try:
            if os.path.exists(self.gadget_path):
                # Disable gadget
                udc_file = f"{self.gadget_path}/UDC"
                if os.path.exists(udc_file):
                    self._write_file(udc_file, "")

                # Remove symlinks
                config_path = f"{self.gadget_path}/configs/c.1"
                func_link = f"{config_path}/hid.usb0"
                if os.path.exists(func_link):
                    os.unlink(func_link)

                # Remove directories (in reverse order)
                import shutil
                if os.path.exists(self.gadget_path):
                    shutil.rmtree(self.gadget_path)

            self.enabled = False
            self.logger.info("USB Gadget cleaned up")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cleanup USB Gadget: {e}")
            return False
