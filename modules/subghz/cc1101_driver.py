"""
CC1101 Driver - драйвер для Sub-GHz трансивера CC1101
Поддержка: 300-928 MHz, ASK/OOK, FSK, GFSK, MSK модуляции
"""

import time
import logging
from typing import Optional, List, Tuple

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


# CC1101 Register addresses
class CC1101Registers:
    """CC1101 configuration registers"""
    IOCFG2 = 0x00  # GDO2 output pin configuration
    IOCFG1 = 0x01  # GDO1 output pin configuration
    IOCFG0 = 0x02  # GDO0 output pin configuration
    FIFOTHR = 0x03  # RX FIFO and TX FIFO thresholds
    SYNC1 = 0x04  # Sync word, high byte
    SYNC0 = 0x05  # Sync word, low byte
    PKTLEN = 0x06  # Packet length
    PKTCTRL1 = 0x07  # Packet automation control
    PKTCTRL0 = 0x08  # Packet automation control
    ADDR = 0x09  # Device address
    CHANNR = 0x0A  # Channel number
    FSCTRL1 = 0x0B  # Frequency synthesizer control
    FSCTRL0 = 0x0C  # Frequency synthesizer control
    FREQ2 = 0x0D  # Frequency control word, high byte
    FREQ1 = 0x0E  # Frequency control word, middle byte
    FREQ0 = 0x0F  # Frequency control word, low byte
    MDMCFG4 = 0x10  # Modem configuration
    MDMCFG3 = 0x11  # Modem configuration
    MDMCFG2 = 0x12  # Modem configuration
    MDMCFG1 = 0x13  # Modem configuration
    MDMCFG0 = 0x14  # Modem configuration
    DEVIATN = 0x15  # Modem deviation setting
    MCSM2 = 0x16  # Main Radio Control State Machine configuration
    MCSM1 = 0x17  # Main Radio Control State Machine configuration
    MCSM0 = 0x18  # Main Radio Control State Machine configuration
    FOCCFG = 0x19  # Frequency Offset Compensation configuration
    BSCFG = 0x1A  # Bit Synchronization configuration
    AGCCTRL2 = 0x1B  # AGC control
    AGCCTRL1 = 0x1C  # AGC control
    AGCCTRL0 = 0x1D  # AGC control
    FREND1 = 0x21  # Front end RX configuration
    FREND0 = 0x22  # Front end TX configuration
    FSCAL3 = 0x23  # Frequency synthesizer calibration
    FSCAL2 = 0x24  # Frequency synthesizer calibration
    FSCAL1 = 0x25  # Frequency synthesizer calibration
    FSCAL0 = 0x26  # Frequency synthesizer calibration
    TEST2 = 0x2C  # Various test settings
    TEST1 = 0x2D  # Various test settings
    TEST0 = 0x2E  # Various test settings
    PATABLE = 0x3E  # PA power output setting

    # Command strobes
    SRES = 0x30  # Reset chip
    SFSTXON = 0x31  # Enable and calibrate frequency synthesizer
    SXOFF = 0x32  # Turn off crystal oscillator
    SCAL = 0x33  # Calibrate frequency synthesizer
    SRX = 0x34  # Enable RX
    STX = 0x35  # Enable TX
    SIDLE = 0x36  # Exit RX / TX
    SWOR = 0x38  # Start automatic RX polling sequence
    SPWD = 0x39  # Enter power down mode when CSn goes high
    SFRX = 0x3A  # Flush the RX FIFO buffer
    SFTX = 0x3B  # Flush the TX FIFO buffer
    SWORRST = 0x3C  # Reset real time clock
    SNOP = 0x3D  # No operation

    # Status registers
    PARTNUM = 0xF0  # Part number
    VERSION = 0xF1  # Current version number
    FREQEST = 0xF2  # Frequency offset estimate
    LQI = 0xF3  # Demodulator estimate for link quality
    RSSI = 0xF4  # Received signal strength indication
    MARCSTATE = 0xF5  # Control state machine state
    PKTSTATUS = 0xF8  # Current GDOx status and packet status
    TXBYTES = 0xFA  # Underflow and number of bytes in TX FIFO
    RXBYTES = 0xFB  # Overflow and number of bytes in RX FIFO


class CC1101:
    """
    CC1101 Sub-GHz transceiver driver.

    Supports:
    - Frequency range: 300-348 MHz, 387-464 MHz, 779-928 MHz
    - Modulations: ASK/OOK, 2-FSK, GFSK, MSK
    - Data rates: 0.6 - 500 kBaud
    - RX/TX with FIFO
    """

    def __init__(self, spi_bus: int = 0, spi_device: int = 1, cs_pin: int = 24, gdo0_pin: int = 25):
        """
        Initialize CC1101 driver.

        Args:
            spi_bus: SPI bus number
            spi_device: SPI device number
            cs_pin: Chip select GPIO pin
            gdo0_pin: GDO0 GPIO pin (for interrupts)
        """
        self.logger = logging.getLogger("cyberdeck.cc1101")

        if not SPI_AVAILABLE:
            self.logger.error("spidev not available")
            self.enabled = False
            return

        self.spi_bus = spi_bus
        self.spi_device = spi_device
        self.cs_pin = cs_pin
        self.gdo0_pin = gdo0_pin

        self.spi = None
        self.enabled = False
        self.frequency = 433.92  # MHz
        self.modulation = "ASK_OOK"

    def initialize(self) -> bool:
        """
        Initialize CC1101 chip.

        Returns:
            bool: True if successful
        """
        try:
            # Open SPI
            self.spi = spidev.SpiDev()
            self.spi.open(self.spi_bus, self.spi_device)
            self.spi.max_speed_hz = 5000000  # 5 MHz
            self.spi.mode = 0

            # Reset chip
            self.reset()
            time.sleep(0.1)

            # Check chip version
            version = self.read_register(CC1101Registers.VERSION)
            if version == 0x00 or version == 0xFF:
                self.logger.error(f"CC1101 not responding (version: 0x{version:02X})")
                return False

            self.logger.info(f"CC1101 detected, version: 0x{version:02X}")

            # Configure chip
            self.configure_default()

            self.enabled = True
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize CC1101: {e}")
            return False

    def reset(self):
        """Reset CC1101 chip"""
        self.send_strobe(CC1101Registers.SRES)
        time.sleep(0.001)

    def send_strobe(self, strobe: int) -> int:
        """
        Send command strobe.

        Args:
            strobe: Strobe command

        Returns:
            int: Status byte
        """
        if self.spi is None:
            return 0

        result = self.spi.xfer2([strobe])
        return result[0]

    def read_register(self, reg: int) -> int:
        """
        Read single register.

        Args:
            reg: Register address

        Returns:
            int: Register value
        """
        if self.spi is None:
            return 0

        # Bit 7 = 1 for read, bit 6 = 0 for single byte
        result = self.spi.xfer2([reg | 0x80, 0x00])
        return result[1]

    def write_register(self, reg: int, value: int):
        """
        Write single register.

        Args:
            reg: Register address
            value: Value to write
        """
        if self.spi is None:
            return

        # Bit 7 = 0 for write
        self.spi.xfer2([reg & 0x7F, value])

    def read_burst(self, reg: int, length: int) -> List[int]:
        """
        Read multiple registers (burst mode).

        Args:
            reg: Starting register address
            length: Number of bytes to read

        Returns:
            List[int]: Register values
        """
        if self.spi is None:
            return []

        # Bit 7 = 1 for read, bit 6 = 1 for burst
        cmd = [reg | 0xC0] + [0x00] * length
        result = self.spi.xfer2(cmd)
        return result[1:]

    def write_burst(self, reg: int, data: List[int]):
        """
        Write multiple registers (burst mode).

        Args:
            reg: Starting register address
            data: Data to write
        """
        if self.spi is None:
            return

        # Bit 7 = 0 for write, bit 6 = 1 for burst
        cmd = [reg | 0x40] + data
        self.spi.xfer2(cmd)

    def configure_default(self):
        """Configure CC1101 with default settings for 433.92 MHz ASK/OOK"""

        # Basic configuration
        self.write_register(CC1101Registers.IOCFG2, 0x0D)  # GDO2 - Serial Clock
        self.write_register(CC1101Registers.IOCFG0, 0x06)  # GDO0 - Sync word sent/received

        self.write_register(CC1101Registers.PKTCTRL0, 0x32)  # Packet automation control
        self.write_register(CC1101Registers.FSCTRL1, 0x06)  # Frequency synthesizer control

        # Set frequency to 433.92 MHz
        self.set_frequency(433.92)

        # Modem configuration for ASK/OOK
        self.write_register(CC1101Registers.MDMCFG4, 0xC8)  # Modem configuration
        self.write_register(CC1101Registers.MDMCFG3, 0x93)  # Modem configuration
        self.write_register(CC1101Registers.MDMCFG2, 0x30)  # ASK/OOK, no preamble/sync
        self.write_register(CC1101Registers.MDMCFG1, 0x22)  # Modem configuration
        self.write_register(CC1101Registers.MDMCFG0, 0xF8)  # Modem configuration

        self.write_register(CC1101Registers.DEVIATN, 0x15)  # Modem deviation setting

        # AGC control
        self.write_register(CC1101Registers.AGCCTRL2, 0x03)
        self.write_register(CC1101Registers.AGCCTRL1, 0x00)
        self.write_register(CC1101Registers.AGCCTRL0, 0x91)

        # Front end configuration
        self.write_register(CC1101Registers.FREND1, 0x56)
        self.write_register(CC1101Registers.FREND0, 0x10)

        # Set TX power (max)
        self.write_register(CC1101Registers.PATABLE, 0xC0)

        self.logger.info("CC1101 configured for 433.92 MHz ASK/OOK")

    def set_frequency(self, freq_mhz: float):
        """
        Set carrier frequency.

        Args:
            freq_mhz: Frequency in MHz (300-928 MHz)
        """
        # Formula: FREQ = (freq_mhz * 2^16) / 26
        freq_reg = int((freq_mhz * 1000000.0 / 26000000.0) * 65536)

        freq2 = (freq_reg >> 16) & 0xFF
        freq1 = (freq_reg >> 8) & 0xFF
        freq0 = freq_reg & 0xFF

        self.write_register(CC1101Registers.FREQ2, freq2)
        self.write_register(CC1101Registers.FREQ1, freq1)
        self.write_register(CC1101Registers.FREQ0, freq0)

        self.frequency = freq_mhz
        self.logger.debug(f"Frequency set to {freq_mhz} MHz")

    def set_modulation(self, modulation: str):
        """
        Set modulation type.

        Args:
            modulation: "ASK_OOK", "2FSK", "GFSK", "MSK"
        """
        mdmcfg2 = self.read_register(CC1101Registers.MDMCFG2) & 0x8F

        if modulation == "ASK_OOK":
            mdmcfg2 |= 0x30
        elif modulation == "2FSK":
            mdmcfg2 |= 0x00
        elif modulation == "GFSK":
            mdmcfg2 |= 0x10
        elif modulation == "MSK":
            mdmcfg2 |= 0x70
        else:
            self.logger.warning(f"Unknown modulation: {modulation}")
            return

        self.write_register(CC1101Registers.MDMCFG2, mdmcfg2)
        self.modulation = modulation
        self.logger.info(f"Modulation set to {modulation}")

    def set_tx_power(self, power_dbm: int):
        """
        Set TX power.

        Args:
            power_dbm: Power in dBm (-30 to +10)
        """
        # PA table for different power levels
        pa_table = {
            -30: 0x00,
            -20: 0x0E,
            -15: 0x1E,
            -10: 0x27,
            -6: 0x38,
            0: 0x8E,
            5: 0x84,
            7: 0xCC,
            10: 0xC0
        }

        # Find closest power level
        closest = min(pa_table.keys(), key=lambda x: abs(x - power_dbm))
        self.write_register(CC1101Registers.PATABLE, pa_table[closest])
        self.logger.info(f"TX power set to {closest} dBm")

    def enter_rx_mode(self):
        """Enter RX mode"""
        self.send_strobe(CC1101Registers.SRX)
        self.logger.debug("Entered RX mode")

    def enter_tx_mode(self):
        """Enter TX mode"""
        self.send_strobe(CC1101Registers.STX)
        self.logger.debug("Entered TX mode")

    def enter_idle(self):
        """Enter IDLE mode"""
        self.send_strobe(CC1101Registers.SIDLE)
        self.logger.debug("Entered IDLE mode")

    def read_rssi(self) -> int:
        """
        Read RSSI value.

        Returns:
            int: RSSI in dBm
        """
        rssi_dec = self.read_register(CC1101Registers.RSSI)

        if rssi_dec >= 128:
            rssi_dbm = (rssi_dec - 256) // 2 - 74
        else:
            rssi_dbm = rssi_dec // 2 - 74

        return rssi_dbm

    def read_lqi(self) -> int:
        """
        Read Link Quality Indicator.

        Returns:
            int: LQI value (0-127)
        """
        lqi = self.read_register(CC1101Registers.LQI) & 0x7F
        return lqi

    def transmit(self, data: List[int]):
        """
        Transmit data.

        Args:
            data: Data bytes to transmit
        """
        if len(data) > 64:
            self.logger.warning("Data too long, truncating to 64 bytes")
            data = data[:64]

        # Enter IDLE
        self.enter_idle()

        # Flush TX FIFO
        self.send_strobe(CC1101Registers.SFTX)

        # Write data to TX FIFO
        self.write_burst(0x3F, data)  # 0x3F = TX FIFO

        # Enter TX mode
        self.enter_tx_mode()

        # Wait for transmission to complete
        time.sleep(0.01)

        # Return to IDLE
        self.enter_idle()

        self.logger.debug(f"Transmitted {len(data)} bytes")

    def receive(self, timeout: float = 1.0) -> Optional[List[int]]:
        """
        Receive data.

        Args:
            timeout: Timeout in seconds

        Returns:
            List[int]: Received bytes or None
        """
        # Enter RX mode
        self.enter_rx_mode()

        start_time = time.time()
        while (time.time() - start_time) < timeout:
            # Check RX FIFO
            rx_bytes = self.read_register(CC1101Registers.RXBYTES) & 0x7F

            if rx_bytes > 0:
                # Read data from RX FIFO
                data = self.read_burst(0x3F, rx_bytes)  # 0x3F = RX FIFO

                # Return to IDLE
                self.enter_idle()

                self.logger.debug(f"Received {len(data)} bytes")
                return data

            time.sleep(0.01)

        # Timeout - return to IDLE
        self.enter_idle()
        return None

    def close(self):
        """Close SPI connection"""
        if self.spi:
            self.enter_idle()
            self.spi.close()
            self.enabled = False
            self.logger.info("CC1101 closed")
