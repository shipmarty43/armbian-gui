"""
Signal Analyzer - анализ и декодирование Sub-GHz сигналов
"""

import time
import struct
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class SignalCapture:
    """Класс для хранения захваченного сигнала"""

    def __init__(self, frequency: float, sample_rate: int = 100000):
        """
        Initialize signal capture.

        Args:
            frequency: Carrier frequency in MHz
            sample_rate: Sampling rate in Hz
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.samples: List[int] = []
        self.timestamp = datetime.now()
        self.duration = 0.0
        self.rssi = []
        self.protocol = None

    def add_sample(self, value: int, rssi: int = 0):
        """Add a sample to the capture"""
        self.samples.append(value)
        self.rssi.append(rssi)

    def finalize(self):
        """Finalize capture and calculate duration"""
        if self.samples:
            self.duration = len(self.samples) / float(self.sample_rate)

    def get_pulse_lengths(self) -> List[int]:
        """
        Get pulse lengths from samples.

        Returns:
            List[int]: List of pulse lengths in microseconds
        """
        if not self.samples:
            return []

        pulses = []
        current_state = self.samples[0]
        pulse_length = 0

        for sample in self.samples:
            if sample == current_state:
                pulse_length += 1
            else:
                # Convert to microseconds
                pulse_us = int((pulse_length / self.sample_rate) * 1000000)
                pulses.append(pulse_us if current_state else -pulse_us)

                current_state = sample
                pulse_length = 1

        return pulses

    def save_to_file(self, filename: str, format: str = "sub"):
        """
        Save signal to file.

        Args:
            filename: Output filename
            format: File format ("sub" for Flipper Zero format, "json", "raw")
        """
        if format == "sub":
            self._save_sub_format(filename)
        elif format == "json":
            self._save_json_format(filename)
        elif format == "raw":
            self._save_raw_format(filename)

    def _save_sub_format(self, filename: str):
        """Save in Flipper Zero .sub format"""
        with open(filename, 'w') as f:
            f.write("Filetype: Flipper SubGhz RAW File\n")
            f.write(f"Version: 1\n")
            f.write(f"Frequency: {int(self.frequency * 1000000)}\n")
            f.write(f"Preset: FuriHalSubGhzPresetOok650Async\n")
            f.write(f"Protocol: RAW\n")

            pulses = self.get_pulse_lengths()
            f.write(f"RAW_Data: {' '.join(map(str, pulses))}\n")

    def _save_json_format(self, filename: str):
        """Save in JSON format"""
        data = {
            'frequency': self.frequency,
            'sample_rate': self.sample_rate,
            'duration': self.duration,
            'timestamp': self.timestamp.isoformat(),
            'samples': self.samples[:10000],  # Limit for size
            'rssi_avg': sum(self.rssi) / len(self.rssi) if self.rssi else 0,
            'protocol': self.protocol
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def _save_raw_format(self, filename: str):
        """Save raw binary format"""
        with open(filename, 'wb') as f:
            # Header
            f.write(struct.pack('<I', int(self.frequency * 1000000)))
            f.write(struct.pack('<I', self.sample_rate))
            f.write(struct.pack('<I', len(self.samples)))

            # Samples
            for sample in self.samples:
                f.write(struct.pack('B', sample))

    @staticmethod
    def load_from_file(filename: str) -> Optional['SignalCapture']:
        """
        Load signal from file.

        Args:
            filename: Input filename

        Returns:
            SignalCapture or None
        """
        try:
            if filename.endswith('.sub'):
                return SignalCapture._load_sub_format(filename)
            elif filename.endswith('.json'):
                return SignalCapture._load_json_format(filename)
            elif filename.endswith('.raw'):
                return SignalCapture._load_raw_format(filename)
        except Exception as e:
            print(f"Failed to load signal: {e}")
            return None

    @staticmethod
    def _load_sub_format(filename: str) -> Optional['SignalCapture']:
        """Load from Flipper Zero .sub format"""
        with open(filename, 'r') as f:
            lines = f.readlines()

        frequency = None
        pulses = None

        for line in lines:
            if line.startswith("Frequency:"):
                frequency = int(line.split(':')[1].strip()) / 1000000.0
            elif line.startswith("RAW_Data:"):
                pulses_str = line.split(':')[1].strip()
                pulses = [int(p) for p in pulses_str.split()]

        if frequency and pulses:
            capture = SignalCapture(frequency)

            # Convert pulses back to samples (simplified)
            for pulse in pulses:
                length = abs(pulse)
                value = 1 if pulse > 0 else 0

                for _ in range(length):
                    capture.add_sample(value)

            capture.finalize()
            return capture

        return None

    @staticmethod
    def _load_json_format(filename: str) -> Optional['SignalCapture']:
        """Load from JSON format"""
        with open(filename, 'r') as f:
            data = json.load(f)

        capture = SignalCapture(
            frequency=data['frequency'],
            sample_rate=data.get('sample_rate', 100000)
        )

        for sample in data.get('samples', []):
            capture.add_sample(sample)

        capture.finalize()
        return capture


class ProtocolDecoder:
    """Декодер протоколов Sub-GHz"""

    @staticmethod
    def detect_protocol(pulses: List[int]) -> Optional[str]:
        """
        Detect protocol from pulse pattern.

        Args:
            pulses: List of pulse lengths

        Returns:
            str: Protocol name or None
        """
        if not pulses or len(pulses) < 10:
            return None

        # Princeton protocol detection
        if ProtocolDecoder._is_princeton(pulses):
            return "Princeton"

        # Came protocol detection
        if ProtocolDecoder._is_came(pulses):
            return "Came"

        # Nice protocol detection
        if ProtocolDecoder._is_nice(pulses):
            return "Nice"

        return None

    @staticmethod
    def _is_princeton(pulses: List[int]) -> bool:
        """Check if signal matches Princeton protocol"""
        # Princeton: short pulse ~350us, long pulse ~1050us
        # Pattern: sync (31x short) + data (24 bits)

        if len(pulses) < 50:
            return False

        # Check for sync pattern (many short pulses)
        short_count = sum(1 for p in pulses[:40] if 250 < abs(p) < 450)
        return short_count > 30

    @staticmethod
    def _is_came(pulses: List[int]) -> bool:
        """Check if signal matches Came protocol"""
        # Came: typically uses longer pulses ~600-800us
        if len(pulses) < 24:
            return False

        avg_pulse = sum(abs(p) for p in pulses[:24]) / 24
        return 500 < avg_pulse < 900

    @staticmethod
    def _is_nice(pulses: List[int]) -> bool:
        """Check if signal matches Nice protocol"""
        # Nice: specific timing patterns
        if len(pulses) < 20:
            return False

        # Check for characteristic Nice timing
        return any(1200 < abs(p) < 1400 for p in pulses[:20])

    @staticmethod
    def decode_princeton(pulses: List[int]) -> Optional[Dict]:
        """
        Decode Princeton protocol.

        Returns:
            Dict: {'code': int, 'pulse_length': int} or None
        """
        if not ProtocolDecoder._is_princeton(pulses):
            return None

        # Skip sync pattern
        data_start = 31

        # Decode 24-bit code
        code = 0
        pulse_length = 0

        for i in range(data_start, min(data_start + 48, len(pulses)), 2):
            if i + 1 >= len(pulses):
                break

            p1 = abs(pulses[i])
            p2 = abs(pulses[i + 1])

            # Determine bit value based on pulse lengths
            if p1 < 500 and p2 > 800:
                bit = 0
            elif p1 > 800 and p2 < 500:
                bit = 1
            else:
                continue

            code = (code << 1) | bit

            if pulse_length == 0:
                pulse_length = min(p1, p2)

        return {
            'protocol': 'Princeton',
            'code': code,
            'pulse_length': pulse_length
        }


class SignalGenerator:
    """Генератор сигналов для различных протоколов"""

    @staticmethod
    def generate_princeton(code: int, pulse_length: int = 350) -> List[int]:
        """
        Generate Princeton protocol signal.

        Args:
            code: 24-bit code
            pulse_length: Base pulse length in microseconds

        Returns:
            List[int]: Pulse pattern
        """
        pulses = []

        # Sync pattern (31x short pulses)
        for _ in range(31):
            pulses.append(pulse_length)
            pulses.append(-pulse_length)

        # Data (24 bits)
        for i in range(23, -1, -1):
            bit = (code >> i) & 1

            if bit == 0:
                # Short-long pattern
                pulses.append(pulse_length)
                pulses.append(-pulse_length * 3)
            else:
                # Long-short pattern
                pulses.append(pulse_length * 3)
                pulses.append(-pulse_length)

        return pulses

    @staticmethod
    def pulses_to_samples(pulses: List[int], sample_rate: int = 100000) -> List[int]:
        """
        Convert pulse pattern to samples.

        Args:
            pulses: Pulse lengths in microseconds
            sample_rate: Sample rate in Hz

        Returns:
            List[int]: Sample values (0 or 1)
        """
        samples = []

        for pulse in pulses:
            duration_us = abs(pulse)
            value = 1 if pulse > 0 else 0

            # Convert to number of samples
            num_samples = int((duration_us / 1000000.0) * sample_rate)

            for _ in range(num_samples):
                samples.append(value)

        return samples
