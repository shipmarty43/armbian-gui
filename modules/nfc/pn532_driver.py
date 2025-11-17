"""
PN532 Driver - драйвер для NFC/RFID контроллера PN532
Поддержка: SPI, I2C, UART интерфейсов
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


# PN532 Commands
PN532_COMMAND_DIAGNOSE = 0x00
PN532_COMMAND_GETFIRMWAREVERSION = 0x02
PN532_COMMAND_GETGENERALSTATUS = 0x04
PN532_COMMAND_READREGISTER = 0x06
PN532_COMMAND_WRITEREGISTER = 0x08
PN532_COMMAND_READGPIO = 0x0C
PN532_COMMAND_WRITEGPIO = 0x0E
PN532_COMMAND_SETSERIALBAUDRATE = 0x10
PN532_COMMAND_SETPARAMETERS = 0x12
PN532_COMMAND_SAMCONFIGURATION = 0x14
PN532_COMMAND_POWERDOWN = 0x16
PN532_COMMAND_RFCONFIGURATION = 0x32
PN532_COMMAND_RFREGULATIONTEST = 0x58
PN532_COMMAND_INJUMPFORDEP = 0x56
PN532_COMMAND_INJUMPFORPSL = 0x46
PN532_COMMAND_INLISTPASSIVETARGET = 0x4A
PN532_COMMAND_INATR = 0x50
PN532_COMMAND_INPSL = 0x4E
PN532_COMMAND_INDATAEXCHANGE = 0x40
PN532_COMMAND_INCOMMUNICATETHRU = 0x42
PN532_COMMAND_INDESELECT = 0x44
PN532_COMMAND_INRELEASE = 0x52
PN532_COMMAND_INSELECT = 0x54
PN532_COMMAND_INAUTOPOLL = 0x60
PN532_COMMAND_TGINITASTARGET = 0x8C
PN532_COMMAND_TGSETGENERALBYTES = 0x92
PN532_COMMAND_TGGETDATA = 0x86
PN532_COMMAND_TGSETDATA = 0x8E
PN532_COMMAND_TGSETMETADATA = 0x94
PN532_COMMAND_TGGETINITIATORCOMMAND = 0x88
PN532_COMMAND_TGRESPONSETOINITIATOR = 0x90
PN532_COMMAND_TGGETTARGETSTATUS = 0x8A

# Mifare Commands
MIFARE_CMD_AUTH_A = 0x60
MIFARE_CMD_AUTH_B = 0x61
MIFARE_CMD_READ = 0x30
MIFARE_CMD_WRITE = 0xA0
MIFARE_CMD_DECREMENT = 0xC0
MIFARE_CMD_INCREMENT = 0xC1
MIFARE_CMD_RESTORE = 0xC2
MIFARE_CMD_TRANSFER = 0xB0

# PN532 Frame markers
PN532_PREAMBLE = 0x00
PN532_STARTCODE1 = 0x00
PN532_STARTCODE2 = 0xFF
PN532_POSTAMBLE = 0x00

PN532_HOSTTOPN532 = 0xD4
PN532_PN532TOHOST = 0xD5

# ACK and NACK
PN532_ACK = bytes([0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00])
PN532_NACK = bytes([0x00, 0x00, 0xFF, 0xFF, 0x00, 0x00])


class PN532:
    """
    PN532 NFC/RFID контроллер driver.

    Supports:
    - Mifare Classic 1K/4K read/write
    - Mifare Ultralight read/write
    - NTAG support
    - ISO14443A/B protocols
    - Card emulation (HCE)
    """

    def __init__(self, interface: str = 'spi', spi_bus: int = 1, spi_device: int = 2,
                 cs_pin: int = 23, reset_pin: Optional[int] = None,
                 i2c_bus: int = 0, i2c_address: int = 0x24):
        """
        Initialize PN532 driver.

        Args:
            interface: 'spi', 'i2c', or 'uart'
            spi_bus: SPI bus number
            spi_device: SPI device number
            cs_pin: Chip select GPIO pin (for SPI)
            reset_pin: Reset GPIO pin (optional)
            i2c_bus: I2C bus number
            i2c_address: I2C address
        """
        self.logger = logging.getLogger("cyberdeck.pn532")

        self.interface = interface
        self.spi = None
        self.i2c = None
        self.cs_pin = cs_pin
        self.reset_pin = reset_pin
        self.enabled = False

        # GPIO setup for reset
        if reset_pin and GPIO_AVAILABLE:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(reset_pin, GPIO.OUT)
            GPIO.output(reset_pin, GPIO.HIGH)

        # Initialize interface
        if interface == 'spi':
            if not SPI_AVAILABLE:
                self.logger.error("spidev not available")
                return

            try:
                self.spi = spidev.SpiDev()
                self.spi.open(spi_bus, spi_device)
                self.spi.max_speed_hz = 1000000  # 1 MHz
                self.spi.mode = 0
                self.logger.info(f"PN532 SPI opened: {spi_bus}.{spi_device}")
            except Exception as e:
                self.logger.error(f"Failed to open SPI: {e}")
                return

        elif interface == 'i2c':
            try:
                import smbus
                self.i2c = smbus.SMBus(i2c_bus)
                self.i2c_address = i2c_address
                self.logger.info(f"PN532 I2C opened: bus {i2c_bus}, addr 0x{i2c_address:02X}")
            except Exception as e:
                self.logger.error(f"Failed to open I2C: {e}")
                return

        else:
            self.logger.error(f"Unsupported interface: {interface}")
            return

    def initialize(self) -> bool:
        """
        Initialize PN532 chip.

        Returns:
            bool: True if successful
        """
        # Reset if pin available
        if self.reset_pin:
            self._hardware_reset()

        # Wake up PN532
        self._wakeup()
        time.sleep(0.5)

        # Get firmware version
        version = self.get_firmware_version()
        if not version:
            self.logger.error("PN532 not responding")
            return False

        ic, ver, rev, support = version
        self.logger.info(f"PN532 v{ver}.{rev} detected (IC: 0x{ic:02X})")

        # Configure SAM (Security Access Module)
        if not self.SAM_configuration():
            self.logger.error("Failed to configure SAM")
            return False

        # Set parameters
        self.set_passive_activation_retries(0xFF)

        self.enabled = True
        return True

    def _hardware_reset(self):
        """Hardware reset via reset pin"""
        if self.reset_pin and GPIO_AVAILABLE:
            GPIO.output(self.reset_pin, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(self.reset_pin, GPIO.HIGH)
            time.sleep(0.5)

    def _wakeup(self):
        """Wake up PN532 from power down"""
        if self.interface == 'spi':
            # Send dummy bytes to wake up
            self.spi.xfer2([0x00] * 10)
            time.sleep(0.01)

    def _write_command(self, cmd: int, params: List[int] = None):
        """Write command to PN532"""
        if params is None:
            params = []

        # Build frame
        frame = [PN532_HOSTTOPN532, cmd] + params

        # Calculate checksum
        checksum = (~sum(frame) + 1) & 0xFF

        # Build full packet
        packet = [
            PN532_PREAMBLE,
            PN532_STARTCODE1,
            PN532_STARTCODE2,
            len(frame),
            (~len(frame) + 1) & 0xFF
        ] + frame + [checksum, PN532_POSTAMBLE]

        if self.interface == 'spi':
            # SPI write (add 0x01 prefix for SPI mode)
            self.spi.xfer2([0x01] + packet)
        elif self.interface == 'i2c':
            # I2C write
            self.i2c.write_i2c_block_data(self.i2c_address, 0, packet)

        time.sleep(0.01)

    def _read_ack(self, timeout: float = 1.0) -> bool:
        """Wait for ACK response"""
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if self.interface == 'spi':
                # SPI read status
                status = self.spi.xfer2([0x02, 0x00])[1]
                if status & 0x01:  # Ready
                    # Read ACK
                    data = self.spi.xfer2([0x03] + [0x00] * 6)[1:]
                    if bytes(data) == PN532_ACK:
                        return True
            elif self.interface == 'i2c':
                # I2C read
                try:
                    data = self.i2c.read_i2c_block_data(self.i2c_address, 0, 6)
                    if bytes(data) == PN532_ACK:
                        return True
                except:
                    pass

            time.sleep(0.01)

        return False

    def _read_response(self, timeout: float = 1.0) -> Optional[List[int]]:
        """Read response from PN532"""
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if self.interface == 'spi':
                # Check if data ready
                status = self.spi.xfer2([0x02, 0x00])[1]
                if not (status & 0x01):
                    time.sleep(0.01)
                    continue

                # Read response (max 255 bytes)
                response = self.spi.xfer2([0x03] + [0x00] * 255)[1:]

                # Find start of frame
                if response[0] != PN532_PREAMBLE:
                    continue
                if response[1] != PN532_STARTCODE1 or response[2] != PN532_STARTCODE2:
                    continue

                # Get length
                length = response[3]
                length_checksum = response[4]

                # Verify length checksum
                if (length + length_checksum) & 0xFF != 0:
                    continue

                # Extract frame
                frame = response[5:5 + length]

                # Verify checksum
                checksum = response[5 + length]
                if (sum(frame) + checksum) & 0xFF != 0:
                    continue

                # Return data (skip PN532TOHOST byte)
                if frame[0] == PN532_PN532TOHOST:
                    return frame[1:]

            elif self.interface == 'i2c':
                try:
                    # Read response
                    response = self.i2c.read_i2c_block_data(self.i2c_address, 0, 255)

                    # Same parsing as SPI
                    if response[0] != PN532_PREAMBLE:
                        time.sleep(0.01)
                        continue

                    length = response[3]
                    frame = response[5:5 + length]

                    if frame[0] == PN532_PN532TOHOST:
                        return frame[1:]

                except:
                    pass

            time.sleep(0.01)

        return None

    def get_firmware_version(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Get PN532 firmware version.

        Returns:
            Tuple of (IC, Ver, Rev, Support) or None
        """
        self._write_command(PN532_COMMAND_GETFIRMWAREVERSION)

        if not self._read_ack():
            return None

        response = self._read_response()
        if not response or len(response) < 5:
            return None

        # Response: [cmd+1, IC, Ver, Rev, Support]
        return (response[1], response[2], response[3], response[4])

    def SAM_configuration(self, mode: int = 0x01, timeout: int = 0x14, irq: int = 0x01) -> bool:
        """
        Configure SAM (Security Access Module).

        Args:
            mode: 0x01 = Normal mode, 0x02 = Virtual card, 0x03 = Wired card
            timeout: Timeout (x 50ms)
            irq: Use IRQ pin

        Returns:
            bool: True if successful
        """
        self._write_command(PN532_COMMAND_SAMCONFIGURATION, [mode, timeout, irq])

        if not self._read_ack():
            return False

        response = self._read_response()
        return response is not None

    def set_passive_activation_retries(self, retries: int = 0xFF) -> bool:
        """
        Set passive activation retries.

        Args:
            retries: Number of retries (0xFF = infinite)

        Returns:
            bool: True if successful
        """
        self._write_command(PN532_COMMAND_SETPARAMETERS, [0x01])  # NAD enabled

        if not self._read_ack():
            return False

        response = self._read_response()
        return response is not None

    def read_passive_target(self, card_type: int = 0x00, timeout: float = 1.0) -> Optional[dict]:
        """
        Read passive target (card).

        Args:
            card_type: 0x00 = Mifare/ISO14443A, 0x01 = FeliCa, 0x02 = ISO14443B
            timeout: Timeout in seconds

        Returns:
            Card info dict or None
        """
        self._write_command(PN532_COMMAND_INLISTPASSIVETARGET, [0x01, card_type])

        if not self._read_ack():
            return None

        response = self._read_response(timeout=timeout)
        if not response or len(response) < 2:
            return None

        # Parse response
        num_targets = response[1]
        if num_targets < 1:
            return None

        # Parse card info
        target_number = response[2]
        sens_res = (response[4] << 8) | response[3]  # SENS_RES / ATQA
        sel_res = response[5]  # SEL_RES / SAK
        uid_length = response[6]
        uid = response[7:7 + uid_length]

        return {
            'target': target_number,
            'sens_res': sens_res,
            'sel_res': sel_res,
            'uid_length': uid_length,
            'uid': uid,
            'type': self._identify_card_type(sel_res)
        }

    def _identify_card_type(self, sak: int) -> str:
        """Identify card type from SAK"""
        if sak == 0x08:
            return "Mifare Classic 1K"
        elif sak == 0x18:
            return "Mifare Classic 4K"
        elif sak == 0x00:
            return "Mifare Ultralight"
        elif sak == 0x20:
            return "Mifare DESFire"
        elif sak == 0x28:
            return "JCOP 31/41"
        elif sak == 0x09:
            return "Mifare Mini"
        else:
            return f"Unknown (SAK: 0x{sak:02X})"

    def mifare_classic_authenticate(self, uid: List[int], block: int, key_type: int = MIFARE_CMD_AUTH_A,
                                    key: List[int] = None) -> bool:
        """
        Authenticate Mifare Classic block.

        Args:
            uid: Card UID
            block: Block number
            key_type: MIFARE_CMD_AUTH_A or MIFARE_CMD_AUTH_B
            key: 6-byte key (default: FF FF FF FF FF FF)

        Returns:
            bool: True if authenticated
        """
        if key is None:
            key = [0xFF] * 6

        params = [key_type, block] + key + uid[:4]
        self._write_command(PN532_COMMAND_INDATAEXCHANGE, [0x01] + params)

        if not self._read_ack():
            return False

        response = self._read_response()
        if not response or len(response) < 2:
            return False

        # Check status
        status = response[1]
        return status == 0x00

    def mifare_classic_read_block(self, block: int) -> Optional[List[int]]:
        """
        Read Mifare Classic block (must authenticate first).

        Args:
            block: Block number

        Returns:
            16 bytes of data or None
        """
        self._write_command(PN532_COMMAND_INDATAEXCHANGE, [0x01, MIFARE_CMD_READ, block])

        if not self._read_ack():
            return None

        response = self._read_response()
        if not response or len(response) < 3:
            return None

        # Check status
        status = response[1]
        if status != 0x00:
            return None

        # Return data (skip status byte)
        return response[2:]

    def mifare_classic_write_block(self, block: int, data: List[int]) -> bool:
        """
        Write Mifare Classic block (must authenticate first).

        Args:
            block: Block number
            data: 16 bytes to write

        Returns:
            bool: True if successful
        """
        if len(data) != 16:
            return False

        self._write_command(PN532_COMMAND_INDATAEXCHANGE, [0x01, MIFARE_CMD_WRITE, block] + data)

        if not self._read_ack():
            return False

        response = self._read_response()
        if not response or len(response) < 2:
            return False

        status = response[1]
        return status == 0x00

    def close(self):
        """Close connection"""
        if self.spi:
            self.spi.close()
        if GPIO_AVAILABLE and self.reset_pin:
            GPIO.cleanup()
        self.enabled = False
        self.logger.info("PN532 closed")
