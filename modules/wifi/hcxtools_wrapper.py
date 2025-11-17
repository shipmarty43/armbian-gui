"""
HCXTools Wrapper - обёртка для работы с hcxdumptool, hcxpcapngtool и другими утилитами
"""

import subprocess
import os
import time
import logging
from typing import List, Optional, Dict
from datetime import datetime


class HCXToolsWrapper:
    """Обёртка для работы с hcxtools suite"""

    def __init__(self, captures_dir: str = "captures/wifi"):
        """
        Initialize HCXTools wrapper.

        Args:
            captures_dir: Directory for capture files
        """
        self.logger = logging.getLogger("cyberdeck.hcxtools")
        self.captures_dir = captures_dir
        os.makedirs(captures_dir, exist_ok=True)

        # Check if tools are available
        self.hcxdumptool_available = self._check_tool("hcxdumptool")
        self.hcxpcapngtool_available = self._check_tool("hcxpcapngtool")
        self.hcxpsktool_available = self._check_tool("hcxpsktool")

        self.logger.info(f"HCXTools: dumptool={self.hcxdumptool_available}, "
                        f"pcapngtool={self.hcxpcapngtool_available}, "
                        f"psktool={self.hcxpsktool_available}")

    def _check_tool(self, tool_name: str) -> bool:
        """Check if tool is available"""
        try:
            subprocess.run([tool_name, "--version"],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL,
                          timeout=2)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def set_monitor_mode(self, interface: str, channel: Optional[int] = None) -> bool:
        """
        Set interface to monitor mode.

        Args:
            interface: WiFi interface (e.g., wlan0)
            channel: Optional channel to set

        Returns:
            bool: True if successful
        """
        try:
            # Bring interface down
            subprocess.run(["ip", "link", "set", interface, "down"],
                          check=True, timeout=5)

            # Set monitor mode
            subprocess.run(["iw", interface, "set", "monitor", "none"],
                          check=True, timeout=5)

            # Bring interface up
            subprocess.run(["ip", "link", "set", interface, "up"],
                          check=True, timeout=5)

            # Set channel if specified
            if channel:
                subprocess.run(["iw", interface, "set", "channel", str(channel)],
                              check=True, timeout=5)

            self.logger.info(f"Set {interface} to monitor mode" +
                           (f" on channel {channel}" if channel else ""))
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to set monitor mode: {e}")
            return False

    def set_managed_mode(self, interface: str) -> bool:
        """
        Set interface back to managed mode.

        Args:
            interface: WiFi interface

        Returns:
            bool: True if successful
        """
        try:
            subprocess.run(["ip", "link", "set", interface, "down"],
                          check=True, timeout=5)
            subprocess.run(["iw", interface, "set", "type", "managed"],
                          check=True, timeout=5)
            subprocess.run(["ip", "link", "set", interface, "up"],
                          check=True, timeout=5)

            self.logger.info(f"Set {interface} to managed mode")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to set managed mode: {e}")
            return False

    def passive_capture(self, interface: str, duration: int = 60,
                       output_prefix: Optional[str] = None) -> Optional[str]:
        """
        Passive capture with hcxdumptool (no active attacks).

        Args:
            interface: WiFi interface in monitor mode
            duration: Capture duration in seconds
            output_prefix: Output file prefix

        Returns:
            str: Path to capture file or None
        """
        if not self.hcxdumptool_available:
            self.logger.error("hcxdumptool not available")
            return None

        if output_prefix is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_prefix = f"passive_{timestamp}"

        output_file = os.path.join(self.captures_dir, f"{output_prefix}.pcapng")

        try:
            # hcxdumptool -i interface -o output --enable_status=15
            cmd = [
                "hcxdumptool",
                "-i", interface,
                "-o", output_file,
                "--enable_status=15"  # Status every 15 seconds
            ]

            self.logger.info(f"Starting passive capture on {interface} for {duration}s")

            process = subprocess.Popen(cmd,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)

            # Wait for specified duration
            time.sleep(duration)

            # Stop capture
            process.terminate()
            process.wait(timeout=5)

            if os.path.exists(output_file):
                self.logger.info(f"Capture saved: {output_file}")
                return output_file
            else:
                self.logger.error("Capture file not created")
                return None

        except Exception as e:
            self.logger.error(f"Passive capture failed: {e}")
            return None

    def active_capture(self, interface: str, duration: int = 60,
                      target_bssid: Optional[str] = None,
                      output_prefix: Optional[str] = None) -> Optional[str]:
        """
        Active capture with deauthentication attacks.

        Args:
            interface: WiFi interface in monitor mode
            duration: Capture duration in seconds
            target_bssid: Optional target BSSID (if None, attacks all)
            output_prefix: Output file prefix

        Returns:
            str: Path to capture file or None
        """
        if not self.hcxdumptool_available:
            self.logger.error("hcxdumptool not available")
            return None

        if output_prefix is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_prefix = f"active_{timestamp}"

        output_file = os.path.join(self.captures_dir, f"{output_prefix}.pcapng")

        try:
            # hcxdumptool with active attacks
            cmd = [
                "hcxdumptool",
                "-i", interface,
                "-o", output_file,
                "--enable_status=15",
                "--active_beacon",  # Active beacon attacks
                "--enable_deauthentication"  # Enable deauth
            ]

            if target_bssid:
                # Create filter file for specific BSSID
                filter_file = os.path.join(self.captures_dir, "filter.txt")
                with open(filter_file, 'w') as f:
                    f.write(target_bssid + "\n")
                cmd.extend(["--filterlist_ap", filter_file])

            self.logger.info(f"Starting active capture on {interface}" +
                           (f" targeting {target_bssid}" if target_bssid else ""))

            process = subprocess.Popen(cmd,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)

            time.sleep(duration)

            process.terminate()
            process.wait(timeout=5)

            if os.path.exists(output_file):
                self.logger.info(f"Active capture saved: {output_file}")
                return output_file
            else:
                return None

        except Exception as e:
            self.logger.error(f"Active capture failed: {e}")
            return None

    def pmkid_attack(self, interface: str, duration: int = 60,
                    output_prefix: Optional[str] = None) -> Optional[str]:
        """
        PMKID attack (captures PMKID without clients).

        Args:
            interface: WiFi interface in monitor mode
            duration: Capture duration in seconds
            output_prefix: Output file prefix

        Returns:
            str: Path to capture file or None
        """
        if not self.hcxdumptool_available:
            self.logger.error("hcxdumptool not available")
            return None

        if output_prefix is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_prefix = f"pmkid_{timestamp}"

        output_file = os.path.join(self.captures_dir, f"{output_prefix}.pcapng")

        try:
            # PMKID attack
            cmd = [
                "hcxdumptool",
                "-i", interface,
                "-o", output_file,
                "--enable_status=15",
                "--active_beacon",  # Required for PMKID
            ]

            self.logger.info(f"Starting PMKID attack on {interface}")

            process = subprocess.Popen(cmd,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)

            time.sleep(duration)

            process.terminate()
            process.wait(timeout=5)

            if os.path.exists(output_file):
                return output_file
            else:
                return None

        except Exception as e:
            self.logger.error(f"PMKID attack failed: {e}")
            return None

    def extract_hashes(self, pcapng_file: str) -> Optional[str]:
        """
        Extract hashes from pcapng file using hcxpcapngtool.

        Args:
            pcapng_file: Path to pcapng file

        Returns:
            str: Path to hash file (22000 format) or None
        """
        if not self.hcxpcapngtool_available:
            self.logger.error("hcxpcapngtool not available")
            return None

        hash_file = pcapng_file.replace(".pcapng", ".22000")

        try:
            # Extract hashes in hashcat 22000 format
            cmd = [
                "hcxpcapngtool",
                "-o", hash_file,
                pcapng_file
            ]

            result = subprocess.run(cmd,
                                   capture_output=True,
                                   text=True,
                                   timeout=30)

            if os.path.exists(hash_file):
                # Get statistics
                with open(hash_file, 'r') as f:
                    hash_count = len(f.readlines())

                self.logger.info(f"Extracted {hash_count} hashes to {hash_file}")
                return hash_file
            else:
                self.logger.warning("No hashes extracted")
                return None

        except Exception as e:
            self.logger.error(f"Hash extraction failed: {e}")
            return None

    def get_capture_info(self, pcapng_file: str) -> Dict:
        """
        Get information about capture file.

        Args:
            pcapng_file: Path to pcapng file

        Returns:
            dict: Capture statistics
        """
        if not self.hcxpcapngtool_available:
            return {}

        try:
            # Get info
            cmd = [
                "hcxpcapngtool",
                "--info",
                pcapng_file
            ]

            result = subprocess.run(cmd,
                                   capture_output=True,
                                   text=True,
                                   timeout=10)

            # Parse output
            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()

            return info

        except Exception as e:
            self.logger.error(f"Failed to get capture info: {e}")
            return {}

    def list_captures(self) -> List[str]:
        """
        List all capture files.

        Returns:
            List of capture file paths
        """
        captures = []

        if not os.path.exists(self.captures_dir):
            return captures

        for filename in os.listdir(self.captures_dir):
            if filename.endswith('.pcapng'):
                filepath = os.path.join(self.captures_dir, filename)
                captures.append(filepath)

        return sorted(captures, key=os.path.getmtime, reverse=True)
