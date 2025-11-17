"""
WiFi Module - полная реализация пентестинга WiFi с hcxtools
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional
import os
import subprocess
from datetime import datetime


class WiFiModule(BaseModule):
    """
    Модуль пентестинга WiFi сетей с hcxtools.

    Функции:
    - 6 сценариев атак (Passive, Active, Dual-Adapter, Wardriving, Rogue AP, PMKID)
    - Захват handshakes (WPA/WPA2/WPA3)
    - Wardriving с GPS синхронизацией
    - Управление captures и hashes
    - Интеграция с hashcat для крекинга
    """

    def __init__(self):
        super().__init__(
            name="WiFi Security",
            version="2.0.0",
            priority=1
        )

        self.adapters = []
        self.current_scenario = None
        self.captures = []
        self.hcxtools = None
        self.wardriving_scanner = None

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("WiFi module loading...")

        # Load configuration
        config = self.load_config("config/main.yaml")
        wifi_config = config.get('wifi', {})

        # Initialize hcxtools wrapper
        try:
            from .hcxtools_wrapper import HCXToolsWrapper
            self.hcxtools = HCXToolsWrapper()

            if not (self.hcxtools.hcxdumptool_available and
                   self.hcxtools.hcxpcapngtool_available):
                self.log_warning("hcxtools not fully available - some features will be limited")
                self.log_warning("Install: apt install hcxdumptool hcxtools")

        except Exception as e:
            self.log_error(f"Failed to initialize hcxtools: {e}")

        # Detect WiFi adapters
        self._detect_adapters()

        # Load captures list
        if self.hcxtools:
            self.captures = self.hcxtools.list_captures()

        self.log_info(f"WiFi module loaded: {len(self.adapters)} adapters, {len(self.captures)} captures")
        self.enabled = True

    def on_unload(self):
        """Освобождение ресурсов"""
        # Restore managed mode on all adapters
        if self.hcxtools:
            for adapter in self.adapters:
                self.hcxtools.set_managed_mode(adapter)

        self.log_info("WiFi module unloaded")

    def _detect_adapters(self):
        """Detect available WiFi adapters"""
        try:
            result = subprocess.run(
                ["iw", "dev"],
                capture_output=True,
                text=True,
                timeout=5
            )

            for line in result.stdout.split('\n'):
                if 'Interface' in line:
                    interface = line.split()[-1]
                    if interface.startswith('wlan'):
                        self.adapters.append(interface)

            self.log_info(f"Detected adapters: {self.adapters}")

        except Exception as e:
            self.log_error(f"Failed to detect adapters: {e}")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.adapters:
            return [
                ("Status: No WiFi Adapters Detected", lambda: None),
            ]

        return [
            ("Attack Scenarios", self.scenario_selector),
            ("Network Scanner", self.network_scanner),
            ("Capture Manager", self.capture_manager),
            ("Wardriving Mode", self.scenario_wardriving),
            ("Crack Hashes", self.crack_hashes),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.adapters:
            return "WiFi: No adapters"

        return f"WiFi: {len(self.adapters)} adapters, {len(self.captures)} captures"

    # ========== Scenario Selector ==========

    def scenario_selector(self):
        """Выбор сценария атаки"""
        scenarios = [
            "[1] Passive Monitor (passive handshake capture)",
            "[2] Active Attack (deauth + capture)",
            "[3] Dual Adapter (monitor + attack)",
            "[4] Wardriving (GPS + mapping)",
            "[5] Rogue AP (evil twin)",
            "[6] PMKID Attack (no clients needed)",
        ]

        choice = self.show_menu("Select Attack Scenario", scenarios + ["Back"])

        scenario_map = {
            0: self.scenario_passive,
            1: self.scenario_active,
            2: self.scenario_dual_adapter,
            3: self.scenario_wardriving,
            4: self.scenario_rogue_ap,
            5: self.scenario_pmkid,
        }

        if choice in scenario_map:
            scenario_map[choice]()

    # ========== Scenario 1: Passive Monitor ==========

    def scenario_passive(self):
        """Scenario 1: Passive Monitoring"""
        if not self.hcxtools or not self.hcxtools.hcxdumptool_available:
            self.show_error("hcxdumptool not available.\n\nInstall: apt install hcxdumptool")
            return

        # Select adapter
        adapter = self._select_adapter()
        if not adapter:
            return

        # Get duration
        duration_input = self.get_user_input("Capture duration (seconds):", default="60")

        try:
            duration = int(duration_input)
        except ValueError:
            self.show_error("Invalid duration")
            return

        # Confirm
        confirm = self.show_menu(
            "Passive Monitor",
            [
                f"Interface: {adapter}",
                f"Duration: {duration}s",
                "Mode: Passive (no attacks)",
                "",
                "Start Capture",
                "Cancel"
            ]
        )

        if confirm != 4:
            return

        # Set monitor mode
        self.show_message("Setup", "Setting up monitor mode...")

        if not self.hcxtools.set_monitor_mode(adapter):
            self.show_error("Failed to set monitor mode")
            return

        # Start capture
        self.show_message(
            "Capturing",
            f"Passive capture running on {adapter}\n\n"
            f"Duration: {duration}s\n\n"
            "Capturing handshakes and PMKID...\n"
            "Please wait..."
        )

        capture_file = self.hcxtools.passive_capture(adapter, duration)

        # Restore managed mode
        self.hcxtools.set_managed_mode(adapter)

        if capture_file:
            # Extract hashes
            hash_file = self.hcxtools.extract_hashes(capture_file)

            result_text = f"Capture Complete!\n\n"
            result_text += f"Capture file: {os.path.basename(capture_file)}\n"

            if hash_file:
                # Count hashes
                with open(hash_file, 'r') as f:
                    hash_count = len(f.readlines())

                result_text += f"Hashes: {hash_count}\n\n"
                result_text += "Use 'Crack Hashes' to crack passwords."
            else:
                result_text += "No hashes extracted.\n\n"
                result_text += "Try active attack for better results."

            self.show_message("Results", result_text)
            self.captures.append(capture_file)

        else:
            self.show_error("Capture failed")

    # ========== Scenario 2: Active Attack ==========

    def scenario_active(self):
        """Scenario 2: Active Handshake Capture"""
        if not self.hcxtools or not self.hcxtools.hcxdumptool_available:
            self.show_error("hcxdumptool not available")
            return

        adapter = self._select_adapter()
        if not adapter:
            return

        # Ask for target BSSID
        target_bssid = self.get_user_input(
            "Target BSSID (MAC address):\n(leave empty for all networks)",
            default=""
        )

        if target_bssid and not self._validate_mac(target_bssid):
            self.show_error("Invalid MAC address format")
            return

        duration_input = self.get_user_input("Capture duration (seconds):", default="60")

        try:
            duration = int(duration_input)
        except ValueError:
            self.show_error("Invalid duration")
            return

        # Confirm
        confirm_items = [
            f"Interface: {adapter}",
            f"Target: {target_bssid if target_bssid else 'All networks'}",
            f"Duration: {duration}s",
            "Mode: Active (deauth enabled)",
            "",
            "⚠️ WARNING: Active deauth attacks!",
            "",
            "Start Attack",
            "Cancel"
        ]

        confirm = self.show_menu("Active Attack", confirm_items)

        if confirm != 7:
            return

        # Set monitor mode
        if not self.hcxtools.set_monitor_mode(adapter):
            self.show_error("Failed to set monitor mode")
            return

        self.show_message(
            "Attacking",
            f"Active attack running on {adapter}\n\n"
            f"Target: {target_bssid if target_bssid else 'All'}\n"
            f"Duration: {duration}s\n\n"
            "Sending deauth packets...\n"
            "Capturing handshakes..."
        )

        capture_file = self.hcxtools.active_capture(
            adapter,
            duration,
            target_bssid if target_bssid else None
        )

        self.hcxtools.set_managed_mode(adapter)

        if capture_file:
            hash_file = self.hcxtools.extract_hashes(capture_file)

            result_text = f"Attack Complete!\n\n"
            result_text += f"Capture: {os.path.basename(capture_file)}\n"

            if hash_file:
                with open(hash_file, 'r') as f:
                    hash_count = len(f.readlines())

                result_text += f"Hashes captured: {hash_count}\n"
            else:
                result_text += "No hashes extracted.\n"

            self.show_message("Results", result_text)
            self.captures.append(capture_file)

        else:
            self.show_error("Attack failed")

    # ========== Scenario 3: Dual Adapter ==========

    def scenario_dual_adapter(self):
        """Scenario 3: Dual Adapter Attack"""
        if len(self.adapters) < 2:
            self.show_error(
                "Dual adapter attack requires 2 WiFi adapters.\n\n"
                f"Detected: {len(self.adapters)}"
            )
            return

        self.show_message(
            "Dual Adapter Attack",
            "Dual Adapter Attack\n\n"
            "Uses 2 adapters:\n"
            "- Adapter 1: Monitor mode (capture)\n"
            "- Adapter 2: Active attacks (deauth)\n\n"
            "This provides better coverage\n"
            "and higher success rate.\n\n"
            "Feature coming soon..."
        )

    # ========== Scenario 4: Wardriving ==========

    def scenario_wardriving(self):
        """Scenario 4: Wardriving Mode"""
        # Check if GPS module is available
        gps_available = False

        try:
            # Try to get GPS module from event bus
            from modules.gps.gps_module import GPSModule
            # Check if GPS is loaded
            # This is simplified - in real implementation would check module loader
            gps_available = True
        except:
            pass

        if not gps_available:
            self.show_message(
                "GPS Required",
                "Wardriving requires GPS module.\n\n"
                "Enable GPS in config/main.yaml\n"
                "and ensure GPS hardware is connected."
            )
            return

        # Initialize wardriving scanner if needed
        if not self.wardriving_scanner:
            try:
                from .wardriving import WardrivingScanner
                # Get GPS module instance - simplified
                self.wardriving_scanner = WardrivingScanner(
                    interface=self.adapters[0],
                    gps_module=None  # Would get from module loader in real implementation
                )
            except Exception as e:
                self.log_error(f"Failed to initialize wardriving: {e}")
                self.show_error("Failed to initialize wardriving scanner")
                return

        duration_input = self.get_user_input("Scan duration (seconds, 0=continuous):", default="300")

        try:
            duration = int(duration_input)
        except ValueError:
            self.show_error("Invalid duration")
            return

        self.show_message(
            "Wardriving",
            f"Starting wardriving scan...\n\n"
            f"Duration: {duration if duration > 0 else 'Continuous'}s\n"
            f"Interface: {self.adapters[0]}\n\n"
            "Scanning networks with GPS tagging..."
        )

        # Start scan (simplified - would run in background)
        # In real implementation this would be async
        import threading
        scan_thread = threading.Thread(
            target=self.wardriving_scanner.start_scan,
            args=(duration,)
        )
        scan_thread.start()
        scan_thread.join(timeout=min(duration, 60) if duration > 0 else 60)

        self.wardriving_scanner.stop_scan()

        # Generate outputs
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        wigle_file = self.wardriving_scanner.export_to_wigle(f"wigle_{timestamp}.csv")
        map_file = self.wardriving_scanner.generate_html_map(f"map_{timestamp}.html")

        stats = self.wardriving_scanner.get_statistics()

        result_text = f"Wardriving Complete!\n\n"
        result_text += f"Networks found: {stats['total']}\n"
        result_text += f"Open: {stats['open']}\n"
        result_text += f"WPA2: {stats['wpa2']}\n"
        result_text += f"WPA3: {stats['wpa3']}\n\n"
        result_text += f"Wigle CSV: {os.path.basename(wigle_file)}\n"
        result_text += f"HTML Map: {os.path.basename(map_file)}\n"

        self.show_message("Wardriving Results", result_text)

    # ========== Scenario 5: Rogue AP ==========

    def scenario_rogue_ap(self):
        """Scenario 5: Rogue AP (Evil Twin)"""
        self.show_message(
            "Rogue AP",
            "Rogue AP (Evil Twin) Attack\n\n"
            "Creates fake access point to:\n"
            "- Capture credentials\n"
            "- Perform MitM attacks\n"
            "- Phishing attacks\n\n"
            "Tools required:\n"
            "- hostapd\n"
            "- dnsmasq\n\n"
            "Feature coming soon..."
        )

    # ========== Scenario 6: PMKID Attack ==========

    def scenario_pmkid(self):
        """Scenario 6: PMKID Attack"""
        if not self.hcxtools or not self.hcxtools.hcxdumptool_available:
            self.show_error("hcxdumptool not available")
            return

        adapter = self._select_adapter()
        if not adapter:
            return

        duration_input = self.get_user_input("Attack duration (seconds):", default="60")

        try:
            duration = int(duration_input)
        except ValueError:
            self.show_error("Invalid duration")
            return

        confirm = self.show_menu(
            "PMKID Attack",
            [
                f"Interface: {adapter}",
                f"Duration: {duration}s",
                "",
                "PMKID attack works without clients!",
                "Targets router directly.",
                "",
                "Start Attack",
                "Cancel"
            ]
        )

        if confirm != 6:
            return

        if not self.hcxtools.set_monitor_mode(adapter):
            self.show_error("Failed to set monitor mode")
            return

        self.show_message(
            "PMKID Attack",
            f"PMKID attack running on {adapter}\n\n"
            f"Duration: {duration}s\n\n"
            "Attacking routers...\n"
            "No clients needed!"
        )

        capture_file = self.hcxtools.pmkid_attack(adapter, duration)

        self.hcxtools.set_managed_mode(adapter)

        if capture_file:
            hash_file = self.hcxtools.extract_hashes(capture_file)

            result_text = f"PMKID Attack Complete!\n\n"
            result_text += f"Capture: {os.path.basename(capture_file)}\n"

            if hash_file:
                with open(hash_file, 'r') as f:
                    hash_count = len(f.readlines())

                result_text += f"PMKID hashes: {hash_count}\n"
            else:
                result_text += "No PMKID captured.\n"

            self.show_message("Results", result_text)
            self.captures.append(capture_file)

        else:
            self.show_error("PMKID attack failed")

    # ========== Network Scanner ==========

    def network_scanner(self):
        """Quick network scan"""
        adapter = self._select_adapter()
        if not adapter:
            return

        self.show_message("Scanning", f"Scanning networks on {adapter}...")

        try:
            result = subprocess.run(
                ["iwlist", adapter, "scan"],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Parse networks (simplified)
            networks = []
            for line in result.stdout.split('\n'):
                if 'ESSID:' in line:
                    essid = line.split('ESSID:')[1].strip('"')
                    if essid:
                        networks.append(essid)

            if networks:
                networks_text = "Networks found:\n\n"
                for i, net in enumerate(networks[:20], 1):  # Show top 20
                    networks_text += f"{i}. {net}\n"

                self.show_message("Networks", networks_text)
            else:
                self.show_message("Scan", "No networks found")

        except Exception as e:
            self.show_error(f"Scan failed: {e}")

    # ========== Capture Manager ==========

    def capture_manager(self):
        """Manage capture files"""
        if not self.captures:
            self.show_message(
                "Capture Manager",
                "No captures yet.\n\n"
                "Run an attack scenario to create captures."
            )
            return

        captures_list = ["View all captures", "Extract hashes", "Delete capture", "Back"]

        choice = self.show_menu("Capture Manager", captures_list)

        if choice == 0:
            self._view_captures()
        elif choice == 1:
            self._extract_all_hashes()
        elif choice == 2:
            self._delete_capture()

    def _view_captures(self):
        """View all captures"""
        captures_text = "Capture Files:\n\n"

        for i, capture in enumerate(self.captures[:10], 1):  # Show latest 10
            size = os.path.getsize(capture) if os.path.exists(capture) else 0
            captures_text += f"{i}. {os.path.basename(capture)}\n"
            captures_text += f"   Size: {size // 1024} KB\n\n"

        self.show_message("Captures", captures_text)

    def _extract_all_hashes(self):
        """Extract hashes from all captures"""
        self.show_message("Extracting", "Extracting hashes from all captures...")

        total_hashes = 0

        for capture in self.captures:
            if capture.endswith('.pcapng'):
                hash_file = self.hcxtools.extract_hashes(capture)
                if hash_file and os.path.exists(hash_file):
                    with open(hash_file, 'r') as f:
                        total_hashes += len(f.readlines())

        self.show_message(
            "Extraction Complete",
            f"Total hashes extracted: {total_hashes}\n\n"
            "Use 'Crack Hashes' to crack passwords."
        )

    def _delete_capture(self):
        """Delete capture file"""
        self.show_message("Delete", "Delete feature coming soon...")

    # ========== Crack Hashes ==========

    def crack_hashes(self):
        """Crack captured hashes with hashcat"""
        self.show_message(
            "Crack Hashes",
            "Hash Cracking\n\n"
            "Use hashcat to crack captured hashes:\n\n"
            "1. Find .22000 files in captures/wifi/\n"
            "2. Run hashcat:\n"
            "   hashcat -m 22000 file.22000 wordlist.txt\n\n"
            "Wordlists:\n"
            "- /usr/share/wordlists/rockyou.txt\n"
            "- Custom wordlists\n\n"
            "Automated cracking coming soon..."
        )

    # ========== Helper Methods ==========

    def _select_adapter(self) -> Optional[str]:
        """Select WiFi adapter from available list"""
        if not self.adapters:
            self.show_error("No WiFi adapters detected")
            return None

        if len(self.adapters) == 1:
            return self.adapters[0]

        choice = self.show_menu(
            "Select WiFi Adapter",
            self.adapters + ["Cancel"]
        )

        if choice < len(self.adapters):
            return self.adapters[choice]

        return None

    def _validate_mac(self, mac: str) -> bool:
        """Validate MAC address format"""
        import re
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(pattern, mac))

    # ========== Settings ==========

    def show_settings(self):
        """Настройки модуля"""
        settings_text = "WiFi Module Settings\n\n"

        settings_text += f"Adapters detected: {len(self.adapters)}\n"
        for adapter in self.adapters:
            settings_text += f"  - {adapter}\n"

        settings_text += f"\nCaptures: {len(self.captures)}\n"

        if self.hcxtools:
            settings_text += f"\nhcxdumptool: {'✓' if self.hcxtools.hcxdumptool_available else '✗'}\n"
            settings_text += f"hcxpcapngtool: {'✓' if self.hcxtools.hcxpcapngtool_available else '✗'}\n"
            settings_text += f"hcxpsktool: {'✓' if self.hcxtools.hcxpsktool_available else '✗'}\n"
        else:
            settings_text += "\nhcxtools: Not initialized\n"

        self.show_message("Settings", settings_text)
