"""Validate selected hardware modules before opening any buses or GPIO."""
from collections import defaultdict

from core.sx1262_spi import find_spi

HARDWARE_MODULES = {'gps', 'nfc', 'subghz', 'nrf24', 'lora'}
LORA_PINS = {'reset_pin': 12, 'busy_pin': 38, 'dio1_pin': 36, 'txen_pin': 31, 'cs_pin': 40}
GPIO_KEYS = {'subghz': ('gdo0_pin', 'gdo2_pin'), 'nfc': ('reset_pin',), 'nrf24': ('ce_pin',),
             'lora': tuple(LORA_PINS)}
HEADER_GPIO = {3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22,
               23, 24, 26, 27, 28, 29, 31, 32, 33, 35, 36, 37, 38, 40}


def lora_settings(settings):
    """Validate the Waveshare 433/470 MHz SPI/GNSS profile before opening devices."""
    pins = {key: settings.get(key, default) for key, default in LORA_PINS.items()}
    for name, pin in pins.items():
        if type(pin) is not int or pin not in HEADER_GPIO or pin in (19, 21, 23):
            raise ValueError(f'{name} must be a physical GPIO separate from SPI1 data/clock')
    if len(set(pins.values())) != len(pins) or pins['cs_pin'] != 40:
        raise ValueError('SX1262 needs distinct control pins and kernel CS on physical 40')
    bus = settings.get('spi_bus', 'auto')
    device = settings.get('spi_device', 0)
    if bus != 'auto' and (type(bus) is not int or bus < 0):
        raise ValueError("spi_bus must be 'auto' or a non-negative integer")
    if type(device) is not int or device != 0:
        raise ValueError('SX1262 kernel overlay uses logical spi_device 0')
    mhz = settings.get('frequency', 433.92)
    if type(mhz) not in (float, int) or not 410 <= mhz <= 490:
        raise ValueError('frequency must be in MHz for the 410–490 MHz Waveshare variant')
    radio = {}
    for key, default, low, high in (('spreading_factor', 7, 7, 12), ('coding_rate', 5, 5, 8),
                                    ('preamble_length', 8, 8, 65535), ('tx_power', 14, -9, 22)):
        value = settings.get(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'{key} must be an integer in {low}..{high}')
        radio[key] = value
    bandwidth = settings.get('bandwidth', 125)
    if type(bandwidth) is not int or bandwidth not in (125, 250, 500):
        raise ValueError('bandwidth must be 125, 250 or 500 kHz')
    return dict(pins, spi_bus=bus, spi_device=device, frequency_hz=round(mhz * 1_000_000),
                bandwidth_hz=bandwidth * 1000, **radio)


def module_settings(config, name):
    section = config.get('hardware', {}).get(name, {}) if name in HARDWARE_MODULES else config.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f'{name} settings must be a mapping')
    if 'enabled' in section and not isinstance(section['enabled'], bool):
        raise ValueError(f'{name}.enabled must be true or false')
    return section


def hardware_errors(config, names):
    """Return errors by package ID. Conflicts disable every participant."""
    errors = defaultdict(list)
    resources = defaultdict(list)
    for name in names:
        try:
            settings = module_settings(config, name)
            if not settings.get('enabled', True):
                continue
            if name == 'lora':
                settings = lora_settings(settings)
            if name in {'subghz', 'nrf24', 'lora', 'nfc'}:
                interface = settings.get('interface', 'pn532_spi')
                if name == 'nfc' and interface not in {'pn532_spi', 'pn532_i2c'}:
                    raise ValueError('NFC interface must be pn532_spi or pn532_i2c')
                if name != 'nfc' or interface == 'pn532_spi':
                    bus, device = settings.get('spi_bus'), settings.get('spi_device')
                    if name != 'lora' and any(type(n) is not int or n < 0 for n in (bus, device)):
                        raise ValueError('spi_bus and spi_device must be non-negative integers')
                    if name == 'lora' and bus == 'auto':
                        try:
                            bus, device = find_spi(bus, device)
                        except (ValueError, OSError):
                            bus = None  # Offline preflight. Activation checks the live route again.
                    if bus is not None:
                        resources[f'/dev/spidev{bus}.{device}'].append(name)
                if name in {"subghz","nrf24","nfc"} and (name != "nfc" or interface == "pn532_spi") and "cs_header" in settings:
                    pin = settings["cs_header"]
                    if type(pin) is not int or pin not in HEADER_GPIO:
                        raise ValueError("cs_header must be the physical pin wired to the kernel chip select")
                    resources[f'physical GPIO {pin}'].append(name)
                for key in GPIO_KEYS.get(name, ()):
                    pin = settings.get(key)
                    if pin is None and (name == 'subghz' or key == 'reset_pin' and name == 'nfc'):
                        continue
                    if type(pin) is not int or pin not in HEADER_GPIO:
                        raise ValueError(f'{key} must be a GPIO-capable physical header pin')
                    resources[f'physical GPIO {pin}'].append(name)
            if name == 'gps':
                if not isinstance(settings.get('device', settings.get('uart_port')), str):
                    raise ValueError('GPS device must be a serial device path')
        except ValueError as exc:
            errors[name].append(str(exc))
    for resource, owners in resources.items():
        if len(owners) > 1:
            for name in owners:
                errors[name].append(f'{resource} is requested more than once: {", ".join(owners)}')
    return dict(errors)
