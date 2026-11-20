from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.spi_clock import device_clock


class SpiClock(unittest.TestCase):
    def test_independent_endpoints_and_chip_limits(self):
        with TemporaryDirectory() as tmp:
            sysfs = Path(tmp)
            def rate(bus, cs, default, maximum):
                return device_clock(bus, cs, default, maximum, sysfs=sysfs)

            self.assertEqual(rate(7, 1, 5_000_000, 6_500_000), 5_000_000)
            for bus, cs, speed in ((3, 0, 6_000_000), (7, 0, 1_200_000), (7, 1, 12_000_000)):
                node = sysfs / f'class/spidev/spidev{bus}.{cs}/device/of_node'
                node.mkdir(parents=True)
                for prop in ('spi-max-frequency', 'armbian,spi-clock-request-hz'):
                    (node / prop).write_bytes(speed.to_bytes(4, 'big'))
            self.assertEqual(rate(3, 0, 5_000_000, 6_500_000), 6_000_000)
            self.assertEqual(rate(7, 0, 8_000_000, 8_000_000), 1_200_000)
            self.assertEqual(rate(7, 1, 1_000_000, 5_000_000), 5_000_000)
            (node/'armbian,spi-clock-request-hz').unlink()
            self.assertEqual(rate(7, 1, 1_000_000, 5_000_000), 1_000_000)
            (node/'spi-max-frequency').write_bytes((500_000).to_bytes(4, 'big'))
            self.assertEqual(rate(7, 1, 1_000_000, 5_000_000), 500_000)
            (node/'armbian,spi-clock-request-hz').write_bytes((900_000).to_bytes(4, 'big'))
            with self.assertRaises(ValueError):
                rate(7, 1, 1_000_000, 5_000_000)
            (node/'spi-max-frequency').write_bytes(b'')
            with self.assertRaises(ValueError):
                rate(7, 1, 1_000_000, 5_000_000)
