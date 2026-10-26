from unittest.mock import Mock

import pytest

from core import battery_monitor


@pytest.fixture
def battery(monkeypatch):
    registers = {1: 0xDF, 2: 0x13, 3: 0x0A, 4: 0x50, 5: 50, 6: 0}
    bus = Mock()
    bus.read_byte_data.side_effect = lambda address, register: registers[register]
    monkeypatch.setattr(battery_monitor, 'SMBUS_AVAILABLE', True)
    monkeypatch.setattr(battery_monitor, 'SMBus', lambda number: bus, raising=False)
    return registers, bus


def test_dfr0528_mcu_registers_and_exact_soc(battery):
    _, bus = battery
    monitor = battery_monitor.BatteryMonitor(poll_interval=0)
    assert monitor.enabled and not monitor.valid
    assert not monitor.is_low()
    assert monitor.update()
    assert monitor.get_status() == {
        'soc': 50, 'voltage': 3.3, 'voltage_mv': 3300,
        'enabled': True, 'valid': True, 'firmware_version': 0x13,
    }
    assert all(call.args[0] == 0x10 for call in bus.read_byte_data.call_args_list)
    monitor.close()
    monitor.close()
    bus.close.assert_called_once()
    assert not monitor.enabled


def test_other_device_at_same_address_is_rejected_and_closed(battery):
    registers, bus = battery
    registers[1] = 0
    monitor = battery_monitor.BatteryMonitor()
    assert not monitor.enabled and not monitor.update()
    bus.close.assert_called_once()


def test_firmware_read_failure_closes_bus(battery):
    registers, bus = battery
    del registers[2]
    monitor = battery_monitor.BatteryMonitor()
    assert not monitor.enabled
    bus.close.assert_called_once()


def test_failed_read_is_not_a_fresh_sample_or_low_battery(battery):
    registers, bus = battery
    registers[5] = 10
    monitor = battery_monitor.BatteryMonitor(poll_interval=0)
    assert monitor.update() and monitor.is_low()
    bus.read_byte_data.side_effect = OSError('adapter disconnected')
    assert not monitor.update()
    assert not monitor.get_status()['valid'] and not monitor.is_low()


def test_polling_uses_monotonic_time(battery, monkeypatch):
    now = [0]
    monkeypatch.setattr(battery_monitor.time, 'monotonic', lambda: now[0])
    monitor = battery_monitor.BatteryMonitor(poll_interval=5)
    assert monitor.update()
    assert not monitor.update()
    now[0] = 5
    assert monitor.update()
