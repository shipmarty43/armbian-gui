"""Explicit, runtime-only CPU policy changes through Linux CPUFreq sysfs."""
from pathlib import Path
import re


class CpuPowerManager:
    def __init__(self, root='/sys/devices/system/cpu/cpufreq'):
        self.root = Path(root)

    def _policy(self, name):
        if not re.fullmatch(r'policy[0-9]+', name):
            raise ValueError('Invalid CPU policy name')
        path = self.root / name
        if not path.is_dir():
            raise FileNotFoundError(f'CPUFreq policy {name} is unavailable')
        return path

    @staticmethod
    def _read(path, name):
        return (path / name).read_text().strip()

    def status(self, name):
        path = self._policy(name)
        read = lambda key: self._read(path, key)
        frequencies = path / 'scaling_available_frequencies'
        current = path / 'scaling_cur_freq'
        return {
            'name': name,
            'driver': read('scaling_driver'),
            'governor': read('scaling_governor'),
            'governors': read('scaling_available_governors').split(),
            'min_khz': int(read('scaling_min_freq')),
            'max_khz': int(read('scaling_max_freq')),
            'hardware_max_khz': int(read('cpuinfo_max_freq')),
            'current_khz': int(current.read_text()) if current.exists() else None,
            'frequencies_khz': sorted(set(map(int, frequencies.read_text().split())))
                if frequencies.exists() else [],
        }

    def policies(self):
        return [self.status(path.name) for path in sorted(self.root.glob('policy*'))
                if re.fullmatch(r'policy[0-9]+', path.name) and path.is_dir()]

    def _write_checked(self, name, attribute, value):
        path = self._policy(name)
        try:
            (path / attribute).write_text(str(value) + '\n')
        except PermissionError as error:
            raise PermissionError('CPUFreq change denied by the OS; no privileges '
                                  'were elevated.') from error
        actual = self._read(path, attribute)
        if actual != str(value):
            raise RuntimeError(f'Kernel reports {attribute}={actual}, requested {value}. '
                               'Another power service or the driver may have changed it.')
        return self.status(name)

    def set_governor(self, name, governor):
        if governor not in self.status(name)['governors']:
            raise ValueError('This governor is not available on this CPU policy')
        return self._write_checked(name, 'scaling_governor', governor)

    def set_max_frequency(self, name, khz):
        if isinstance(khz, bool) or not isinstance(khz, int):
            raise ValueError('Frequency must be an integer in kHz')
        status = self.status(name)
        if not status['min_khz'] <= khz <= status['hardware_max_khz']:
            raise ValueError('Frequency must be within the current minimum and hardware maximum')
        if status['frequencies_khz'] and khz not in status['frequencies_khz']:
            raise ValueError('Frequency is not in the kernel frequency table')
        return self._write_checked(name, 'scaling_max_freq', khz)
