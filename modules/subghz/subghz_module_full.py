"""
Sub-GHz Module - полная реализация с CC1101
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional
import time
import os
from datetime import datetime

try:
    from .cc1101_driver import CC1101
    from .signal_analyzer import SignalCapture, ProtocolDecoder, SignalGenerator
    CC1101_AVAILABLE = True
except ImportError:
    CC1101_AVAILABLE = False


class SubGHzModuleFull(BaseModule):
    """
    Полнофункциональный модуль работы с Sub-GHz сигналами (CC1101).

    Функции:
    - Захват RAW сигналов 300-928 MHz
    - Replay атаки
    - Анализ и декодирование протоколов
    - Генерация сигналов
    - Совместимость с Flipper Zero
    """

    def __init__(self):
        super().__init__(
            name="Sub-GHz Analyzer",
            version="2.0.0",
            priority=1
        )

        self.cc1101 = None
        self.current_frequency = 433.92
        self.is_recording = False
        self.current_capture = None
        self.saved_signals = []
        self.signals_dir = "captures/subghz"

        # Create signals directory
        os.makedirs(self.signals_dir, exist_ok=True)

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("Sub-GHz module loading...")

        if not CC1101_AVAILABLE:
            self.log_warning("CC1101 driver not available (running in demo mode)")
            self.enabled = False
            return

        # Load configuration
        config = self.load_config("config/main.yaml")
        subghz_config = config.get('hardware', {}).get('subghz', {})

        if not subghz_config.get('enabled', False):
            self.log_info("Sub-GHz disabled in config")
            self.enabled = False
            return

        # Initialize CC1101
        try:
            self.cc1101 = CC1101(
                spi_bus=subghz_config.get('spi_bus', 0),
                spi_device=subghz_config.get('spi_device', 1),
                cs_pin=subghz_config.get('cs_pin', 24),
                gdo0_pin=subghz_config.get('gdo0_pin', 25)
            )

            if self.cc1101.initialize():
                self.log_info("CC1101 initialized successfully")
                self.current_frequency = subghz_config.get('default_freq', 433.92)
                self.cc1101.set_frequency(self.current_frequency)
            else:
                self.log_error("Failed to initialize CC1101")
                self.enabled = False

        except Exception as e:
            self.log_error(f"Failed to load CC1101: {e}")
            self.enabled = False

        # Load saved signals
        self._load_saved_signals()

    def on_unload(self):
        """Освобождение ресурсов"""
        if self.cc1101:
            self.cc1101.close()
        self.log_info("Sub-GHz module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.enabled:
            return [
                ("Status: Hardware Not Available", lambda: None),
                ("About", self.show_about),
            ]

        return [
            ("Read RAW Signal", self.read_signal),
            ("Replay Signal", self.replay_signal),
            ("Frequency Analyzer", self.frequency_analyzer),
            ("Protocol Decoder", self.protocol_decoder),
            ("Signal Generator", self.signal_generator),
            ("Saved Signals", self.view_saved_signals),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.enabled:
            return "SubGHz: Disabled"

        if self.is_recording:
            return f"SubGHz: Recording {self.current_frequency}MHz"

        return f"SubGHz: {self.current_frequency}MHz Ready"

    def get_hotkeys(self):
        """Горячие клавиши"""
        return {
            'r': self.read_signal,
            'p': self.replay_signal,
            's': self.stop_recording,
            'a': self.frequency_analyzer,
        }

    # ========== Основные функции ==========

    def read_signal(self):
        """Захват RAW сигнала"""
        if not self.enabled:
            self.show_error("CC1101 not available")
            return

        self.log_info("Starting signal capture")

        # Запрос параметров
        freq = self.get_user_input(
            "Frequency (MHz):",
            default=str(self.current_frequency)
        )

        try:
            freq = float(freq)
            if not (300 <= freq <= 928):
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
            if not (1 <= duration <= 300):
                self.show_error("Duration must be 1-300 seconds")
                return
        except ValueError:
            self.show_error("Invalid duration format")
            return

        # Set frequency
        self.cc1101.set_frequency(freq)
        self.current_frequency = freq

        # Create capture object
        self.current_capture = SignalCapture(freq)

        # Start capture
        self.is_recording = True
        self.cc1101.enter_rx_mode()

        self.show_message(
            "Capture",
            f"Capturing at {freq}MHz for {duration}s...\n"
            "Press 's' to stop early"
        )

        start_time = time.time()
        sample_count = 0

        try:
            while (time.time() - start_time) < duration and self.is_recording:
                # Receive samples
                data = self.cc1101.receive(timeout=0.1)

                if data:
                    for byte in data:
                        self.current_capture.add_sample(byte)
                        sample_count += 1

                # Read RSSI
                rssi = self.cc1101.read_rssi()
                self.current_capture.rssi.append(rssi)

        except KeyboardInterrupt:
            pass

        finally:
            self.is_recording = False
            self.cc1101.enter_idle()

        # Finalize capture
        self.current_capture.finalize()

        self.log_info(f"Captured {sample_count} samples in {self.current_capture.duration:.2f}s")

        # Analyze
        pulses = self.current_capture.get_pulse_lengths()
        protocol = ProtocolDecoder.detect_protocol(pulses)

        if protocol:
            self.current_capture.protocol = protocol
            self.log_info(f"Detected protocol: {protocol}")

        # Save
        save = self.show_menu(
            "Save Signal?",
            ["Yes", "No"]
        )

        if save == 0:
            self._save_current_signal()

    def replay_signal(self):
        """Воспроизведение сигнала"""
        if not self.enabled:
            self.show_error("CC1101 not available")
            return

        if not self.saved_signals:
            self.show_message(
                "Replay",
                "No saved signals.\n\nCapture a signal first."
            )
            return

        # Show signal list
        signal_names = [
            f"{s['name']} ({s['frequency']}MHz, {s['protocol'] or 'Unknown'})"
            for s in self.saved_signals
        ]

        idx = self.show_menu("Select Signal to Replay", signal_names)

        if idx < 0 or idx >= len(self.saved_signals):
            return

        signal_info = self.saved_signals[idx]

        # Load signal
        capture = SignalCapture.load_from_file(signal_info['filepath'])

        if not capture:
            self.show_error("Failed to load signal")
            return

        # Set frequency
        self.cc1101.set_frequency(capture.frequency)

        # Get transmission count
        count = self.get_user_input("Repeat count (1-100):", default="1")

        try:
            count = int(count)
            count = max(1, min(100, count))
        except ValueError:
            count = 1

        # Transmit
        self.show_message(
            "Transmitting",
            f"Replaying signal {count} time(s)...\n"
            f"Frequency: {capture.frequency}MHz"
        )

        for i in range(count):
            self.log_info(f"Transmission {i+1}/{count}")

            # Convert samples to bytes and transmit
            data = [b & 0xFF for b in capture.samples[:64]]
            self.cc1101.transmit(data)

            time.sleep(0.1)

        self.cc1101.enter_idle()

        self.show_message("Complete", f"Transmitted {count} time(s)")
        self.log_info(f"Replayed signal: {signal_info['name']}")

    def frequency_analyzer(self):
        """Анализ частотного спектра в реальном времени"""
        if not self.enabled:
            self.show_error("CC1101 not available")
            return

        freq = self.get_user_input(
            "Start frequency (MHz):",
            default=str(self.current_frequency)
        )

        try:
            freq = float(freq)
        except ValueError:
            freq = self.current_frequency

        self.cc1101.set_frequency(freq)
        self.cc1101.enter_rx_mode()

        # Scan spectrum
        results = []
        scan_range = 2.0  # MHz

        for offset in range(-10, 11):
            scan_freq = freq + (offset * scan_range / 20)
            self.cc1101.set_frequency(scan_freq)
            time.sleep(0.05)

            rssi = self.cc1101.read_rssi()
            results.append((scan_freq, rssi))

        self.cc1101.enter_idle()

        # Display results
        spectrum_text = "Frequency Spectrum Analyzer\n\n"
        spectrum_text += f"Center: {freq} MHz\n"
        spectrum_text += f"Span: {scan_range} MHz\n\n"

        spectrum_text += "Freq (MHz)  RSSI (dBm)  Graph\n"
        spectrum_text += "-" * 45 + "\n"

        for scan_freq, rssi in results:
            bars = int((rssi + 120) / 3)  # Scale RSSI to bars
            bars = max(0, min(20, bars))

            spectrum_text += f"{scan_freq:>7.2f}     {rssi:>4d}      "
            spectrum_text += "█" * bars + "\n"

        # Find peak
        peak_freq, peak_rssi = max(results, key=lambda x: x[1])
        spectrum_text += f"\nPeak: {peak_freq:.2f} MHz @ {peak_rssi} dBm"

        self.show_message("Spectrum Analyzer", spectrum_text)

    def protocol_decoder(self):
        """Декодирование протоколов"""
        if not self.current_capture:
            self.show_message(
                "Protocol Decoder",
                "No signal captured.\n\nCapture a signal first."
            )
            return

        pulses = self.current_capture.get_pulse_lengths()
        protocol = ProtocolDecoder.detect_protocol(pulses)

        result_text = "Protocol Decoder Results\n\n"
        result_text += f"Frequency: {self.current_capture.frequency} MHz\n"
        result_text += f"Duration: {self.current_capture.duration:.2f}s\n"
        result_text += f"Samples: {len(self.current_capture.samples)}\n"
        result_text += f"Pulses: {len(pulses)}\n\n"

        if protocol:
            result_text += f"Detected: {protocol}\n\n"

            if protocol == "Princeton":
                decoded = ProtocolDecoder.decode_princeton(pulses)
                if decoded:
                    result_text += f"Code: 0x{decoded['code']:06X}\n"
                    result_text += f"Pulse Length: {decoded['pulse_length']}us\n"
        else:
            result_text += "Protocol: Unknown\n\n"
            result_text += "Pulse pattern (first 20):\n"
            for i, pulse in enumerate(pulses[:20]):
                result_text += f"{i+1}. {abs(pulse)}us {'HIGH' if pulse > 0 else 'LOW'}\n"

        self.show_message("Protocol Decoder", result_text)

    def signal_generator(self):
        """Генератор сигналов"""
        if not self.enabled:
            self.show_error("CC1101 not available")
            return

        protocol_choice = self.show_menu(
            "Select Protocol",
            ["Princeton", "Custom RAW", "Cancel"]
        )

        if protocol_choice == 0:
            self._generate_princeton()
        elif protocol_choice == 1:
            self._generate_custom()

    def _generate_princeton(self):
        """Генерация Princeton сигнала"""
        code = self.get_user_input(
            "Enter 24-bit code (hex):",
            default="123456"
        )

        try:
            code_int = int(code, 16) & 0xFFFFFF
        except ValueError:
            self.show_error("Invalid code format")
            return

        # Generate signal
        pulses = SignalGenerator.generate_princeton(code_int)
        samples = SignalGenerator.pulses_to_samples(pulses)

        # Create capture
        capture = SignalCapture(self.current_frequency)
        for sample in samples:
            capture.add_sample(sample)
        capture.finalize()
        capture.protocol = "Princeton (Generated)"

        self.current_capture = capture

        self.show_message(
            "Generated",
            f"Generated Princeton signal\n"
            f"Code: 0x{code_int:06X}\n"
            f"Samples: {len(samples)}\n\n"
            "Use Replay to transmit"
        )

    def _generate_custom(self):
        """Генерация custom сигнала"""
        self.show_message(
            "Custom Generator",
            "Custom signal generator\n\n"
            "Feature coming soon.\n\n"
            "You can create pulses manually\n"
            "and save as .sub file."
        )

    def view_saved_signals(self):
        """Просмотр сохранённых сигналов"""
        if not self.saved_signals:
            self.show_message(
                "Saved Signals",
                "No saved signals yet.\n\n"
                "Capture and save a signal first."
            )
            return

        signal_list = "Saved Signals\n\n"
        signal_list += f"Location: {self.signals_dir}\n\n"

        for idx, signal in enumerate(self.saved_signals, 1):
            signal_list += f"{idx}. {signal['name']}\n"
            signal_list += f"   Freq: {signal['frequency']} MHz\n"
            signal_list += f"   Protocol: {signal['protocol'] or 'Unknown'}\n"
            signal_list += f"   Date: {signal['date']}\n\n"

        signal_list += f"Total: {len(self.saved_signals)} signals"

        self.show_message("Saved Signals", signal_list)

    def show_settings(self):
        """Настройки модуля"""
        if not self.enabled:
            settings_text = "Sub-GHz Module Settings\n\n"
            settings_text += "Status: Hardware not available\n\n"
            settings_text += "Check:\n"
            settings_text += "- SPI connection\n"
            settings_text += "- CC1101 wiring\n"
            settings_text += "- Configuration in config/main.yaml"
        else:
            settings_text = "Sub-GHz Module Settings\n\n"
            settings_text += f"Current Frequency: {self.current_frequency} MHz\n"
            settings_text += f"Modulation: {self.cc1101.modulation}\n"
            settings_text += f"RSSI: {self.cc1101.read_rssi()} dBm\n\n"

            settings_text += "Capabilities:\n"
            settings_text += "- Frequency: 300-928 MHz\n"
            settings_text += "- Modulations: ASK/OOK, 2FSK, GFSK, MSK\n"
            settings_text += "- Data rates: 0.6 - 500 kBaud\n"
            settings_text += "- TX Power: -30 to +10 dBm\n\n"

            settings_text += f"Saved Signals: {len(self.saved_signals)}\n"

        self.show_message("Settings", settings_text)

    def show_about(self):
        """О модуле"""
        about_text = """
        Sub-GHz Analyzer Module v2.0

        Hardware: CC1101 Sub-GHz Transceiver
        Frequency: 300-928 MHz
        Modulations: ASK/OOK, FSK, GFSK, MSK

        Features:
        - RAW signal capture and replay
        - Protocol detection and decoding
        - Flipper Zero compatible
        - Signal generation
        - Spectrum analyzer

        Supported Protocols:
        - Princeton (315/433MHz remotes)
        - Came (gate remotes)
        - Nice (gate remotes)
        - Custom RAW

        For educational and authorized use only.
        """

        self.show_message("About Sub-GHz Module", about_text)

    def stop_recording(self):
        """Остановка записи"""
        if self.is_recording:
            self.is_recording = False
            self.log_info("Recording stopped by user")

    # ========== Helper methods ==========

    def _save_current_signal(self):
        """Сохранить текущий захваченный сигнал"""
        if not self.current_capture:
            return

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        protocol_name = self.current_capture.protocol or "unknown"
        filename = f"{protocol_name}_{self.current_capture.frequency}MHz_{timestamp}.sub"
        filepath = os.path.join(self.signals_dir, filename)

        # Save in Flipper Zero format
        self.current_capture.save_to_file(filepath, format="sub")

        # Add to saved signals list
        signal_info = {
            'name': filename,
            'filepath': filepath,
            'frequency': self.current_capture.frequency,
            'protocol': self.current_capture.protocol,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self.saved_signals.append(signal_info)

        self.show_message(
            "Saved",
            f"Signal saved:\n{filename}\n\n"
            f"Format: Flipper Zero .sub\n"
            f"Location: {self.signals_dir}"
        )

        self.log_info(f"Signal saved: {filepath}")

    def _load_saved_signals(self):
        """Загрузить список сохранённых сигналов"""
        if not os.path.exists(self.signals_dir):
            return

        for filename in os.listdir(self.signals_dir):
            if filename.endswith('.sub'):
                filepath = os.path.join(self.signals_dir, filename)

                # Try to extract info from filename
                parts = filename.replace('.sub', '').split('_')

                signal_info = {
                    'name': filename,
                    'filepath': filepath,
                    'frequency': 433.92,  # Default
                    'protocol': parts[0] if parts else None,
                    'date': os.path.getmtime(filepath)
                }

                self.saved_signals.append(signal_info)

        self.log_info(f"Loaded {len(self.saved_signals)} saved signals")
