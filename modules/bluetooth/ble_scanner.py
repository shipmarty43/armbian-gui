"""
BLE Scanner - сканер Bluetooth Low Energy устройств
"""

import subprocess
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime


class BLEScanner:
    """Scanner for Bluetooth Low Energy devices"""

    def __init__(self, adapter: str = "hci0"):
        """
        Initialize BLE scanner.

        Args:
            adapter: Bluetooth adapter (e.g., hci0)
        """
        self.logger = logging.getLogger("cyberdeck.ble")
        self.adapter = adapter
        self.devices = {}
        self.scanning = False

    def start_scan(self, duration: int = 10, scan_type: str = "passive") -> Dict:
        """
        Start BLE scan.

        Args:
            duration: Scan duration in seconds
            scan_type: "passive" or "active"

        Returns:
            Dict of discovered devices
        """
        self.logger.info(f"Starting BLE scan on {self.adapter} for {duration}s")

        try:
            # Enable adapter
            subprocess.run(["hciconfig", self.adapter, "up"],
                          check=True,
                          timeout=5)

            # Start lescan
            scan_cmd = ["timeout", str(duration), "hcitool", "-i", self.adapter, "lescan"]

            if scan_type == "passive":
                scan_cmd.append("--passive")

            process = subprocess.Popen(
                scan_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Parse output
            for line in process.stdout:
                self._parse_scan_line(line)

            process.wait()

            # Get device info for discovered devices
            for mac in list(self.devices.keys()):
                info = self._get_device_info(mac)
                if info:
                    self.devices[mac].update(info)

            self.logger.info(f"Scan complete: {len(self.devices)} devices found")
            return self.devices

        except Exception as e:
            self.logger.error(f"BLE scan failed: {e}")
            return {}

    def _parse_scan_line(self, line: str):
        """Parse lescan output line"""
        # Format: "MAC_ADDRESS Device_Name"
        match = re.search(r'([0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2})\s*(.*)', line, re.IGNORECASE)

        if match:
            mac = match.group(1).upper()
            name = match.group(2).strip() if match.group(2) else "(unknown)"

            if mac not in self.devices:
                self.devices[mac] = {
                    'mac': mac,
                    'name': name,
                    'first_seen': datetime.now().isoformat(),
                    'rssi': None,
                    'type': 'BLE',
                    'services': []
                }

    def _get_device_info(self, mac: str) -> Optional[Dict]:
        """Get detailed device information"""
        try:
            # Get RSSI
            result = subprocess.run(
                ["hcitool", "-i", self.adapter, "rssi", mac],
                capture_output=True,
                text=True,
                timeout=2
            )

            info = {}

            # Parse RSSI
            rssi_match = re.search(r'RSSI return value:\s*(-?\d+)', result.stdout)
            if rssi_match:
                info['rssi'] = int(rssi_match.group(1))

            return info

        except Exception as e:
            self.logger.debug(f"Failed to get info for {mac}: {e}")
            return None

    def scan_classic(self, duration: int = 10) -> Dict:
        """
        Scan for classic Bluetooth devices.

        Args:
            duration: Scan duration in seconds

        Returns:
            Dict of discovered devices
        """
        self.logger.info(f"Starting Classic Bluetooth scan for {duration}s")

        try:
            # Enable adapter
            subprocess.run(["hciconfig", self.adapter, "up"],
                          check=True,
                          timeout=5)

            # Start scan
            result = subprocess.run(
                ["timeout", str(duration), "hcitool", "-i", self.adapter, "scan"],
                capture_output=True,
                text=True,
                timeout=duration + 5
            )

            # Parse output
            devices = {}

            for line in result.stdout.split('\n'):
                # Format: "MAC_ADDRESS    Device_Name"
                match = re.search(r'([0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2})\s+(.*)', line, re.IGNORECASE)

                if match:
                    mac = match.group(1).upper()
                    name = match.group(2).strip()

                    devices[mac] = {
                        'mac': mac,
                        'name': name,
                        'type': 'Classic',
                        'first_seen': datetime.now().isoformat()
                    }

            self.logger.info(f"Classic scan complete: {len(devices)} devices found")
            return devices

        except Exception as e:
            self.logger.error(f"Classic scan failed: {e}")
            return {}

    def get_device_class(self, mac: str) -> Optional[str]:
        """Get device class (type)"""
        try:
            result = subprocess.run(
                ["hcitool", "-i", self.adapter, "info", mac],
                capture_output=True,
                text=True,
                timeout=5
            )

            # Parse device class
            class_match = re.search(r'Class:\s*0x([0-9a-f]+)', result.stdout, re.IGNORECASE)
            if class_match:
                class_code = class_match.group(1)
                return self._decode_device_class(class_code)

            return None

        except Exception as e:
            self.logger.debug(f"Failed to get class for {mac}: {e}")
            return None

    def _decode_device_class(self, class_code: str) -> str:
        """Decode Bluetooth device class"""
        # Simplified device class decoding
        major_device_class = {
            '01': 'Computer',
            '02': 'Phone',
            '03': 'LAN/Network',
            '04': 'Audio/Video',
            '05': 'Peripheral',
            '06': 'Imaging',
            '07': 'Wearable',
            '08': 'Toy',
            '09': 'Health'
        }

        # Get major class (bits 12-8)
        try:
            code_int = int(class_code, 16)
            major = (code_int >> 8) & 0x1F
            major_hex = f'{major:02x}'

            return major_device_class.get(major_hex, f'Unknown (0x{class_code})')

        except:
            return f'Unknown (0x{class_code})'

    def enumerate_services(self, mac: str) -> List[str]:
        """Enumerate Bluetooth services"""
        try:
            result = subprocess.run(
                ["sdptool", "browse", mac],
                capture_output=True,
                text=True,
                timeout=10
            )

            services = []

            # Parse service records
            for line in result.stdout.split('\n'):
                if 'Service Name:' in line:
                    service_name = line.split('Service Name:')[1].strip()
                    services.append(service_name)

            return services

        except Exception as e:
            self.logger.debug(f"Failed to enumerate services for {mac}: {e}")
            return []

    def get_statistics(self) -> Dict:
        """Get scan statistics"""
        total = len(self.devices)

        ble_count = sum(1 for d in self.devices.values() if d.get('type') == 'BLE')
        classic_count = sum(1 for d in self.devices.values() if d.get('type') == 'Classic')

        return {
            'total': total,
            'ble': ble_count,
            'classic': classic_count
        }
