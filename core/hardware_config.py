"""Validate selected hardware modules before opening any buses or GPIO."""
from collections import defaultdict

HARDWARE_MODULES = {'gps', 'nfc', 'subghz', 'nrf24', 'lora'}
GPIO_KEYS = {'nfc': ('reset_pin',), 'nrf24': ('ce_pin',),
             'lora': ('reset_pin', 'busy_pin', 'dio1_pin')}
HEADER_GPIO = {3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22,
               23, 24, 26, 27, 28, 29, 31, 32, 33, 35, 36, 37, 38, 40}


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
            if name in {'subghz', 'nrf24', 'lora', 'nfc'}:
                interface = settings.get('interface', 'pn532_spi')
                if name == 'nfc' and interface not in {'pn532_spi', 'pn532_i2c'}:
                    raise ValueError('NFC interface must be pn532_spi or pn532_i2c')
                if name != 'nfc' or interface == 'pn532_spi':
                    bus, device = settings.get('spi_bus'), settings.get('spi_device')
                    if any(type(n) is not int or n < 0 for n in (bus, device)):
                        raise ValueError('spi_bus and spi_device must be non-negative integers')
                    resources[f'/dev/spidev{bus}.{device}'].append(name)
                for key in GPIO_KEYS.get(name, ()):
                    pin = settings.get(key)
                    if pin is None and key == 'reset_pin' and name == 'nfc':
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
