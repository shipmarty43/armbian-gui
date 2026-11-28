"""Resolve the direct-mounted Zero 2W HAT's kernel-managed SPI endpoint."""
from pathlib import Path
import re
import struct


def enabled(node):
    path = node/"status"
    return not path.exists() or path.read_bytes().rstrip(b"\0") in (b"ok",b"okay")


def check_pinmux(ctrl, pio):
    group = pio/"spi1-pins"
    if ((ctrl/'pinctrl-0').read_bytes() != (group/'phandle').read_bytes() or
            (group/'function').read_bytes() != b'spi1\0' or
            set((group/'pins').read_bytes().rstrip(b'\0').split(b'\0')) != {b'PH6',b'PH7',b'PH8'}):
        raise ValueError("Unexpected SPI1 pinmux")


def header_endpoint(bus, cs, compatible, *, sysfs=Path('/sys')):
    """Discover a typed client by OF controller and logical CS, even if Linux renumbers the bus."""
    ctrl = sysfs/'firmware/devicetree/base/soc/spi@5011000'
    found = []
    for entry in (sysfs/'class/spidev').glob(f'spidev*.{cs}'):
        m = re.fullmatch(r'spidev([0-9]+)\.([0-9]+)', entry.name)
        node = (entry/'device/of_node').resolve()
        if not m or node.parent != ctrl.resolve() or (node/'reg').read_bytes() != struct.pack('>I',cs):
            continue
        if not enabled(ctrl) or not enabled(node) or bus not in ('auto', int(m[1])):
            continue
        if compatible.encode() not in (node/'compatible').read_bytes().split(b'\0'):
            continue
        found.append((int(m[1]), cs))
    if len(found) != 1:
        raise OSError(f"Expected one {compatible} SPI1 CS{cs} endpoint")
    return found[0]


def validate_shared(ctrl, pio):
    """Validate the complete shared profile before opening any of its devices."""
    gpios = b''.join(pio + struct.pack('>III',bank,pin,1) for bank,pin in ((8,3),(7,9),(7,5)))
    if (len(pio)!=4 or (ctrl/'cs-gpios').read_bytes()!=gpios or
            (ctrl/'num-cs').read_bytes()!=struct.pack('>I',3)):
        raise ValueError("Expected active-low SPI1 CS on pins 40/26/24")
    expected = (('radio@0','semtech,sx1262'),('cc1101@1','ti,cc1101'),('nrf24@2','nordic,nrf24l01'))
    active = [p for p in ctrl.iterdir() if (p/'reg').is_file() and enabled(p)]
    if {p.name for p in active} != {name for name,_ in expected}:
        raise ValueError("Unexpected client on shared SPI1")
    for cs,(name,kind) in enumerate(expected):
        p = ctrl/name
        if ((p/'reg').read_bytes() != struct.pack('>I',cs) or
                (p/'compatible').read_bytes().split(b'\0') != [kind.encode(), b'armbian,spi-dev', b''] or
                any((p/k).exists() for k in ('spi-cpha','spi-cpol','spi-cs-high','spi-3wire','spi-lsb-first'))):
            raise ValueError(f"Invalid shared SPI1 CS{cs} endpoint")
    if (ctrl/'nrf24@2/ce-gpios').read_bytes() != pio + struct.pack('>III',7,4,0):
        raise ValueError("nRF24 CE must be on physical 18")
    for prop,fields in (("reset-gpios",(8,1,1)), ("busy-gpios",(8,4,0)),
                        ("dio1-gpios",(2,12,0)), ("rxen-gpios",(8,15,0))):
        if (ctrl/"radio@0"/prop).read_bytes() != pio + struct.pack(">III",*fields):
            raise ValueError(f"Unexpected SX1262 {prop}")
    check_pinmux(ctrl,ctrl.parent/"pinctrl@300b000")


def find_spi(bus, device, *, control_pins=None, sysfs=Path('/sys')):
    """Match the live SPI controller, radio DT node and active-low PI3 CS."""
    if device != 0:
        raise ValueError("Waveshare SX1262 requires logical CS0")
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
        if node.parent != controller or not enabled(controller) or not enabled(node):
            continue
        if b'semtech,sx1262' not in (node / 'compatible').read_bytes().split(b'\0'):
            continue
        if (node / 'reg').read_bytes() != struct.pack('>I', select):
            continue
        # Both qualified layouts keep the HAT on CS0.
        pio = (dt / 'pinctrl@300b000/phandle').read_bytes()
        count_file = controller / 'num-cs'
        count = count_file.read_bytes() if count_file.exists() else struct.pack('>I',1)
        if count == struct.pack('>I',3):
            validate_shared(controller,pio)
            if control_pins is not None and tuple(control_pins) != (12,38,36,31):
                raise ValueError("Shared profile requires reset/BUSY/DIO1/TXEN on pins 12/38/36/31")
        elif (count != struct.pack('>I',1) or len(pio) != 4 or (node / 'spi-cs-high').exists() or
              (controller/'cs-gpios').read_bytes() != pio + struct.pack('>III', 8, 3, 1)):
            raise ValueError('SX1262 requires kernel CS0 on physical 40 (PI3, active low)')
        else:
            check_pinmux(controller,dt/'pinctrl@300b000')
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


def selected_spi_hz(bus, device, *, sysfs=Path('/sys'),
                    setting=Path('/etc/armbian-config/sx1262-spi-hz')):
    node = sysfs / f'class/spidev/spidev{bus}.{device}/device/of_node'
    cell = (node / 'spi-max-frequency').read_bytes()
    if len(cell) != 4 or int.from_bytes(cell, 'big') < 3000:
        raise ValueError('Invalid SX1262 device-tree SPI ceiling')
    limit = min(16_000_000, int.from_bytes(cell, 'big'))
    try:
        text = setting.read_bytes().removesuffix(b'\n')
    except FileNotFoundError:
        return min(2_000_000, limit)
    if not re.fullmatch(rb'[0-9]{1,8}', text) or not 3000 <= int(text) <= limit:
        raise ValueError(f'SX1262 SPI request must be within 3000..{limit} Hz')
    return int(text)
