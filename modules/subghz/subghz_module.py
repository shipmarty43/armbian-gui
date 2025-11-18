"""
Sub-GHz Module - захват и воспроизведение сигналов 433MHz через CC1101
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional
import time
import json
import os

try:
    from .cc1101_driver import CC1101
    CC1101_AVAILABLE = True
except ImportError:
    CC1101_AVAILABLE = False


class SubGHzModule(BaseModule):
    """
    Модуль работы с Sub-GHz сигналами (CC1101).

    Функции:
    - Захват RAW сигналов 300-928 MHz
    - Replay атаки
    - Анализ модуляций (ASK/OOK, FSK, etc.)
    - Декодирование протоколов (Princeton, Came, Nice, etc.)
    """

    def __init__(self):
        super().__init__(
            name="Sub-GHz Analyzer",
            version="2.0.0",
            priority=1  # Highest priority
        )

        self.cc1101: Optional[CC1101] = None
        self.hardware_enabled = False
        self.current_frequency = 433.92  # MHz
        self.current_modulation = "ASK_OOK"
        self.is_recording = False
        self.saved_signals = []
        self.signals_dir = "saved_signals"

        # Hardware configuration (from config)
        self.spi_bus = 1
        self.spi_device = 1
        self.cs_pin = 20
        self.gdo0_pin = 25

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("Sub-GHz module loaded")

        # Create signals directory
        os.makedirs(self.signals_dir, exist_ok=True)

        # Load saved signals
        self.load_saved_signals()

        # Initialize CC1101 hardware
        if CC1101_AVAILABLE:
            try:
                # Get config from module
                config = self.get_config().get('hardware', {}).get('subghz', {})
                if config.get('enabled', False):
                    self.spi_bus = config.get('spi_bus', 1)
                    self.spi_device = config.get('spi_device', 1)
                    self.cs_pin = config.get('cs_pin', 20)
                    self.gdo0_pin = config.get('gdo0_pin', 25)

                    self.cc1101 = CC1101(
                        spi_bus=self.spi_bus,
                        spi_device=self.spi_device,
                        cs_pin=self.cs_pin,
                        gdo0_pin=self.gdo0_pin
                    )

                    if self.cc1101.initialize():
                        self.hardware_enabled = True
                        self.log_info("CC1101 hardware initialized successfully")
                    else:
                        self.log_warning("CC1101 initialization failed - running in demo mode")
                else:
                    self.log_info("CC1101 disabled in config - running in demo mode")
            except Exception as e:
                self.log_error(f"Failed to initialize CC1101: {e}")
                self.hardware_enabled = False
        else:
            self.log_warning("CC1101 driver not available - running in demo mode")

    def on_unload(self):
        """Освобождение ресурсов"""
        self.log_info("Sub-GHz module unloaded")

        if self.cc1101 and self.hardware_enabled:
            try:
                self.cc1101.close()
                self.log_info("CC1101 closed")
            except Exception as e:
                self.log_error(f"Error closing CC1101: {e}")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        return [
            ("Read RAW Signal", self.read_signal),
            ("Replay Signal", self.replay_signal),
            ("Frequency Analyzer", self.frequency_analyzer),
            ("Protocol Decoder", self.protocol_decoder),
            ("Signal Generator", self.signal_generator),
            ("Saved Signals", self.view_saved_signals),
            ("Settings", self.show_settings),
            ("Hardware Status", self.show_hardware_status),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        hw_status = "HW" if self.hardware_enabled else "DEMO"
        if self.is_recording:
            return f"SubGHz[{hw_status}]: REC {self.current_frequency}MHz"
        return f"SubGHz[{hw_status}]: {self.current_frequency}MHz"

    def get_hotkeys(self):
        """Горячие клавиши"""
        return {
            'r': self.read_signal,
            'p': self.replay_signal,
            's': self.stop_recording,
            'a': self.frequency_analyzer,
        }

    # ========== Функции модуля ==========

    def read_signal(self):
        """Захват RAW сигнала"""
        self.log_info("Starting signal capture")

        # Запрос параметров
        freq = self.get_user_input(
            "Frequency (MHz):",
            default=str(self.current_frequency)
        )

        try:
            freq = float(freq)
            if not self.is_valid_frequency(freq):
                self.show_error(
                    f"Invalid frequency: {freq}MHz\n"
                    "Valid range: 300-928 MHz"
                )
                return
        except ValueError:
            self.show_error("Invalid frequency format")
            return

        duration = self.get_user_input("Duration (seconds):", default="5")

        try:
            duration = int(duration)
        except ValueError:
            self.show_error("Invalid duration format")
            return

        # Capture signal
        if self.hardware_enabled and self.cc1101:
            self.capture_real_signal(freq, duration)
        else:
            self.capture_demo_signal(freq, duration)

    def capture_real_signal(self, freq: float, duration: int):
        """Захват реального сигнала через CC1101"""
        try:
            # Set frequency
            self.cc1101.set_frequency(freq)
            self.current_frequency = freq

            # Enter RX mode
            self.cc1101.enter_rx_mode()
            self.is_recording = True

            # Capture data
            captured_data = []
            start_time = time.time()

            self.show_message(
                "Capturing",
                f"Capturing signal at {freq}MHz...\n"
                f"Duration: {duration}s\n"
                f"Press 's' to stop early"
            )

            while (time.time() - start_time) < duration and self.is_recording:
                # Read RSSI
                rssi = self.cc1101.read_rssi()
                lqi = self.cc1101.read_lqi()

                # Try to receive data
                data = self.cc1101.receive(timeout=0.1)
                if data:
                    captured_data.append({
                        'timestamp': time.time() - start_time,
                        'data': data,
                        'rssi': rssi,
                        'lqi': lqi
                    })

                time.sleep(0.05)

            self.is_recording = False
            self.cc1101.enter_idle()

            # Save signal
            signal_info = {
                'frequency': freq,
                'duration': duration,
                'modulation': self.current_modulation,
                'data_points': len(captured_data),
                'filename': f'capture_{freq}MHz_{int(time.time())}.json',
                'captured_data': captured_data
            }

            self.save_signal(signal_info)

            self.show_message(
                "Capture Complete",
                f"Signal captured successfully!\n\n"
                f"Frequency: {freq}MHz\n"
                f"Duration: {duration}s\n"
                f"Data points: {len(captured_data)}\n"
                f"File: {signal_info['filename']}"
            )

        except Exception as e:
            self.log_error(f"Capture error: {e}")
            self.show_error(f"Capture failed: {e}")
            self.is_recording = False

    def capture_demo_signal(self, freq: float, duration: int):
        """Демо-захват сигнала"""
        self.show_message(
            "Capture (DEMO)",
            f"Capturing signal at {freq}MHz for {duration}s...\n\n"
            "(Running in DEMO mode - no real hardware)\n"
            "(Connect CC1101 and enable in config for real capture)"
        )

        self.log_info(f"Demo capture: {freq}MHz, {duration}s")

        # Сохраняем демо-данные
        signal_data = {
            'frequency': freq,
            'duration': duration,
            'modulation': 'ASK/OOK',
            'filename': f'demo_capture_{freq}MHz.json',
            'data_points': 0,
            'captured_data': []
        }
        self.saved_signals.append(signal_data)

    def replay_signal(self):
        """Воспроизведение сигнала"""
        if not self.saved_signals:
            self.show_message(
                "Replay",
                "No saved signals. Capture a signal first."
            )
            return

        # Показываем список сигналов
        signal_names = [
            f"{s['filename']} ({s['frequency']}MHz, {s['data_points']} pts)"
            for s in self.saved_signals
        ]

        idx = self.show_menu("Select Signal to Replay", signal_names)

        if idx >= 0 and idx < len(self.saved_signals):
            signal = self.saved_signals[idx]

            if self.hardware_enabled and self.cc1101:
                self.replay_real_signal(signal)
            else:
                self.replay_demo_signal(signal)

    def replay_real_signal(self, signal: dict):
        """Воспроизведение реального сигнала"""
        try:
            # Set frequency
            self.cc1101.set_frequency(signal['frequency'])

            # Get captured data
            captured_data = signal.get('captured_data', [])

            if not captured_data:
                self.show_error("No data to replay")
                return

            self.show_message(
                "Replaying",
                f"Replaying signal...\n"
                f"Frequency: {signal['frequency']}MHz\n"
                f"Data points: {len(captured_data)}"
            )

            # Replay each data point
            for point in captured_data:
                data = point.get('data', [])
                if data:
                    self.cc1101.transmit(data)
                    time.sleep(point.get('timestamp', 0.01))

            self.show_message(
                "Replay Complete",
                f"Signal replayed successfully!\n"
                f"Transmitted {len(captured_data)} data points"
            )

        except Exception as e:
            self.log_error(f"Replay error: {e}")
            self.show_error(f"Replay failed: {e}")

    def replay_demo_signal(self, signal: dict):
        """Демо-воспроизведение"""
        self.show_message(
            "Replay (DEMO)",
            f"Replaying signal:\n"
            f"Frequency: {signal['frequency']}MHz\n"
            f"Modulation: {signal['modulation']}\n\n"
            "(Running in DEMO mode)"
        )

        self.log_info(f"Demo replay: {signal['filename']}")

    def frequency_analyzer(self):
        """Анализ частотного спектра"""
        if self.hardware_enabled and self.cc1101:
            self.real_frequency_analyzer()
        else:
            self.demo_frequency_analyzer()

    def real_frequency_analyzer(self):
        """Реальный анализатор частот"""
        try:
            self.cc1101.enter_rx_mode()

            # Scan frequencies
            scan_results = []
            base_freq = self.current_frequency - 1.0  # Scan ±1 MHz

            for offset in range(-10, 11):
                freq = base_freq + (offset * 0.1)
                self.cc1101.set_frequency(freq)
                time.sleep(0.01)

                rssi = self.cc1101.read_rssi()
                lqi = self.cc1101.read_lqi()

                scan_results.append({
                    'freq': freq,
                    'rssi': rssi,
                    'lqi': lqi
                })

            self.cc1101.enter_idle()

            # Find peak
            peak = max(scan_results, key=lambda x: x['rssi'])

            result_text = "Frequency Analyzer\n\n"
            result_text += f"Center: {self.current_frequency}MHz\n"
            result_text += f"Peak: {peak['freq']:.2f}MHz\n"
            result_text += f"RSSI: {peak['rssi']}dBm\n"
            result_text += f"LQI: {peak['lqi']}\n\n"

            result_text += "Spectrum (±1MHz):\n"
            for scan in scan_results:
                bars = '█' * max(0, int((scan['rssi'] + 100) / 5))
                result_text += f"{scan['freq']:.2f}: {bars} {scan['rssi']}dBm\n"

            self.show_message("Frequency Analyzer", result_text)

        except Exception as e:
            self.log_error(f"Analyzer error: {e}")
            self.show_error(f"Analyzer failed: {e}")

    def demo_frequency_analyzer(self):
        """Демо-анализатор"""
        self.show_message(
            "Frequency Analyzer (DEMO)",
            f"Frequency Analyzer\n\n"
            f"Current frequency: {self.current_frequency} MHz\n"
            f"RSSI: -85 dBm\n"
            f"Bandwidth: 200 kHz\n\n"
            "[This is a demo view]\n\n"
            "ASCII Waterfall would be displayed here\n"
            "in real implementation."
        )

    def protocol_decoder(self):
        """Декодер протоколов"""
        self.show_message(
            "Protocol Decoder",
            "Supported Protocols:\n\n"
            "- Princeton (PT-2262/2272)\n"
            "- Came (12-bit)\n"
            "- Nice (Flo12/Flo24)\n"
            "- Gate-TX\n"
            "- KeeLoq\n"
            "- Holtek HT12E\n\n"
            "Auto-detection: Enabled\n"
            "(Protocol decoding coming soon)"
        )

    def signal_generator(self):
        """Генератор сигналов"""
        if not self.hardware_enabled:
            self.show_message(
                "Signal Generator",
                "Signal Generator requires real hardware.\n\n"
                "Enable CC1101 in config and restart."
            )
            return

        freq = self.get_user_input(
            "Frequency (MHz):",
            default=str(self.current_frequency)
        )

        try:
            freq = float(freq)
            if not self.is_valid_frequency(freq):
                self.show_error("Invalid frequency")
                return
        except ValueError:
            self.show_error("Invalid frequency format")
            return

        # Generate test pattern
        test_data = [0x55, 0xAA, 0x55, 0xAA]  # Alternating pattern

        try:
            self.cc1101.set_frequency(freq)
            self.cc1101.transmit(test_data)

            self.show_message(
                "Signal Generator",
                f"Test signal transmitted!\n\n"
                f"Frequency: {freq}MHz\n"
                f"Pattern: 0x55AA55AA"
            )
        except Exception as e:
            self.show_error(f"Transmission failed: {e}")

    def view_saved_signals(self):
        """Просмотр сохранённых сигналов"""
        if not self.saved_signals:
            self.show_message(
                "Saved Signals",
                "No saved signals yet.\n\n"
                "Capture a signal using 'Read RAW Signal' option."
            )
            return

        signal_list = "Saved Signals:\n\n"
        for idx, signal in enumerate(self.saved_signals, 1):
            signal_list += (
                f"{idx}. {signal['filename']}\n"
                f"   Freq: {signal['frequency']}MHz, "
                f"Points: {signal.get('data_points', 0)}\n\n"
            )

        self.show_message("Saved Signals", signal_list)

    def show_settings(self):
        """Настройки модуля"""
        modulations = ["ASK_OOK", "2FSK", "GFSK", "MSK"]
        idx = self.show_menu("Select Modulation", modulations)

        if idx >= 0 and idx < len(modulations):
            self.current_modulation = modulations[idx]

            if self.hardware_enabled and self.cc1101:
                try:
                    self.cc1101.set_modulation(self.current_modulation)
                    self.show_message(
                        "Settings",
                        f"Modulation changed to {self.current_modulation}"
                    )
                except Exception as e:
                    self.show_error(f"Failed to set modulation: {e}")
            else:
                self.show_message(
                    "Settings",
                    f"Modulation set to {self.current_modulation}\n"
                    "(Demo mode - will apply when hardware enabled)"
                )

    def show_hardware_status(self):
        """Показать статус железа"""
        if self.hardware_enabled and self.cc1101:
            try:
                rssi = self.cc1101.read_rssi()
                lqi = self.cc1101.read_lqi()

                status = (
                    "CC1101 Hardware Status\n\n"
                    f"Status: ENABLED\n"
                    f"SPI: /dev/spidev{self.spi_bus}.{self.spi_device}\n"
                    f"CS Pin: GPIO{self.cs_pin}\n"
                    f"GDO0 Pin: GPIO{self.gdo0_pin}\n\n"
                    f"Current Frequency: {self.current_frequency}MHz\n"
                    f"Modulation: {self.current_modulation}\n\n"
                    f"RSSI: {rssi}dBm\n"
                    f"LQI: {lqi}\n"
                )
            except Exception as e:
                status = f"Hardware error: {e}"
        else:
            status = (
                "CC1101 Hardware Status\n\n"
                "Status: DISABLED (Demo Mode)\n\n"
                "To enable:\n"
                "1. Connect CC1101 to SPI\n"
                "2. Set enabled=true in config/main.yaml\n"
                "3. Run as root for GPIO/SPI access\n"
            )

        self.show_message("Hardware Status", status)

    def stop_recording(self):
        """Остановка записи"""
        if self.is_recording:
            self.is_recording = False
            self.log_info("Recording stopped")
            self.show_message("Stop", "Recording stopped")
        else:
            self.show_message("Stop", "Not currently recording")

    # ========== Helper methods ==========

    def is_valid_frequency(self, freq: float) -> bool:
        """
        Проверка валидности частоты.

        Args:
            freq: Частота в MHz

        Returns:
            bool: True если валидна
        """
        return 300 <= freq <= 928

    def save_signal(self, signal_info: dict):
        """Сохранить сигнал в файл"""
        try:
            filepath = os.path.join(self.signals_dir, signal_info['filename'])

            with open(filepath, 'w') as f:
                json.dump(signal_info, f, indent=2)

            self.saved_signals.append(signal_info)
            self.log_info(f"Signal saved: {signal_info['filename']}")

        except Exception as e:
            self.log_error(f"Failed to save signal: {e}")

    def load_saved_signals(self):
        """Загрузить сохранённые сигналы"""
        try:
            if not os.path.exists(self.signals_dir):
                return

            for filename in os.listdir(self.signals_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.signals_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            signal_info = json.load(f)
                            self.saved_signals.append(signal_info)
                    except Exception as e:
                        self.log_warning(f"Failed to load {filename}: {e}")

            if self.saved_signals:
                self.log_info(f"Loaded {len(self.saved_signals)} saved signals")

        except Exception as e:
            self.log_error(f"Failed to load saved signals: {e}")
