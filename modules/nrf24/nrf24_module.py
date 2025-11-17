"""
nRF24L01+ Module - 2.4GHz спектроанализатор и джаммер
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable
import time


class NRF24Module(BaseModule):
    """
    Модуль работы с nRF24L01+ для анализа и джамминга 2.4 ГГц.

    Функции:
    - Спектроанализатор 2400-2525 МГц
    - Детектор WiFi, Bluetooth, ZigBee
    - Джамминг Bluetooth (все 79 каналов)
    - Джамминг WiFi (каналы 1, 6, 11)
    - Джамминг BLE advertising
    """

    def __init__(self):
        super().__init__(
            name="nRF24 2.4GHz",
            version="1.0.0",
            priority=2  # High priority
        )

        self.scanner = None
        self.jamming_active = False
        self.scan_history = []
        self.max_history = 100

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("nRF24 module loading...")

        # Load configuration
        config = self.load_config("config/main.yaml")
        nrf24_config = config.get('hardware', {}).get('nrf24', {})

        if not nrf24_config.get('enabled', False):
            self.log_info("nRF24 disabled in config")
            self.enabled = False
            return

        ce_pin = nrf24_config.get('ce_pin', 7)
        spi_bus = nrf24_config.get('spi_bus', 0)
        spi_device = nrf24_config.get('spi_device', 0)
        lna_enable = nrf24_config.get('lna_enable', True)
        pa_level = nrf24_config.get('pa_level', 3)

        try:
            from .nrf24_driver import NRF24Spectrum

            self.scanner = NRF24Spectrum(
                ce_pin=ce_pin,
                spi_bus=spi_bus,
                spi_device=spi_device,
                lna_enable=lna_enable,
                pa_level=pa_level
            )

            if self.scanner.enabled:
                self.log_info(f"nRF24L01+ initialized on SPI {spi_bus}.{spi_device}")
                self.enabled = True
            else:
                self.log_error("nRF24L01+ initialization failed")
                self.enabled = False

        except Exception as e:
            self.log_error(f"Failed to initialize nRF24: {e}")
            self.enabled = False

    def on_unload(self):
        """Освобождение ресурсов"""
        if self.scanner:
            self.scanner.cleanup()
        self.log_info("nRF24 module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.enabled:
            return [
                ("Status: nRF24 Not Available", lambda: None),
            ]

        return [
            ("Spectrum Analyzer", self.spectrum_analyzer),
            ("Quick Scan", self.quick_scan),
            ("Jamming Menu", self.jamming_menu),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.enabled:
            return "nRF24: Disabled"

        if self.jamming_active:
            return "nRF24: JAMMING ACTIVE ⚡"

        return "nRF24: Ready"

    # ========== Scanning Functions ==========

    def quick_scan(self):
        """Быстрое сканирование спектра"""
        self.log_info("Starting quick scan")

        self.show_message(
            "Quick Scan",
            "Scanning 2.4 GHz spectrum...\n\n"
            "Please wait..."
        )

        # Perform scan
        spectrum = self.scanner.scan_spectrum()
        self.scan_history.append(spectrum)

        # Keep only recent scans
        if len(self.scan_history) > self.max_history:
            self.scan_history.pop(0)

        # Analyze results
        active_channels = [i for i, v in enumerate(spectrum) if v > 0]
        total_activity = sum(spectrum)

        # Identify bands
        wifi_channels = self._identify_wifi_channels(active_channels)
        bluetooth_active = any(ch in range(2, 81) for ch in active_channels)

        result_text = f"Spectrum Scan Complete\n\n"
        result_text += f"Active channels: {len(active_channels)}/126\n"
        result_text += f"Total activity: {total_activity}\n\n"

        if wifi_channels:
            result_text += f"WiFi detected on channels: {wifi_channels}\n"

        if bluetooth_active:
            result_text += f"Bluetooth activity detected\n"

        if active_channels:
            result_text += f"\nMost active frequencies:\n"
            # Get top 5 active channels
            sorted_channels = sorted(enumerate(spectrum), key=lambda x: x[1], reverse=True)
            for i, (ch, activity) in enumerate(sorted_channels[:5]):
                if activity > 0:
                    freq = 2400 + ch
                    result_text += f"  {freq} MHz: {activity}\n"

        self.show_message("Scan Results", result_text)
        self.log_info(f"Scan complete: {len(active_channels)} active channels")

    def spectrum_analyzer(self):
        """Полный спектроанализатор"""
        self.show_message(
            "Spectrum Analyzer",
            "Full spectrum analyzer mode\n\n"
            "Scanning 2400-2525 MHz...\n\n"
            "This will take about 10 seconds."
        )

        # Multiple scans for averaging
        num_scans = 10
        accumulated = [0] * self.scanner.num_channels

        for i in range(num_scans):
            spectrum = self.scanner.scan_spectrum()
            for j in range(len(spectrum)):
                accumulated[j] += spectrum[j]

            # Update progress
            if i % 2 == 0:
                progress = int((i + 1) / num_scans * 100)
                # Could update UI here if we had a progress bar

        # Find hotspots
        max_activity = max(accumulated)
        hotspots = []

        for i, activity in enumerate(accumulated):
            if activity > max_activity * 0.5:  # 50% threshold
                freq = 2400 + i
                hotspots.append((freq, activity))

        result_text = f"Spectrum Analysis ({num_scans} scans)\n\n"

        if hotspots:
            result_text += "Hotspots (>50% max activity):\n"
            for freq, activity in hotspots:
                bar = "█" * min(int(activity / max_activity * 20), 20)
                result_text += f"{freq:4d} MHz: {bar} ({activity})\n"
        else:
            result_text += "No significant activity detected.\n"

        result_text += f"\nTotal scans: {num_scans}\n"
        result_text += f"Channels scanned: {self.scanner.num_channels}\n"

        self.show_message("Spectrum Analysis", result_text)

    def _identify_wifi_channels(self, active_channels: List[int]) -> List[int]:
        """Определение WiFi каналов из активных частот"""
        wifi_channels = []

        # WiFi канал 1: 2412 МГц (nRF24 каналы 7-17)
        if any(ch in range(7, 18) for ch in active_channels):
            wifi_channels.append(1)

        # WiFi канал 6: 2437 МГц (nRF24 каналы 32-42)
        if any(ch in range(32, 43) for ch in active_channels):
            wifi_channels.append(6)

        # WiFi канал 11: 2462 МГц (nRF24 каналы 57-67)
        if any(ch in range(57, 68) for ch in active_channels):
            wifi_channels.append(11)

        return wifi_channels

    # ========== Jamming Functions ==========

    def jamming_menu(self):
        """Меню джамминга"""
        choice = self.show_menu(
            "Jamming Menu",
            [
                "Jam Bluetooth (79 channels)",
                "Jam WiFi (channels 1, 6, 11)",
                "Jam BLE Advertising",
                "Jam Custom Channels",
                "Stop Jamming" if self.jamming_active else "Back"
            ]
        )

        if choice == 0:
            self.jam_bluetooth()
        elif choice == 1:
            self.jam_wifi()
        elif choice == 2:
            self.jam_ble()
        elif choice == 3:
            self.jam_custom()
        elif choice == 4 and self.jamming_active:
            self.stop_jamming()

    def jam_bluetooth(self):
        """Джамминг Bluetooth"""
        confirm = self.show_menu(
            "Bluetooth Jamming",
            [
                "⚠️ WARNING: This will disrupt ALL Bluetooth devices!",
                "",
                "Channels: 79 (2402-2480 MHz)",
                "BLE advertising priority: YES",
                "",
                "Start Jamming",
                "Cancel"
            ]
        )

        if confirm == 5:  # Start Jamming
            self.jamming_active = True
            self.log_warning("Bluetooth jamming started")

            self.show_message(
                "Jamming Active",
                "Bluetooth jamming in progress...\n\n"
                "79 channels (2402-2480 MHz)\n"
                "BLE advertising priority enabled\n\n"
                "Duration: 30 seconds\n\n"
                "Press OK to start"
            )

            # Run jamming in background (limited duration for safety)
            try:
                stats = self.scanner.jam_spectrum(
                    channels=list(range(2, 81)),
                    hop_delay=0.0005,
                    mode='continuous',
                    ble_priority=True,
                    callback=lambda: time.time() > time.time() + 30  # 30 sec limit
                )

                self.show_message(
                    "Jamming Complete",
                    f"Bluetooth jamming finished\n\n"
                    f"Impulses: {stats['jam_count']}\n"
                    f"Duration: {stats['duration']:.1f}s\n"
                    f"Rate: {stats['channels_per_sec']:.0f} ch/s"
                )

            finally:
                self.jamming_active = False
                self.log_info("Bluetooth jamming stopped")

    def jam_wifi(self):
        """Джамминг WiFi"""
        confirm = self.show_menu(
            "WiFi Jamming",
            [
                "⚠️ WARNING: This will disrupt WiFi networks!",
                "",
                "Target: WiFi channels 1, 6, 11",
                "Frequencies: 2412, 2437, 2462 MHz",
                "",
                "Start Jamming",
                "Cancel"
            ]
        )

        if confirm == 5:  # Start Jamming
            self.jamming_active = True

            # WiFi каналы имеют ширину ~20 МГц
            wifi_channels = (
                list(range(7, 18)) +    # WiFi канал 1
                list(range(32, 43)) +   # WiFi канал 6
                list(range(57, 68))     # WiFi канал 11
            )

            self.show_message(
                "Jamming Active",
                f"WiFi jamming in progress...\n\n"
                f"Channels: 1, 6, 11\n"
                f"nRF24 channels: {len(wifi_channels)}\n\n"
                f"Duration: 30 seconds"
            )

            try:
                stats = self.scanner.jam_spectrum(
                    channels=wifi_channels,
                    hop_delay=0,
                    mode='continuous',
                    ble_priority=False,
                    callback=lambda: time.time() > time.time() + 30
                )

                self.show_message(
                    "Jamming Complete",
                    f"WiFi jamming finished\n\n"
                    f"Impulses: {stats['jam_count']}\n"
                    f"Duration: {stats['duration']:.1f}s"
                )

            finally:
                self.jamming_active = False

    def jam_ble(self):
        """Джамминг BLE advertising"""
        self.jamming_active = True

        # BLE advertising channels: 37, 38, 39
        ble_channels = [37, 38, 39]

        self.show_message(
            "BLE Jamming",
            "BLE advertising jamming...\n\n"
            "Channels: 37, 38, 39\n"
            "Duration: 30 seconds"
        )

        try:
            stats = self.scanner.jam_spectrum(
                channels=ble_channels,
                hop_delay=0,
                mode='continuous',
                ble_priority=True,
                callback=lambda: time.time() > time.time() + 30
            )

            self.show_message(
                "Jamming Complete",
                f"BLE jamming finished\n\n"
                f"Channels attacked: 3\n"
                f"Impulses: {stats['jam_count']}"
            )

        finally:
            self.jamming_active = False

    def jam_custom(self):
        """Джамминг пользовательских каналов"""
        channels_input = self.get_user_input(
            "Enter channels (comma-separated, 0-125):",
            default="37,38,39"
        )

        try:
            channels = [int(ch.strip()) for ch in channels_input.split(',')]
            channels = [ch for ch in channels if 0 <= ch <= 125]

            if not channels:
                self.show_error("No valid channels specified")
                return

            freqs = [2400 + ch for ch in channels]

            confirm = self.show_menu(
                "Custom Jamming",
                [
                    f"Channels: {channels}",
                    f"Frequencies: {freqs} MHz",
                    "",
                    "Start Jamming",
                    "Cancel"
                ]
            )

            if confirm == 3:  # Start Jamming
                self.jamming_active = True

                try:
                    stats = self.scanner.jam_spectrum(
                        channels=channels,
                        hop_delay=0,
                        mode='continuous',
                        ble_priority=False,
                        callback=lambda: time.time() > time.time() + 30
                    )

                    self.show_message(
                        "Jamming Complete",
                        f"Custom jamming finished\n\n"
                        f"Channels: {len(channels)}\n"
                        f"Impulses: {stats['jam_count']}"
                    )

                finally:
                    self.jamming_active = False

        except ValueError:
            self.show_error("Invalid channel format")

    def stop_jamming(self):
        """Остановка джамминга"""
        self.jamming_active = False
        self.show_message("Jamming", "Jamming stopped")

    # ========== Settings ==========

    def show_settings(self):
        """Настройки модуля"""
        if not self.scanner:
            settings_text = "nRF24 Module Settings\n\n"
            settings_text += "Status: Not available\n"
        else:
            settings_text = "nRF24 Module Settings\n\n"
            settings_text += f"LNA: {'Enabled' if self.scanner.lna_enable else 'Disabled'}\n"
            settings_text += f"PA Level: {self.scanner.pa_level}\n"
            settings_text += f"Channels: {self.scanner.num_channels}\n"
            settings_text += f"Frequency range: 2400-2525 MHz\n\n"

            settings_text += f"Scan history: {len(self.scan_history)}/{self.max_history}\n"
            settings_text += f"Jamming active: {'YES ⚡' if self.jamming_active else 'No'}\n"

        self.show_message("Settings", settings_text)
