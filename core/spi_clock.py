"""Resolve the Linux spidev client's requested clock for one SPI peripheral."""
from pathlib import Path


def device_clock(bus, cs, default_hz, chip_max_hz, *, sysfs=Path('/sys')):
    node = sysfs / f'class/spidev/spidev{bus}.{cs}/device/of_node'

    def cell(name):
        try:
            data = (node / name).read_bytes()
        except FileNotFoundError:
            return None
        if len(data) != 4 or not int.from_bytes(data, 'big'):
            raise ValueError(f'Invalid SPI device-tree property {name}')
        return int.from_bytes(data, 'big')

    limit = cell('spi-max-frequency')
    selected = cell('armbian,spi-clock-request-hz')
    if selected is not None and (selected != limit or selected < 3000):
        raise ValueError('Configured SPI request differs from the device-tree clock')
    return min(selected or default_hz, chip_max_hz, limit or default_hz)
