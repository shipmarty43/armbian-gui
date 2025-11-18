"""
SDR Module - Software Defined Radio
Support for HackRF One and RTL-SDR
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional
import os
import time
import numpy as np

try:
    import SoapySDR
    from SoapySDR import SOAPY_SDR_RX, SOAPY_SDR_CF32
    SOAPY_AVAILABLE = True
except ImportError:
    SOAPY_AVAILABLE = False


class SDRModule(BaseModule):
    """
    SDR модуль для работы с HackRF One и RTL-SDR.
    
    Функции:
    - Spectrum analyzer
    - Signal recording
    - FM/AM demodulation
    - Waterfall display
    - IQ sample capture
    """
    
    def __init__(self):
        super().__init__(
            name="SDR Analysis",
            version="1.0.0",
            priority=6
        )
        
        self.sdr = None
        self.hardware_enabled = False
        self.device_type = None
        
        # SDR parameters
        self.center_freq = 100.0e6  # 100 MHz
        self.sample_rate = 2.048e6  # 2.048 MHz
        self.gain = 20
        
        self.samples_dir = "iq_samples"
        os.makedirs(self.samples_dir, exist_ok=True)
    
    def on_load(self):
        """Инициализация модуля"""
        self.log_info("SDR module loading...")
        
        if not SOAPY_AVAILABLE:
            self.log_warning("SoapySDR not available - running in demo mode")
            return
            
        # Load config
        config = self.get_config().get('sdr', {})
        
        if not config.get('enabled', False):
            self.log_info("SDR disabled in config")
            return
            
        try:
            # List available devices
            devices = SoapySDR.Device.enumerate()
            
            if not devices:
                self.log_warning("No SDR devices found")
                return
                
            # Try to open first device
            device_args = devices[0]
            self.sdr = SoapySDR.Device(device_args)
            
            # Detect device type
            if 'hackrf' in str(device_args).lower():
                self.device_type = "HackRF One"
            elif 'rtlsdr' in str(device_args).lower():
                self.device_type = "RTL-SDR"
            else:
                self.device_type = "Unknown SDR"
                
            self.hardware_enabled = True
            self.log_info(f"SDR initialized: {self.device_type}")
            
        except Exception as e:
            self.log_error(f"Failed to initialize SDR: {e}")
    
    def on_unload(self):
        """Освобождение ресурсов"""
        if self.sdr:
            try:
                self.sdr = None
            except Exception as e:
                self.log_error(f"Error closing SDR: {e}")
    
    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        return [
            ("Spectrum Analyzer", self.spectrum_analyzer),
            ("Record IQ Samples", self.record_samples),
            ("FM Demodulator", self.fm_demod),
            ("Waterfall Display", self.waterfall),
            ("Device Settings", self.settings),
            ("SDR Status", self.show_status),
        ]
    
    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        hw_status = "HW" if self.hardware_enabled else "DEMO"
        freq_mhz = self.center_freq / 1e6
        return f"SDR[{hw_status}]: {freq_mhz:.2f}MHz"
    
    def get_hotkeys(self):
        """Горячие клавиши"""
        return {
            's': self.spectrum_analyzer,
            'r': self.record_samples,
            'w': self.waterfall,
        }
    
    # ========== Функции модуля ==========
    
    def spectrum_analyzer(self):
        """Spectrum analyzer"""
        if not self.hardware_enabled:
            self.demo_spectrum_analyzer()
            return
            
        try:
            # Configure RX
            self.sdr.setSampleRate(SOAPY_SDR_RX, 0, self.sample_rate)
            self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
            self.sdr.setGain(SOAPY_SDR_RX, 0, self.gain)
            
            # Create stream
            rxStream = self.sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
            self.sdr.activateStream(rxStream)
            
            # Receive samples
            buff = np.array([0]*1024, np.complex64)
            sr = self.sdr.readStream(rxStream, [buff], len(buff))
            
            if sr.ret > 0:
                # Compute FFT
                fft = np.fft.fft(buff)
                fft_shifted = np.fft.fftshift(fft)
                magnitude = np.abs(fft_shifted)
                magnitude_db = 20 * np.log10(magnitude + 1e-10)
                
                # Find peak
                peak_idx = np.argmax(magnitude_db)
                peak_db = magnitude_db[peak_idx]
                
                # Simple ASCII spectrum
                spectrum_text = f"Spectrum Analyzer\n\n"
                spectrum_text += f"Center: {self.center_freq/1e6:.2f}MHz\n"
                spectrum_text += f"Sample Rate: {self.sample_rate/1e6:.2f}MHz\n"
                spectrum_text += f"Gain: {self.gain}dB\n\n"
                spectrum_text += f"Peak: {peak_db:.1f}dBFS\n\n"
                
                # Simple bar chart
                for i in range(0, len(magnitude_db), 20):
                    level = int(magnitude_db[i] + 100)  # Scale to 0-100
                    bars = '█' * max(0, min(level, 50))
                    spectrum_text += f"{bars}\n"
                
                self.show_message("Spectrum Analyzer", spectrum_text)
            
            # Cleanup
            self.sdr.deactivateStream(rxStream)
            self.sdr.closeStream(rxStream)
            
        except Exception as e:
            self.show_error(f"Spectrum analyzer error: {e}")
    
    def demo_spectrum_analyzer(self):
        """Demo spectrum analyzer"""
        self.show_message(
            "Spectrum Analyzer (DEMO)",
            f"Spectrum Analyzer\n\n"
            f"Center: {self.center_freq/1e6:.2f}MHz\n"
            f"Span: {self.sample_rate/1e6:.2f}MHz\n"
            f"RBW: 10kHz\n\n"
            f"Peak: -45dBm @ 100.3MHz\n\n"
            "[ASCII Waterfall would be here]\n\n"
            "(Running in DEMO mode)\n"
            "(Connect HackRF/RTL-SDR for real spectrum)"
        )
    
    def record_samples(self):
        """Record IQ samples"""
        if not self.hardware_enabled:
            self.show_message(
                "Record IQ (DEMO)",
                "IQ sample recording requires SDR hardware.\n\n"
                "Connect HackRF One or RTL-SDR."
            )
            return
            
        duration = self.get_user_input("Duration (seconds):", default="5")
        
        try:
            duration = int(duration)
        except ValueError:
            self.show_error("Invalid duration")
            return
            
        try:
            # Configure
            self.sdr.setSampleRate(SOAPY_SDR_RX, 0, self.sample_rate)
            self.sdr.setFrequency(SOAPY_SDR_RX, 0, self.center_freq)
            self.sdr.setGain(SOAPY_SDR_RX, 0, self.gain)
            
            # Create stream
            rxStream = self.sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32)
            self.sdr.activateStream(rxStream)
            
            # Record
            samples_to_read = int(self.sample_rate * duration)
            all_samples = []
            
            self.show_message("Recording", f"Recording {duration}s...\nPlease wait.")
            
            while len(all_samples) < samples_to_read:
                buff = np.array([0]*4096, np.complex64)
                sr = self.sdr.readStream(rxStream, [buff], len(buff))
                
                if sr.ret > 0:
                    all_samples.extend(buff[:sr.ret])
            
            # Save to file
            filename = f"iq_{int(self.center_freq/1e6)}MHz_{int(time.time())}.npy"
            filepath = os.path.join(self.samples_dir, filename)
            
            np.save(filepath, np.array(all_samples))
            
            # Cleanup
            self.sdr.deactivateStream(rxStream)
            self.sdr.closeStream(rxStream)
            
            self.show_message(
                "Recording Complete",
                f"IQ samples saved!\n\n"
                f"File: {filename}\n"
                f"Samples: {len(all_samples)}\n"
                f"Duration: {duration}s\n"
                f"Center Freq: {self.center_freq/1e6:.2f}MHz"
            )
            
        except Exception as e:
            self.show_error(f"Recording error: {e}")
    
    def fm_demod(self):
        """FM demodulator"""
        self.show_message(
            "FM Demodulator",
            "FM Demodulator\n\n"
            "Demodulate FM broadcast signals.\n\n"
            "(Feature in development)\n"
            "Requires audio output integration."
        )
    
    def waterfall(self):
        """Waterfall display"""
        self.show_message(
            "Waterfall Display",
            "Waterfall Display\n\n"
            "Real-time frequency vs time display.\n\n"
            "(Feature in development)\n"
            "Requires continuous streaming and rendering."
        )
    
    def settings(self):
        """Device settings"""
        freq_input = self.get_user_input(
            "Center Frequency (MHz):",
            default=str(self.center_freq / 1e6)
        )
        
        try:
            freq_mhz = float(freq_input)
            self.center_freq = freq_mhz * 1e6
            
            self.show_message(
                "Settings",
                f"Frequency set to {freq_mhz}MHz\n\n"
                f"Sample Rate: {self.sample_rate/1e6}MHz\n"
                f"Gain: {self.gain}dB"
            )
        except ValueError:
            self.show_error("Invalid frequency")
    
    def show_status(self):
        """SDR status"""
        if self.hardware_enabled and self.sdr:
            try:
                status = (
                    "SDR Hardware Status\n\n"
                    f"Device: {self.device_type}\n"
                    f"Status: ENABLED\n\n"
                    f"Center Freq: {self.center_freq/1e6:.2f}MHz\n"
                    f"Sample Rate: {self.sample_rate/1e6:.2f}MSPS\n"
                    f"Gain: {self.gain}dB\n\n"
                    "Supported Modes:\n"
                    "- Spectrum Analyzer\n"
                    "- IQ Recording\n"
                    "- FM Demodulation (coming soon)\n"
                )
            except Exception as e:
                status = f"SDR Error: {e}"
        else:
            status = (
                "SDR Hardware Status\n\n"
                "Status: DISABLED (Demo Mode)\n\n"
                "To enable:\n"
                "1. Connect HackRF One or RTL-SDR via USB\n"
                "2. Install SoapySDR: apt install soapysdr-tools\n"
                "3. Set enabled=true in config/main.yaml\n"
                "4. Run as root for USB access\n"
            )
            
        self.show_message("SDR Status", status)
