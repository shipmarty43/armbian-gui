"""
SX1262 LoRa Driver for Waveshare HAT
Supports Orange Pi GPIO with SPI interface
"""

import time
import logging
from typing import Optional, List

try:
    import spidev
    SPI_AVAILABLE = True
except ImportError:
    SPI_AVAILABLE = False

try:
    import OPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False


class SX1262:
    """
    SX1262 LoRa transceiver driver for Waveshare HAT.
    
    Compatible with:
    - Waveshare SX1262 LoRa HAT (433/868/915MHz)
    - Orange Pi GPIO
    - Raspberry Pi GPIO
    """
    
    # SX1262 Commands
    CMD_SET_SLEEP = 0x84
    CMD_SET_STANDBY = 0x80
    CMD_SET_FS = 0xC1
    CMD_SET_TX = 0x83
    CMD_SET_RX = 0x82
    CMD_SET_RF_FREQUENCY = 0x86
    CMD_SET_TX_PARAMS = 0x8E
    CMD_SET_MODULATION_PARAMS = 0x8B
    CMD_SET_PACKET_PARAMS = 0x8C
    CMD_WRITE_BUFFER = 0x0E
    CMD_READ_BUFFER = 0x1E
    CMD_GET_STATUS = 0xC0
    CMD_GET_RSSI = 0x15
    CMD_GET_PACKET_STATUS = 0x14
    
    def __init__(self, spi_bus: int = 0, spi_device: int = 0,
                 reset_pin: int = 18, busy_pin: int = 24, dio1_pin: int = 23):
        """
        Initialize SX1262 driver.
        
        Args:
            spi_bus: SPI bus number
            spi_device: SPI device number
            reset_pin: Reset GPIO pin
            busy_pin: BUSY GPIO pin
            dio1_pin: DIO1 GPIO pin
        """
        self.logger = logging.getLogger("cyberdeck.sx1262")
        
        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.reset_pin = reset_pin
        self.busy_pin = busy_pin
        self.dio1_pin = dio1_pin
        
        self.spi = None
        self.enabled = False
        
        # LoRa parameters
        self.frequency = 868000000  # 868 MHz
        self.bandwidth = 125000  # 125 kHz
        self.spreading_factor = 7
        self.coding_rate = 5
        self.tx_power = 22  # dBm
        
    def initialize(self) -> bool:
        """
        Initialize SX1262 chip.
        
        Returns:
            bool: True if successful
        """
        try:
            if not SPI_AVAILABLE or not GPIO_AVAILABLE:
                self.logger.error("SPI or GPIO not available")
                return False
                
            # Initialize GPIO
            GPIO.setmode(GPIO.CUSTOM)
            GPIO.setup(self.reset_pin, GPIO.OUT)
            GPIO.setup(self.busy_pin, GPIO.IN)
            GPIO.setup(self.dio1_pin, GPIO.IN)
            
            # Initialize SPI
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            self.spi.max_speed_hz = 2000000  # 2 MHz
            self.spi.mode = 0
            
            # Reset chip
            self.reset()
            time.sleep(0.1)
            
            # Configure for LoRa
            self.set_standby()
            self.set_packet_type_lora()
            self.set_rf_frequency(self.frequency)
            self.set_tx_params(self.tx_power, 0x04)
            self.configure_modulation()
            
            self.enabled = True
            self.logger.info(f"SX1262 initialized on SPI {self.spi_bus}.{self.spi_device}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize SX1262: {e}")
            return False
    
    def reset(self):
        """Hardware reset"""
        GPIO.output(self.reset_pin, GPIO.LOW)
        time.sleep(0.001)
        GPIO.output(self.reset_pin, GPIO.HIGH)
        time.sleep(0.005)
    
    def wait_busy(self, timeout: float = 1.0):
        """Wait for BUSY pin to go low"""
        start = time.time()
        while GPIO.input(self.busy_pin) == GPIO.HIGH:
            if (time.time() - start) > timeout:
                raise TimeoutError("SX1262 BUSY timeout")
            time.sleep(0.001)
    
    def send_command(self, cmd: int, data: List[int] = None):
        """Send command to SX1262"""
        self.wait_busy()
        
        if data is None:
            data = []
            
        packet = [cmd] + data
        self.spi.xfer2(packet)
        
        # Some commands need extra wait
        if cmd in [self.CMD_SET_TX, self.CMD_SET_RX]:
            time.sleep(0.001)
    
    def set_standby(self):
        """Set to standby mode"""
        self.send_command(self.CMD_SET_STANDBY, [0x00])
    
    def set_packet_type_lora(self):
        """Set packet type to LoRa"""
        self.send_command(0x8A, [0x01])  # Packet type: LoRa
    
    def set_rf_frequency(self, freq: int):
        """Set RF frequency in Hz"""
        freq_reg = int((freq * (2**25)) / 32000000)
        
        self.send_command(self.CMD_SET_RF_FREQUENCY, [
            (freq_reg >> 24) & 0xFF,
            (freq_reg >> 16) & 0xFF,
            (freq_reg >> 8) & 0xFF,
            freq_reg & 0xFF
        ])
        
        self.frequency = freq
        self.logger.debug(f"Frequency set to {freq / 1e6}MHz")
    
    def set_tx_params(self, power: int, ramp_time: int):
        """Set TX parameters"""
        self.send_command(self.CMD_SET_TX_PARAMS, [power, ramp_time])
    
    def configure_modulation(self):
        """Configure LoRa modulation parameters"""
        # Spreading Factor: 7-12
        # Bandwidth: 0x04 = 125kHz
        # Coding Rate: 1-4 (4/5 to 4/8)
        # Low Data Rate Optimize: 0x00
        
        sf_val = self.spreading_factor
        bw_val = 0x04  # 125 kHz
        cr_val = self.coding_rate - 4  # Convert to register value
        ldro = 0x00
        
        self.send_command(self.CMD_SET_MODULATION_PARAMS, [
            sf_val, bw_val, cr_val, ldro
        ])
    
    def transmit(self, data: bytes):
        """Transmit data"""
        if not self.enabled:
            return
            
        try:
            # Write to buffer
            self.wait_busy()
            packet = [self.CMD_WRITE_BUFFER, 0x00] + list(data)
            self.spi.xfer2(packet)
            
            # Set packet params
            self.send_command(self.CMD_SET_PACKET_PARAMS, [
                0x00, 0x00,  # Preamble length
                0x00,  # Header type
                len(data),  # Payload length
                0x01, 0x00, 0x00  # CRC, invert IQ, etc
            ])
            
            # Transmit
            self.send_command(self.CMD_SET_TX, [0x00, 0x00, 0x00])
            
            # Wait for TX done
            time.sleep(0.5)
            
            self.logger.debug(f"Transmitted {len(data)} bytes")
            
        except Exception as e:
            self.logger.error(f"Transmit error: {e}")
    
    def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        """Receive data"""
        if not self.enabled:
            return None
            
        try:
            # Enter RX mode
            self.send_command(self.CMD_SET_RX, [0xFF, 0xFF, 0xFF])
            
            # Wait for packet
            start = time.time()
            while (time.time() - start) < timeout:
                # Check DIO1 for RX done
                if GPIO.input(self.dio1_pin) == GPIO.HIGH:
                    # Read buffer
                    self.wait_busy()
                    read_cmd = [self.CMD_READ_BUFFER, 0x00, 0x00] + [0x00] * 255
                    result = self.spi.xfer2(read_cmd)
                    
                    # Parse received data (skip first 3 bytes)
                    rx_data = bytes(result[3:])
                    
                    # Back to standby
                    self.set_standby()
                    
                    return rx_data
                    
                time.sleep(0.01)
            
            # Timeout - back to standby
            self.set_standby()
            return None
            
        except Exception as e:
            self.logger.error(f"Receive error: {e}")
            self.set_standby()
            return None
    
    def get_rssi(self) -> int:
        """Get RSSI value"""
        self.wait_busy()
        result = self.spi.xfer2([self.CMD_GET_RSSI, 0x00, 0x00])
        rssi_raw = result[2]
        rssi_dbm = -rssi_raw // 2
        return rssi_dbm
    
    def close(self):
        """Close SPI"""
        if self.spi:
            self.set_standby()
            self.spi.close()
            self.enabled = False
            self.logger.info("SX1262 closed")
