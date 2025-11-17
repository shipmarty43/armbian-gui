"""
SDR Module - Software Defined Radio для HackRF One и RTL-SDR
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable
import os
from datetime import datetime


class SDRModule(BaseModule):
    """
    SDR модуль для работы с HackRF One и RTL-SDR.

    Функции:
    - IQ запись (RX)
    - IQ воспроизведение (TX, только HackRF)
    - Spectrum analyzer
    - Поддержка HackRF One и RTL-SDR
    - Управление recordings
    """

    def __init__(self):
        super().__init__(
            name="SDR Radio",
            version="1.0.0",
            priority=6
        )

        self.sdr = None
        self.available_devices = {}
        self.recordings_dir = "iq_samples"
        self.recordings = []

        os.makedirs(self.recordings_dir, exist_ok=True)

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("SDR module loading...")

        # Load configuration
        config = self.load_config("config/main.yaml")
        sdr_config = config.get('sdr', {})

        if not sdr_config.get('enabled', False):
            self.log_info("SDR disabled in config")
            self.enabled = False
            return

        # Initialize SDR controller
        try:
            from .sdr_controller import SDRController

            device_priority = sdr_config.get('device_priority', ['hackrf', 'rtlsdr'])
            self.sdr = SDRController(device_priority=device_priority)

            # Detect devices
            self.available_devices = self.sdr.detect_devices()

            if not any(self.available_devices.values()):
                self.log_warning("No SDR devices detected")
                self.log_warning("Install hackrf-tools or rtl-sdr package")
                self.enabled = False
                return

            # Load recordings
            self._load_recordings()

            devices_str = ", ".join([k for k, v in self.available_devices.items() if v])
            self.log_info(f"SDR module loaded: {devices_str}")
            self.enabled = True

        except Exception as e:
            self.log_error(f"Failed to initialize SDR: {e}")
            self.enabled = False

    def on_unload(self):
        """Освобождение ресурсов"""
        self.log_info("SDR module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.enabled:
            return [
                ("Status: No SDR Devices Detected", lambda: None),
                ("Help", self.show_help),
            ]

        menu = []

        # RX (both devices)
        menu.append(("Record IQ Samples", self.record_iq))

        # TX (HackRF only)
        if self.available_devices.get('hackrf'):
            menu.append(("Transmit IQ Samples", self.transmit_iq))

        # Spectrum analyzer (RTL-SDR)
        if self.available_devices.get('rtlsdr'):
            menu.append(("Spectrum Analyzer", self.spectrum_analyzer))

        menu.extend([
            ("Recordings Manager", self.recordings_manager),
            ("Settings", self.show_settings),
        ])

        return menu

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.enabled:
            return "SDR: Disabled"

        devices = []
        if self.available_devices.get('hackrf'):
            devices.append("HackRF")
        if self.available_devices.get('rtlsdr'):
            devices.append("RTL-SDR")

        return f"SDR: {', '.join(devices)}"

    # ========== Record IQ ==========

    def record_iq(self):
        """Запись IQ сэмплов"""
        # Select device
        device = self._select_device()
        if not device:
            return

        # Get parameters
        freq_input = self.get_user_input("Center frequency (MHz):", default="433.92")
        rate_input = self.get_user_input("Sample rate (MSPS):", default="2.0")
        duration_input = self.get_user_input("Duration (seconds):", default="10")

        try:
            frequency = float(freq_input)
            sample_rate = float(rate_input)
            duration = int(duration_input)
        except ValueError:
            self.show_error("Invalid parameters")
            return

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"iq_{int(frequency)}MHz_{timestamp}.bin"
        filepath = os.path.join(self.recordings_dir, filename)

        # Confirm
        confirm = self.show_menu(
            "Record IQ Samples",
            [
                f"Device: {device}",
                f"Frequency: {frequency} MHz",
                f"Sample rate: {sample_rate} MSPS",
                f"Duration: {duration}s",
                "",
                f"Output: {filename}",
                "",
                "Start Recording",
                "Cancel"
            ]
        )

        if confirm != 7:
            return

        self.show_message(
            "Recording",
            f"Recording IQ samples...\n\n"
            f"{frequency} MHz @ {sample_rate} MSPS\n"
            f"Duration: {duration}s\n\n"
            "Please wait..."
        )

        # Record
        success = self.sdr.record_iq(frequency, sample_rate, duration, filepath, device)

        if success:
            # Get file size
            file_size = os.path.getsize(filepath)
            size_mb = file_size / (1024 * 1024)

            self.show_message(
                "Recording Complete",
                f"IQ samples saved!\n\n"
                f"File: {filename}\n"
                f"Size: {size_mb:.1f} MB\n"
                f"Samples: {int(sample_rate * 1e6 * duration)}"
            )

            self.recordings.append({
                'filename': filename,
                'frequency': frequency,
                'sample_rate': sample_rate,
                'duration': duration,
                'size': file_size
            })

        else:
            self.show_error("Recording failed!\n\nCheck SDR connection.")

    # ========== Transmit IQ ==========

    def transmit_iq(self):
        """Передача IQ сэмплов (только HackRF)"""
        if not self.recordings:
            self.show_message(
                "No Recordings",
                "No IQ recordings found.\n\n"
                "Record some samples first."
            )
            return

        # Select recording
        recording_names = [r['filename'] for r in self.recordings] + ["Cancel"]

        choice = self.show_menu("Select Recording", recording_names)

        if choice >= len(self.recordings):
            return

        recording = self.recordings[choice]
        filepath = os.path.join(self.recordings_dir, recording['filename'])

        # Get TX parameters
        freq_input = self.get_user_input(
            "TX Frequency (MHz):",
            default=str(recording['frequency'])
        )

        rate_input = self.get_user_input(
            "Sample rate (MSPS):",
            default=str(recording['sample_rate'])
        )

        try:
            frequency = float(freq_input)
            sample_rate = float(rate_input)
        except ValueError:
            self.show_error("Invalid parameters")
            return

        # Confirm
        confirm = self.show_menu(
            "Transmit IQ Samples",
            [
                "⚠️ WARNING: RF Transmission!",
                "",
                f"File: {recording['filename']}",
                f"Frequency: {frequency} MHz",
                f"Sample rate: {sample_rate} MSPS",
                "",
                "Make sure this is legal!",
                "",
                "Transmit",
                "Cancel"
            ]
        )

        if confirm != 8:
            return

        self.show_message(
            "Transmitting",
            f"Transmitting IQ samples...\n\n"
            f"{frequency} MHz @ {sample_rate} MSPS\n\n"
            "TX in progress..."
        )

        # Transmit
        success = self.sdr.transmit(frequency, sample_rate, filepath, device="hackrf")

        if success:
            self.show_message("Complete", "Transmission complete!")
        else:
            self.show_error("Transmission failed!")

    # ========== Spectrum Analyzer ==========

    def spectrum_analyzer(self):
        """Spectrum analyzer (RTL-SDR)"""
        # Get parameters
        start_input = self.get_user_input("Start frequency (MHz):", default="400")
        stop_input = self.get_user_input("Stop frequency (MHz):", default="470")
        bin_input = self.get_user_input("Bin size (MHz):", default="1.0")

        try:
            start_freq = float(start_input)
            stop_freq = float(stop_input)
            bin_size = float(bin_input)
        except ValueError:
            self.show_error("Invalid parameters")
            return

        self.show_message(
            "Analyzing",
            f"Spectrum analysis...\n\n"
            f"{start_freq} - {stop_freq} MHz\n"
            f"Bin size: {bin_size} MHz\n\n"
            "Please wait..."
        )

        # Analyze
        spectrum = self.sdr.spectrum_analyzer(start_freq, stop_freq, bin_size, device="rtlsdr")

        if spectrum:
            # Find peak
            peak = max(spectrum, key=lambda x: x[1])

            result_text = f"Spectrum Analysis Complete!\n\n"
            result_text += f"Range: {start_freq}-{stop_freq} MHz\n"
            result_text += f"Bins: {len(spectrum)}\n\n"
            result_text += f"Peak: {peak[0]:.2f} MHz ({peak[1]:.1f} dB)\n\n"

            # Show top 5 frequencies
            sorted_spectrum = sorted(spectrum, key=lambda x: x[1], reverse=True)
            result_text += "Top frequencies:\n"
            for i, (freq, power) in enumerate(sorted_spectrum[:5], 1):
                result_text += f"{i}. {freq:.2f} MHz: {power:.1f} dB\n"

            self.show_message("Spectrum Analysis", result_text)

        else:
            self.show_error("Spectrum analysis failed!")

    # ========== Recordings Manager ==========

    def recordings_manager(self):
        """Управление recordings"""
        if not self.recordings:
            self.show_message(
                "Recordings Manager",
                "No recordings found.\n\n"
                "Record some IQ samples first."
            )
            return

        actions = [
            "View Recordings",
            "Delete Recording",
            "Back"
        ]

        choice = self.show_menu("Recordings Manager", actions)

        if choice == 0:
            self._view_recordings()
        elif choice == 1:
            self._delete_recording()

    def _view_recordings(self):
        """View all recordings"""
        recordings_text = "IQ Recordings:\n\n"

        for i, rec in enumerate(self.recordings, 1):
            size_mb = rec['size'] / (1024 * 1024)
            recordings_text += f"{i}. {rec['filename']}\n"
            recordings_text += f"   Freq: {rec['frequency']} MHz\n"
            recordings_text += f"   Rate: {rec['sample_rate']} MSPS\n"
            recordings_text += f"   Duration: {rec['duration']}s\n"
            recordings_text += f"   Size: {size_mb:.1f} MB\n\n"

        self.show_message("Recordings", recordings_text)

    def _delete_recording(self):
        """Delete recording"""
        self.show_message("Delete", "Delete feature coming soon...")

    def _load_recordings(self):
        """Load recordings from directory"""
        self.recordings = []

        if not os.path.exists(self.recordings_dir):
            return

        for filename in os.listdir(self.recordings_dir):
            if filename.endswith('.bin'):
                filepath = os.path.join(self.recordings_dir, filename)
                file_size = os.path.getsize(filepath)

                # Try to parse filename for metadata
                # Format: iq_433MHz_20231117_120000.bin
                import re
                match = re.search(r'iq_(\d+)MHz_', filename)
                freq = float(match.group(1)) if match else 0

                self.recordings.append({
                    'filename': filename,
                    'frequency': freq,
                    'sample_rate': 2.0,  # Default
                    'duration': 0,
                    'size': file_size
                })

        self.log_info(f"Loaded {len(self.recordings)} recordings")

    def _select_device(self) -> str:
        """Select SDR device"""
        available = [k for k, v in self.available_devices.items() if v]

        if len(available) == 1:
            return available[0]

        if len(available) > 1:
            choice = self.show_menu(
                "Select SDR Device",
                [d.upper() for d in available] + ["Cancel"]
            )

            if choice < len(available):
                return available[choice]

        return None

    # ========== Settings ==========

    def show_settings(self):
        """Настройки модуля"""
        settings_text = "SDR Module Settings\n\n"

        settings_text += "Devices:\n"
        for device, available in self.available_devices.items():
            status = "✓" if available else "✗"
            settings_text += f"  {status} {device.upper()}\n"

            if available and device in self.sdr.device_info:
                info = self.sdr.device_info[device]
                for key, value in info.items():
                    settings_text += f"     {key}: {value}\n"

        settings_text += f"\nRecordings directory: {self.recordings_dir}\n"
        settings_text += f"Recordings: {len(self.recordings)}\n"

        self.show_message("Settings", settings_text)

    def show_help(self):
        """Show help information"""
        help_text = """SDR Module Help

Supported Devices:
- HackRF One (RX + TX)
- RTL-SDR (RX only)

Installation:
- HackRF: apt install hackrf
- RTL-SDR: apt install rtl-sdr

Features:
- IQ recording
- IQ transmission (HackRF)
- Spectrum analysis (RTL-SDR)

File Format:
- Complex int8 (IQ interleaved)
- Compatible with GNU Radio
"""
        self.show_message("Help", help_text)
