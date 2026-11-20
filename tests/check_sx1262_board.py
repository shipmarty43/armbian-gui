"""Board acceptance for an isolated Waveshare HAT. Run with the radio services stopped."""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.radio_lock import acquire_radio
from modules.lora.sx1262_driver import SX1262
import wiringpi_zero2w as gpio


class StandbyProbe(SX1262):
    """Exercise the installed driver's initialization with only standby/config SPI commands."""

    allowed = {0x80, 0xc0, 0x8a, 0x11, 0x98, 0x86, 0x9d, 0x95, 0x8e, 0x8b, 0x8f}

    def _transfer(self, packet):
        if packet[0] not in self.allowed:
            raise RuntimeError(f'Unexpected opcode in board test: 0x{packet[0]:02x}')
        return super()._transfer(packet)

    def read_configuration(self):
        status = self._transfer([0xc0, 0])[1]
        packet_type = self._transfer([0x11, 0, 0])[2]
        if (status >> 4) & 7 != 2 or packet_type != 1:
            raise RuntimeError(f'Unexpected readback: status={status:#04x}, packet_type={packet_type}')
        return status, packet_type


class RxTimerProbe(StandbyProbe):
    """Use the internal receive timeout as a real DIO1 stimulus."""
    allowed = StandbyProbe.allowed | {0x8c, 0x08, 0x02, 0x82, 0x12}

    def check_rx_irq(self, duration_ms):
        self._prepare_packet(255, self.TIMEOUT)
        if self._dio1.read():
            raise RuntimeError('DIO1 already asserted before RX')
        self._txen.write(1)
        try:
            # SX1262 timed RX counts ticks of 15.625 us.
            ticks = duration_ms * 64
            self.wait_busy()
            start = time.monotonic_ns()
            self.send_command(0x82, ticks.to_bytes(3, 'big'))
            event = self._dio1.wait_edge(1.0)
            flags = int.from_bytes(self._transfer([0x12, 0, 0, 0])[2:], 'big')
            if event is None or event.edge != 'rising' or not self._dio1.read() or flags != self.TIMEOUT:
                raise RuntimeError(f'Expected rising DIO1 and RX timeout: event={event}, flags={flags:#06x}')
            elapsed = (event.timestamp_ns - start) / 1e6
            self.send_command(0x02, flags.to_bytes(2, 'big'))
            self.wait_busy()
            if self._dio1.read():
                raise RuntimeError('DIO1 remained high after IRQ clear')
            print(f'RX {duration_ms} ms: DIO1 edge at {elapsed:.2f} ms, flags={flags:#06x}, cleared')
        finally:
            try:
                self.set_standby()
            finally:
                self._txen.write(0)


def main():
    pins = (12, 31, 36, 38)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rx-irq', action='store_true', help='Also test DIO1 with two timed RX windows')
    args = parser.parse_args()
    radio = RxTimerProbe() if args.rx_irq else StandbyProbe()
    for run in (1, 2):
        try:
            if not radio.initialize():
                raise RuntimeError(f'Standby initialization failed on run {run}')
            status, packet_type = radio.read_configuration()
            if not all(gpio.line_info(pin).used for pin in pins):
                raise RuntimeError('Missing GPIO ownership during standby')
            print(f'Run {run}: status={status:#04x}, packet_type={packet_type}, GPIO owned')
            if args.rx_irq:
                radio.check_rx_irq(50 if run == 1 else 150)
                radio.read_configuration()
        finally:
            radio.close()
        if any(gpio.line_info(pin).used for pin in pins):
            raise RuntimeError('Control pin still owned after close')
        with acquire_radio():
            print(f'Run {run}: GPIO free and process lock reacquired')


if __name__ == '__main__':
    main()
