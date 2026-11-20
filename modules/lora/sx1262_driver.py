"""Waveshare SX1262 SPI/GNSS HAT on the Orange Pi Zero 2W."""
import errno
import logging
import math
import threading
import time

try:
    import spidev
except ImportError:
    spidev = None

try:
    import wiringpi_zero2w as gpio
except ImportError:
    gpio = None

from core.hardware_config import LORA_PINS, lora_settings
from core.radio_lock import acquire_radio
from core.resources import close_attributes
from core.sx1262_spi import find_spi, selected_spi_hz


class SX1262:
    """Physical header numbering. Linux SPI owns CS throughout every transfer."""

    TX_DONE = 0x0001
    RX_DONE = 0x0002
    RX_ERRORS = 0x0060  # header and payload CRC errors
    TIMEOUT = 0x0200

    def __init__(self, spi_bus='auto', spi_device=0, reset_pin=LORA_PINS['reset_pin'],
                 busy_pin=LORA_PINS['busy_pin'], dio1_pin=LORA_PINS['dio1_pin'], *,
                 cs_pin=LORA_PINS['cs_pin'], txen_pin=LORA_PINS['txen_pin'],
                 frequency_hz=433_920_000, bandwidth_hz=125000, spreading_factor=7,
                 coding_rate=5, tx_power=14, preamble_length=8):
        if type(bandwidth_hz) is not int or bandwidth_hz not in (125000, 250000, 500000):
            raise ValueError('Unsupported LoRa bandwidth in Hz')
        if type(frequency_hz) is not int or not 410_000_000 <= frequency_hz <= 490_000_000:
            raise ValueError('frequency_hz must be an integer in the HAT band')
        # Direct callers receive the same preflight as the TUI.
        lora_settings(dict(spi_bus=spi_bus, spi_device=spi_device, cs_pin=cs_pin,
                           reset_pin=reset_pin, busy_pin=busy_pin, dio1_pin=dio1_pin,
                           txen_pin=txen_pin, frequency=frequency_hz / 1e6, bandwidth=bandwidth_hz // 1000,
                           spreading_factor=spreading_factor, coding_rate=coding_rate,
                           tx_power=tx_power, preamble_length=preamble_length))
        self.logger = logging.getLogger("cyberdeck.sx1262")
        self.spi_bus, self.spi_device = spi_bus, spi_device
        self.reset_pin, self.busy_pin = reset_pin, busy_pin
        self.dio1_pin, self.txen_pin = dio1_pin, txen_pin
        self._owner = self._reset = self._busy = self._dio1 = self._txen = self.spi = None
        self.enabled = False
        self._lock = threading.RLock()
        self.frequency = frequency_hz
        self.bandwidth = bandwidth_hz
        self.spreading_factor = spreading_factor
        self.coding_rate = coding_rate
        self.tx_power = tx_power
        self.preamble_length = preamble_length

    def initialize(self):
        with self._lock:
            if self.enabled:
                return True
            try:
                if gpio is None or spidev is None:
                    raise RuntimeError('SX1262 requires wiringpi-zero2w, its native library and spidev')
                self._owner = acquire_radio()
                bus, device = find_spi(self.spi_bus, self.spi_device)
                spi_hz = selected_spi_hz(bus, device)
                # Claim every control line before pulsing RESET or configuring SPI.
                self._busy = gpio.request_input(self.busy_pin)
                self._dio1 = gpio.request_input(self.dio1_pin, edge='rising')
                self._txen = gpio.request_output(self.txen_pin, initial=0)
                self._reset = gpio.request_output(self.reset_pin, initial=1)
                self.spi = spidev.SpiDev()
                self.spi.open(bus, device)
                self.spi.mode = 0
                self.spi.max_speed_hz = spi_hz
                self.reset()
                self.set_standby()
                self._check_standby()
                self.set_packet_type_lora()
                if self._transfer([0x11, 0, 0])[2] != 1:
                    raise OSError(errno.EIO, 'SX1262 did not accept the LoRa packet type')
                self.set_rf_frequency(self.frequency)
                self.send_command(0x9D, [1])  # DIO2 controls the on-board RF switch.
                self.send_command(0x95, [4, 7, 0, 1])  # SX1262 high-power PA configuration
                self.set_tx_params(self.tx_power, 0x04)
                self.configure_modulation()
                self.send_command(0x8F, [0, 0])  # FIFO base addresses for TX and RX
                self._check_standby()
                self.enabled = True
                self.logger.info('SX1262 in standby on spidev%d.%d', bus, device)
                return True
            except (OSError, RuntimeError, ValueError) as exc:
                self.logger.error('SX1262 initialization failed: %s', exc)
                return False
            finally:
                if not self.enabled:
                    self.close()

    def reset(self):
        self._reset.write(0)
        try:
            time.sleep(.001)
        finally:
            self._reset.write(1)
        time.sleep(.005)

    def wait_busy(self, timeout=1.0):
        deadline = time.monotonic() + timeout
        while self._busy.read():
            if time.monotonic() >= deadline:
                raise TimeoutError('SX1262 BUSY stayed high')
            time.sleep(.001)

    def _transfer(self, packet):
        self.wait_busy()
        return self.spi.xfer2(packet)

    def send_command(self, cmd, data=()):
        self._transfer([cmd, *data])

    def set_standby(self):
        self.send_command(0x80, [0])

    def _check_standby(self):
        status = self._transfer([0xC0, 0])[1]
        if ((status >> 4) & 7) != 2 or ((status >> 1) & 7) in (3, 4, 5):
            raise OSError(errno.EIO, f'Invalid SX1262 standby status 0x{status:02x}')

    def set_packet_type_lora(self):
        self.send_command(0x8A, [1])

    def set_rf_frequency(self, freq):
        if type(freq) is not int or not 410_000_000 <= freq <= 490_000_000:
            raise ValueError('Frequency outside the 433/470 MHz HAT band')
        # Waveshare uses the 430/440 and 470/510 MHz image calibration pairs.
        self.send_command(0x98, [0x6b, 0x6f] if freq < 446_000_000 else [0x75, 0x81])
        word = round(freq * (1 << 25) / 32_000_000)
        self.send_command(0x86, word.to_bytes(4, 'big'))
        self.frequency = freq

    def set_tx_params(self, power, ramp_time):
        self.send_command(0x8E, [power & 0xff, ramp_time])

    def configure_modulation(self):
        bandwidth_code = {125000: 4, 250000: 5, 500000: 6}[self.bandwidth]
        ldro = int(2 ** self.spreading_factor / self.bandwidth >= .016)
        self.send_command(0x8B, [self.spreading_factor, bandwidth_code, self.coding_rate - 4, ldro])

    def _prepare_packet(self, length, mask):
        self.set_standby()
        self.send_command(0x8C, [*self.preamble_length.to_bytes(2, 'big'), 0, length, 1, 0])
        raw = mask.to_bytes(2, 'big')
        self.send_command(0x08, [*raw, *raw, 0, 0, 0, 0])  # global IRQ mask and DIO1
        self.send_command(0x02, [0xff, 0xff])
        # A level read may have completed the previous operation before its
        # queued rising edge was consumed. Drain it while the radio is idle.
        self.wait_busy()
        for _ in range(64):
            if self._dio1.wait_edge(0) is None:
                break
        else:
            raise OSError(errno.EIO, 'DIO1 did not settle in standby')

    def _wait_irq(self, done, timeout):
        deadline = time.monotonic() + timeout
        while True:
            # Level catches an IRQ already asserted before we entered the wait.
            if not self._dio1.read():
                remaining = max(0, deadline - time.monotonic())
                if self._dio1.wait_edge(remaining) is None:
                    return False
            flags = int.from_bytes(self._transfer([0x12, 0, 0, 0])[2:], 'big')
            if flags:
                self.send_command(0x02, flags.to_bytes(2, 'big'))
            if flags & self.RX_ERRORS:
                raise OSError(errno.EBADMSG, 'SX1262 header/CRC error')
            if flags & self.TIMEOUT:
                return False
            if flags & done:
                return True
            if time.monotonic() >= deadline:
                return False

    def transmit(self, data):
        with self._lock:
            if not self.enabled:
                raise RuntimeError('SX1262 is closed')
            if not 1 <= len(data) <= 255:
                raise ValueError('LoRa payload must contain 1..255 bytes')
            self._prepare_packet(len(data), self.TX_DONE | self.TIMEOUT)
            self.send_command(0x0E, [0, *data])
            try:
                self._txen.write(0)  # Waveshare DIO4/TXEN is low during TX.
                self.send_command(0x83, [0, 0, 0])
                # Upper bound for a 255-byte LoRa packet at SF12/BW125 in this UI.
                timeout = 20 + self.preamble_length * (2 ** self.spreading_factor / self.bandwidth)
                if not self._wait_irq(self.TX_DONE, timeout):
                    raise TimeoutError('SX1262 TX_DONE timed out')
            finally:
                try:
                    self.set_standby()
                finally:
                    self._txen.write(0)

    def receive(self, timeout=1.0):
        with self._lock:
            if not self.enabled:
                raise RuntimeError('SX1262 is closed')
            if not math.isfinite(timeout) or timeout < 0:
                raise ValueError('RX timeout must be finite and non-negative')
            self._prepare_packet(255, self.RX_DONE | self.RX_ERRORS | self.TIMEOUT)
            try:
                self._txen.write(1)  # High selects RX in the manufacturer demo.
                self.send_command(0x82, [0, 0, 0])  # Single packet, host deadline.
                if not self._wait_irq(self.RX_DONE, timeout):
                    return None
                length, offset = self._transfer([0x13, 0, 0, 0])[2:]
                return bytes(self._transfer([0x1E, offset, 0] + [0] * length)[3:])
            finally:
                try:
                    self.set_standby()
                finally:
                    self._txen.write(0)

    def get_rssi(self):
        with self._lock:
            if not self.enabled:
                raise RuntimeError('SX1262 is closed')
            # Packet RSSI from GetPacketStatus remains available in standby.
            return -self._transfer([0x14, 0, 0, 0, 0])[2] / 2

    def close(self):
        with self._lock:
            try:
                if self.enabled:
                    self.set_standby()
            except OSError:
                self.logger.exception('SX1262 standby failed')
            finally:
                self.enabled = False
                close_attributes(self, 'spi', '_reset', '_txen', '_dio1', '_busy', '_owner')
