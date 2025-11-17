"""
Bluetooth Module - BLE/Classic сканирование и анализ
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable
import os
import json
from datetime import datetime


class BluetoothModule(BaseModule):
    """
    Bluetooth модуль для сканирования и анализа устройств.

    Функции:
    - BLE (Bluetooth Low Energy) сканирование
    - Classic Bluetooth сканирование
    - Определение типов устройств
    - RSSI измерение
    - Service enumeration
    - Экспорт данных
    """

    def __init__(self):
        super().__init__(
            name="Bluetooth Scanner",
            version="1.0.0",
            priority=5
        )

        self.scanner = None
        self.adapter = "hci0"
        self.devices = {}
        self.scan_history = []
        self.scans_dir = "bluetooth_scans"

        os.makedirs(self.scans_dir, exist_ok=True)

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("Bluetooth module loading...")

        # Load configuration
        config = self.load_config("config/main.yaml")
        bt_config = config.get('bluetooth', {})

        if not bt_config.get('enabled', False):
            self.log_info("Bluetooth disabled in config")
            self.enabled = False
            return

        self.adapter = bt_config.get('adapter', 'hci0')

        # Check if Bluetooth is available
        import subprocess
        try:
            result = subprocess.run(
                ["hciconfig", self.adapter],
                capture_output=True,
                timeout=5
            )

            if result.returncode != 0:
                self.log_warning(f"Bluetooth adapter {self.adapter} not found")
                self.enabled = False
                return

        except Exception as e:
            self.log_error(f"Failed to check Bluetooth: {e}")
            self.enabled = False
            return

        # Initialize scanner
        try:
            from .ble_scanner import BLEScanner
            self.scanner = BLEScanner(adapter=self.adapter)

            self.log_info(f"Bluetooth module loaded on {self.adapter}")
            self.enabled = True

        except Exception as e:
            self.log_error(f"Failed to initialize Bluetooth: {e}")
            self.enabled = False

    def on_unload(self):
        """Освобождение ресурсов"""
        self.log_info("Bluetooth module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.enabled:
            return [
                ("Status: Bluetooth Not Available", lambda: None),
            ]

        return [
            ("BLE Scan", self.ble_scan),
            ("Classic Scan", self.classic_scan),
            ("Combined Scan", self.combined_scan),
            ("Device Details", self.device_details),
            ("Scan History", self.scan_history_menu),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.enabled:
            return "BT: Disabled"

        return f"BT: {len(self.devices)} devices"

    # ========== BLE Scan ==========

    def ble_scan(self):
        """BLE сканирование"""
        duration_input = self.get_user_input("Scan duration (seconds):", default="10")

        try:
            duration = int(duration_input)
        except ValueError:
            self.show_error("Invalid duration")
            return

        # Scan type
        scan_type_choice = self.show_menu(
            "Scan Type",
            [
                "Passive (stealthy)",
                "Active (more info)",
                "Cancel"
            ]
        )

        if scan_type_choice == 2:
            return

        scan_type = "passive" if scan_type_choice == 0 else "active"

        self.show_message(
            "Scanning",
            f"BLE scan in progress...\n\n"
            f"Duration: {duration}s\n"
            f"Type: {scan_type}\n\n"
            "Please wait..."
        )

        # Perform scan
        devices = self.scanner.start_scan(duration, scan_type)

        self.devices.update(devices)

        # Save scan
        self._save_scan("BLE", devices)

        # Show results
        result_text = f"BLE Scan Complete!\n\n"
        result_text += f"Devices found: {len(devices)}\n\n"

        if devices:
            result_text += "Top devices:\n"
            sorted_devices = sorted(
                devices.items(),
                key=lambda x: x[1].get('rssi', -100),
                reverse=True
            )

            for i, (mac, dev) in enumerate(sorted_devices[:5], 1):
                result_text += f"\n{i}. {dev['name']}\n"
                result_text += f"   MAC: {mac}\n"
                if dev.get('rssi'):
                    result_text += f"   RSSI: {dev['rssi']} dBm\n"

        self.show_message("Scan Results", result_text)

    # ========== Classic Scan ==========

    def classic_scan(self):
        """Classic Bluetooth сканирование"""
        duration_input = self.get_user_input("Scan duration (seconds):", default="10")

        try:
            duration = int(duration_input)
        except ValueError:
            self.show_error("Invalid duration")
            return

        self.show_message(
            "Scanning",
            f"Classic Bluetooth scan...\n\n"
            f"Duration: {duration}s\n\n"
            "Searching for devices..."
        )

        # Perform scan
        devices = self.scanner.scan_classic(duration)

        self.devices.update(devices)

        # Save scan
        self._save_scan("Classic", devices)

        # Show results
        result_text = f"Classic Scan Complete!\n\n"
        result_text += f"Devices found: {len(devices)}\n\n"

        if devices:
            for i, (mac, dev) in enumerate(devices.items(), 1):
                result_text += f"{i}. {dev['name']}\n"
                result_text += f"   MAC: {mac}\n\n"

        self.show_message("Scan Results", result_text)

    # ========== Combined Scan ==========

    def combined_scan(self):
        """Combined BLE + Classic scan"""
        self.show_message(
            "Combined Scan",
            "Running combined BLE + Classic scan...\n\n"
            "This will take about 20 seconds."
        )

        # BLE scan
        ble_devices = self.scanner.start_scan(duration=10, scan_type="passive")

        # Classic scan
        classic_devices = self.scanner.scan_classic(duration=10)

        # Merge results
        all_devices = {**ble_devices, **classic_devices}
        self.devices.update(all_devices)

        # Save scan
        self._save_scan("Combined", all_devices)

        # Statistics
        stats = {
            'ble': len(ble_devices),
            'classic': len(classic_devices),
            'total': len(all_devices)
        }

        result_text = f"Combined Scan Complete!\n\n"
        result_text += f"BLE devices: {stats['ble']}\n"
        result_text += f"Classic devices: {stats['classic']}\n"
        result_text += f"Total: {stats['total']}\n"

        self.show_message("Scan Results", result_text)

    # ========== Device Details ==========

    def device_details(self):
        """Show device details"""
        if not self.devices:
            self.show_message(
                "No Devices",
                "No devices found yet.\n\n"
                "Run a scan first."
            )
            return

        # Select device
        device_list = [f"{dev['name']} ({mac})" for mac, dev in self.devices.items()] + ["Back"]

        choice = self.show_menu("Select Device", device_list)

        if choice < len(self.devices):
            mac = list(self.devices.keys())[choice]
            self._show_device_info(mac)

    def _show_device_info(self, mac: str):
        """Show detailed device information"""
        device = self.devices[mac]

        info_text = f"Device Information\n\n"
        info_text += f"Name: {device['name']}\n"
        info_text += f"MAC: {mac}\n"
        info_text += f"Type: {device.get('type', 'Unknown')}\n"

        if device.get('rssi'):
            info_text += f"RSSI: {device['rssi']} dBm\n"

        info_text += f"\nFirst seen: {device.get('first_seen', 'Unknown')}\n"

        # Try to get additional info
        if device.get('type') == 'Classic':
            self.show_message("Getting info", "Enumerating services...")

            device_class = self.scanner.get_device_class(mac)
            if device_class:
                info_text += f"\nDevice class: {device_class}\n"

            services = self.scanner.enumerate_services(mac)
            if services:
                info_text += f"\nServices ({len(services)}):\n"
                for service in services[:5]:  # Show first 5
                    info_text += f"- {service}\n"

        self.show_message("Device Info", info_text)

    # ========== Scan History ==========

    def scan_history_menu(self):
        """Scan history menu"""
        if not self.scan_history:
            self.show_message(
                "Scan History",
                "No scans in history.\n\n"
                "Run a scan first."
            )
            return

        actions = [
            "View All Scans",
            "Export Data",
            "Clear History",
            "Back"
        ]

        choice = self.show_menu("Scan History", actions)

        if choice == 0:
            self._view_scan_history()
        elif choice == 1:
            self._export_scans()
        elif choice == 2:
            self._clear_history()

    def _view_scan_history(self):
        """View scan history"""
        history_text = "Scan History:\n\n"

        for i, scan in enumerate(self.scan_history[-10:], 1):  # Last 10
            history_text += f"{i}. {scan['type']} scan\n"
            history_text += f"   Time: {scan['timestamp']}\n"
            history_text += f"   Devices: {scan['device_count']}\n\n"

        self.show_message("History", history_text)

    def _save_scan(self, scan_type: str, devices: dict):
        """Save scan to history"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        scan_data = {
            'type': scan_type,
            'timestamp': timestamp,
            'device_count': len(devices),
            'devices': devices
        }

        self.scan_history.append(scan_data)

        # Save to file
        filename = f"scan_{scan_type}_{timestamp}.json"
        filepath = os.path.join(self.scans_dir, filename)

        try:
            with open(filepath, 'w') as f:
                json.dump(scan_data, f, indent=2)

            self.log_info(f"Scan saved: {filename}")

        except Exception as e:
            self.log_error(f"Failed to save scan: {e}")

    def _export_scans(self):
        """Export scans"""
        self.show_message(
            "Export",
            f"Scans are automatically saved to:\n\n"
            f"{self.scans_dir}/\n\n"
            f"Format: JSON"
        )

    def _clear_history(self):
        """Clear scan history"""
        confirm = self.show_menu(
            "Clear History",
            [
                "This will clear scan history from memory.",
                "Files will not be deleted.",
                "",
                "Clear",
                "Cancel"
            ]
        )

        if confirm == 3:
            self.scan_history = []
            self.devices = {}
            self.show_message("Cleared", "Scan history cleared from memory.")

    # ========== Settings ==========

    def show_settings(self):
        """Настройки модуля"""
        settings_text = "Bluetooth Module Settings\n\n"

        settings_text += f"Adapter: {self.adapter}\n"
        settings_text += f"Status: {'Enabled' if self.enabled else 'Disabled'}\n\n"

        settings_text += f"Devices in memory: {len(self.devices)}\n"
        settings_text += f"Scan history: {len(self.scan_history)}\n"
        settings_text += f"Scans directory: {self.scans_dir}\n"

        if self.scanner:
            stats = self.scanner.get_statistics()
            settings_text += f"\nCurrent session:\n"
            settings_text += f"BLE devices: {stats.get('ble', 0)}\n"
            settings_text += f"Classic devices: {stats.get('classic', 0)}\n"

        self.show_message("Settings", settings_text)
