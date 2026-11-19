"""Resolve the direct-mounted Zero 2W HAT's kernel-managed SPI endpoint."""
from pathlib import Path
import re
import struct


def find_spi(bus, device, *, sysfs=Path('/sys')):
    """Match the live SPI controller, radio DT node and active-low PI3 CS."""
    dt = sysfs / 'firmware/devicetree/base/soc'
    controller = (dt / 'spi@5011000').resolve()
    matches = []
    for entry in (sysfs / 'class/spidev').glob('spidev*.*'):
        name = re.fullmatch(r'spidev(\d+)\.(\d+)', entry.name)
        if not name:
            continue
        number, select = map(int, name.groups())
        if select != device or bus not in ('auto', number):
            continue
        node = (entry / 'device/of_node').resolve()
        if node.parent != controller:
            continue
        if b'semtech,sx1262' not in (node / 'compatible').read_bytes().split(b'\0'):
            continue
        if (node / 'reg').read_bytes() != struct.pack('>I', select):
            continue
        # This HAT overlay assigns the only CS descriptor to logical CS0.
        pio = (dt / 'pinctrl@300b000/phandle').read_bytes()
        if (select != 0 or len(pio) != 4 or (node / 'spi-cs-high').exists() or
                (controller / 'cs-gpios').read_bytes() != pio + struct.pack('>III', 8, 3, 1)):
            raise ValueError('SX1262 requires kernel CS0 on physical 40 (PI3, active low)')
        group = dt / 'pinctrl@300b000/spi1-pins'
        if ((controller / 'pinctrl-0').read_bytes() != (group / 'phandle').read_bytes()
                or (group / 'function').read_bytes() != b'spi1\0'
                or set((group / 'pins').read_bytes().rstrip(b'\0').split(b'\0')) != {b'PH6', b'PH7', b'PH8'}):
            raise ValueError('Unexpected pinmux on the SX1262 SPI bus')
        for peer in controller.iterdir():
            if peer == node or not (peer / 'reg').is_file():
                continue
            if (peer / 'status').is_file() and (peer / 'status').read_bytes().rstrip(b'\0') not in (b'ok', b'okay'):
                continue
            if (peer / 'reg').read_bytes() == struct.pack('>I', select):
                raise ValueError('Two enabled Device Tree nodes share the SX1262 chip select')
        matches.append((number, select))
    if len(matches) != 1:
        raise OSError('Expected one SPI1 SX1262 endpoint; check opi-zero2w-sx1262 and spi_bus')
    return matches[0]
