"""
SDR Controller - управление HackRF One и RTL-SDR
"""

import subprocess
import os
import logging
from typing import Optional, Dict, List
from datetime import datetime


class SDRController:
    """Controller for SDR devices (HackRF, RTL-SDR)"""

    def __init__(self, device_priority: List[str] = None):
        """
        Initialize SDR controller.

        Args:
            device_priority: Priority list of devices to try ["hackrf", "rtlsdr"]
        """
        self.logger = logging.getLogger("cyberdeck.sdr")

        if device_priority is None:
            device_priority = ["hackrf", "rtlsdr"]

        self.device_priority = device_priority
        self.active_device = None
        self.device_info = {}

    def detect_devices(self) -> Dict[str, bool]:
        """
        Detect available SDR devices.

        Returns:
            Dict of device availability
        """
        available = {}

        # Check HackRF
        available['hackrf'] = self._check_hackrf()

        # Check RTL-SDR
        available['rtlsdr'] = self._check_rtlsdr()

        self.logger.info(f"SDR devices detected: {available}")
        return available

    def _check_hackrf(self) -> bool:
        """Check if HackRF is available"""
        try:
            result = subprocess.run(
                ["hackrf_info"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and "Found HackRF" in result.stdout:
                # Parse device info
                self.device_info['hackrf'] = self._parse_hackrf_info(result.stdout)
                return True

            return False

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _check_rtlsdr(self) -> bool:
        """Check if RTL-SDR is available"""
        try:
            result = subprocess.run(
                ["rtl_test", "-t"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if "Found" in result.stdout:
                # Parse device info
                self.device_info['rtlsdr'] = self._parse_rtlsdr_info(result.stdout)
                return True

            return False

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _parse_hackrf_info(self, output: str) -> Dict:
        """Parse HackRF device info"""
        info = {}

        for line in output.split('\n'):
            if "Serial number" in line:
                info['serial'] = line.split(':')[1].strip()
            elif "Board ID" in line:
                info['board_id'] = line.split(':')[1].strip()
            elif "Firmware Version" in line:
                info['firmware'] = line.split(':')[1].strip()

        return info

    def _parse_rtlsdr_info(self, output: str) -> Dict:
        """Parse RTL-SDR device info"""
        info = {}

        for line in output.split('\n'):
            if "Found" in line:
                info['device'] = line.strip()
            elif "Tuner" in line:
                info['tuner'] = line.split(':')[1].strip()

        return info

    def record_iq(self, frequency: float, sample_rate: float, duration: int,
                  output_file: str, device: str = None) -> bool:
        """
        Record IQ samples.

        Args:
            frequency: Center frequency in MHz
            sample_rate: Sample rate in MSPS
            duration: Recording duration in seconds
            output_file: Output file path
            device: Device to use (hackrf or rtlsdr)

        Returns:
            bool: True if successful
        """
        if device is None:
            # Auto-select device
            available = self.detect_devices()
            for dev in self.device_priority:
                if available.get(dev):
                    device = dev
                    break

        if device is None:
            self.logger.error("No SDR device available")
            return False

        self.logger.info(f"Recording IQ: {frequency}MHz @ {sample_rate}MSPS for {duration}s")

        try:
            if device == "hackrf":
                return self._record_hackrf(frequency, sample_rate, duration, output_file)
            elif device == "rtlsdr":
                return self._record_rtlsdr(frequency, sample_rate, duration, output_file)
            else:
                self.logger.error(f"Unknown device: {device}")
                return False

        except Exception as e:
            self.logger.error(f"IQ recording failed: {e}")
            return False

    def _record_hackrf(self, frequency: float, sample_rate: float, duration: int,
                      output_file: str) -> bool:
        """Record IQ with HackRF"""
        # Convert frequency to Hz
        freq_hz = int(frequency * 1e6)

        # Convert sample rate to Hz
        sample_rate_hz = int(sample_rate * 1e6)

        # Calculate number of samples
        num_samples = int(sample_rate_hz * duration)

        cmd = [
            "hackrf_transfer",
            "-r", output_file,
            "-f", str(freq_hz),
            "-s", str(sample_rate_hz),
            "-n", str(num_samples)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 10
        )

        if result.returncode == 0:
            self.logger.info(f"HackRF recording saved: {output_file}")
            return True
        else:
            self.logger.error(f"HackRF recording failed: {result.stderr}")
            return False

    def _record_rtlsdr(self, frequency: float, sample_rate: float, duration: int,
                      output_file: str) -> bool:
        """Record IQ with RTL-SDR"""
        # Convert frequency to Hz
        freq_hz = int(frequency * 1e6)

        # Convert sample rate to Hz
        sample_rate_hz = int(sample_rate * 1e6)

        # Calculate number of samples
        num_samples = int(sample_rate_hz * duration * 2)  # I+Q samples

        cmd = [
            "rtl_sdr",
            "-f", str(freq_hz),
            "-s", str(sample_rate_hz),
            "-n", str(num_samples),
            output_file
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 10
        )

        if result.returncode == 0:
            self.logger.info(f"RTL-SDR recording saved: {output_file}")
            return True
        else:
            self.logger.error(f"RTL-SDR recording failed: {result.stderr}")
            return False

    def spectrum_analyzer(self, start_freq: float, stop_freq: float,
                         bin_size: float = 1.0, device: str = None) -> Optional[List]:
        """
        Perform spectrum analysis.

        Args:
            start_freq: Start frequency in MHz
            stop_freq: Stop frequency in MHz
            bin_size: Bin size in MHz
            device: Device to use

        Returns:
            List of (frequency, power) tuples or None
        """
        if device is None:
            available = self.detect_devices()
            for dev in self.device_priority:
                if available.get(dev):
                    device = dev
                    break

        if device is None:
            return None

        # Use rtl_power for RTL-SDR (HackRF would need different tool)
        if device == "rtlsdr":
            return self._spectrum_rtlsdr(start_freq, stop_freq, bin_size)
        else:
            self.logger.warning("Spectrum analyzer not implemented for HackRF")
            return None

    def _spectrum_rtlsdr(self, start_freq: float, stop_freq: float,
                        bin_size: float) -> Optional[List]:
        """Spectrum analysis with RTL-SDR using rtl_power"""
        try:
            # Convert to Hz
            start_hz = int(start_freq * 1e6)
            stop_hz = int(stop_freq * 1e6)
            bin_hz = int(bin_size * 1e6)

            # Output file
            output_file = "/tmp/rtl_power_output.csv"

            cmd = [
                "rtl_power",
                "-f", f"{start_hz}:{stop_hz}:{bin_hz}",
                "-i", "1",  # 1 second integration
                output_file
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10
            )

            if result.returncode == 0 and os.path.exists(output_file):
                # Parse output
                spectrum = []
                with open(output_file, 'r') as f:
                    for line in f:
                        parts = line.strip().split(',')
                        if len(parts) > 6:
                            # Extract frequency and power data
                            freq_low = float(parts[2])
                            freq_high = float(parts[3])
                            freq_center = (freq_low + freq_high) / 2
                            # Power values start from index 6
                            powers = [float(p) for p in parts[6:]]
                            avg_power = sum(powers) / len(powers) if powers else 0

                            spectrum.append((freq_center / 1e6, avg_power))

                os.remove(output_file)
                return spectrum

            return None

        except Exception as e:
            self.logger.error(f"Spectrum analysis failed: {e}")
            return None

    def transmit(self, frequency: float, sample_rate: float, input_file: str,
                device: str = "hackrf") -> bool:
        """
        Transmit from IQ file (HackRF only).

        Args:
            frequency: Center frequency in MHz
            sample_rate: Sample rate in MSPS
            input_file: Input IQ file
            device: Device (only hackrf supports TX)

        Returns:
            bool: True if successful
        """
        if device != "hackrf":
            self.logger.error("Only HackRF supports transmission")
            return False

        try:
            freq_hz = int(frequency * 1e6)
            sample_rate_hz = int(sample_rate * 1e6)

            cmd = [
                "hackrf_transfer",
                "-t", input_file,
                "-f", str(freq_hz),
                "-s", str(sample_rate_hz),
                "-x", "47"  # TX gain
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                self.logger.info("HackRF transmission complete")
                return True
            else:
                self.logger.error(f"HackRF transmission failed: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Transmission failed: {e}")
            return False
