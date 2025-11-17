"""
Sub-GHz Module - захват и воспроизведение сигналов 433MHz через CC1101
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable


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
            version="1.0.0",
            priority=1  # Highest priority
        )

        self.spi_bus = 0
        self.spi_device = 1
        self.current_frequency = 433.92  # MHz
        self.is_recording = False
        self.saved_signals = []

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("Sub-GHz module loaded")

        # TODO: Инициализация CC1101 через SPI
        # try:
        #     import spidev
        #     self.spi = spidev.SpiDev()
        #     self.spi.open(self.spi_bus, self.spi_device)
        #     self.initialize_cc1101()
        # except Exception as e:
        #     self.log_error(f"Failed to initialize CC1101: {e}")

    def on_unload(self):
        """Освобождение ресурсов"""
        self.log_info("Sub-GHz module unloaded")

        # TODO: Закрыть SPI
        # if hasattr(self, 'spi'):
        #     self.spi.close()

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
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if self.is_recording:
            return f"SubGHz: Recording {self.current_frequency}MHz"
        return f"SubGHz: Ready"

    def get_hotkeys(self):
        """Горячие клавиши"""
        return {
            'r': self.read_signal,
            'p': self.replay_signal,
            's': self.stop_recording,
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

        # TODO: Реальный захват
        self.show_message(
            "Capture",
            f"Capturing signal at {freq}MHz for {duration}s...\n"
            "(This is a demo - actual hardware integration required)"
        )

        self.log_info(f"Captured signal: {freq}MHz, {duration}s")

        # Сохраняем в список
        signal_data = {
            'frequency': freq,
            'duration': duration,
            'modulation': 'ASK/OOK',
            'filename': f'capture_{freq}MHz.sub'
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
            f"{s['filename']} ({s['frequency']}MHz)"
            for s in self.saved_signals
        ]

        idx = self.show_menu("Select Signal to Replay", signal_names)

        if idx >= 0 and idx < len(self.saved_signals):
            signal = self.saved_signals[idx]

            self.show_message(
                "Replay",
                f"Replaying signal:\n"
                f"Frequency: {signal['frequency']}MHz\n"
                f"Modulation: {signal['modulation']}\n"
                "(This is a demo)"
            )

            self.log_info(f"Replayed signal: {signal['filename']}")

    def frequency_analyzer(self):
        """Анализ частотного спектра"""
        self.show_message(
            "Frequency Analyzer",
            "Frequency Analyzer\n\n"
            "Current frequency: 433.92 MHz\n"
            "RSSI: -85 dBm\n"
            "Bandwidth: 200 kHz\n\n"
            "[This is a demo view]\n\n"
            "ASCII Waterfall would be displayed here\n"
            "in real implementation."
        )

    def protocol_decoder(self):
        """Декодер протоколов"""
        self.show_message(
            "Protocol Decoder",
            "Supported Protocols:\n\n"
            "- Princeton\n"
            "- Came\n"
            "- Nice\n"
            "- Gate-TX\n"
            "- KeeLoq\n\n"
            "Auto-detection: Enabled\n"
            "(Demo mode)"
        )

    def signal_generator(self):
        """Генератор сигналов"""
        self.show_message(
            "Signal Generator",
            "Signal Generator\n\n"
            "Generate custom Sub-GHz signals\n"
            "(Coming soon)"
        )

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
                f"Duration: {signal['duration']}s\n\n"
            )

        self.show_message("Saved Signals", signal_list)

    def show_settings(self):
        """Настройки модуля"""
        settings_text = (
            "Sub-GHz Module Settings\n\n"
            f"Current Frequency: {self.current_frequency} MHz\n"
            f"SPI Bus: {self.spi_bus}\n"
            f"SPI Device: {self.spi_device}\n\n"
            "Default Modulation: ASK/OOK\n"
            "TX Power: 10 dBm\n"
            "(Settings are read-only in demo mode)"
        )

        self.show_message("Settings", settings_text)

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
