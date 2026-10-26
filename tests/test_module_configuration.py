"""Configuration and lifecycle regressions; no physical devices are opened."""
import importlib
from unittest.mock import Mock

import pytest

from core.base_module import BaseModule
from core.config_loader import ConfigLoader
from core.module_loader import ModuleLoader


class DummyModule(BaseModule):
    def __init__(self, name, priority, events, fail=False):
        super().__init__(name, 'test', priority)
        self.events = events
        self.fail = fail

    def get_menu_items(self):
        return []

    def on_load(self):
        self.events.append((self.name, self.get_config()))
        if self.fail:
            raise RuntimeError('device unavailable')

    def on_unload(self):
        self.events.append(('closed', self.name))


def test_selected_modules_initialize_in_priority_order_with_config(monkeypatch):
    events = []
    config = {'hardware': {'gps': {'device': '/dev/test-gps'}}}
    modules = {name: DummyModule(name, priority, events)
               for name, priority in [('slow', 9), ('fast', 1)]}
    loader = ModuleLoader()
    load = Mock(side_effect=modules.get)
    monkeypatch.setattr(loader, 'load_module', load)
    result = loader.load_all_modules(module_names=['slow', 'fast', 'slow'], config=config)
    assert [m.name for m in result] == ['fast', 'slow']
    assert events == [('fast', config), ('slow', config)]
    assert load.call_count == 2


def test_empty_autoload_does_not_discover_or_initialize(monkeypatch):
    loader = ModuleLoader()
    discover = Mock(side_effect=AssertionError('must not discover modules'))
    monkeypatch.setattr(loader, 'discover_modules', discover)
    assert loader.load_all_modules(module_names=[]) == []
    discover.assert_not_called()


def test_failed_initialization_is_cleaned_up_and_not_registered(monkeypatch):
    events = []
    module = DummyModule('failed', 1, events, fail=True)
    loader = ModuleLoader()
    monkeypatch.setattr(loader, 'load_module', lambda name: module)
    assert loader.load_all_modules(module_names=['failed']) == []
    assert events == [('failed', {}), ('closed', 'failed')]
    assert loader.get_all_modules() == []


def test_discovery_and_unsorted_loading_remain_available(monkeypatch):
    events = []
    modules = {name: DummyModule(name, priority, events)
               for name, priority in [('slow', 9), ('fast', 1)]}
    loader = ModuleLoader()
    monkeypatch.setattr(loader, 'discover_modules', lambda: ['slow', 'fast'])
    monkeypatch.setattr(loader, 'load_module', modules.get)
    result = loader.load_all_modules(priority_order=False)
    assert [m.name for m in result] == ['slow', 'fast']
    assert [name for name, _ in events] == ['slow', 'fast']


@pytest.mark.parametrize('contents', ['', 'null', '[]', '42', 'false', 'text'])
def test_non_mapping_config_returns_empty_mapping(tmp_path, contents):
    (tmp_path / 'main.yaml').write_text(contents)
    assert ConfigLoader(str(tmp_path)).load('main.yaml') == {}


@pytest.mark.parametrize('package,class_name,section', [
    ('nfc', 'NFCModule', 'hardware'),
    ('nrf24', 'NRF24Module', 'hardware'),
    ('bluetooth', 'BluetoothModule', 'bluetooth'),
    ('badusb', 'BadUSBModule', 'badusb'),
])
def test_disabled_modules_obey_supplied_config_not_default_file(
        monkeypatch, tmp_path, package, class_name, section):
    monkeypatch.chdir(tmp_path)
    imported = importlib.import_module(f'modules.{package}')
    module = getattr(imported, class_name)()
    settings = {'enabled': False}
    module.config = {section: {package: settings} if section == 'hardware' else settings}
    monkeypatch.setattr(module, 'load_config', Mock(side_effect=AssertionError('wrong config')))
    module.on_load()
    assert not module.enabled


def test_gps_device_and_baudrate_reach_driver(monkeypatch, tmp_path):
    imported = importlib.import_module('modules.gps.gps_module')
    monkeypatch.chdir(tmp_path)
    driver = Mock()
    driver.return_value.initialize.return_value = True
    monkeypatch.setattr(imported, 'GPS_AVAILABLE', True)
    monkeypatch.setattr(imported, 'GPSReader', driver, raising=False)
    module = imported.GPSModule()
    module.config = {'hardware': {'gps': {
        'enabled': True, 'device': '/dev/custom-gps', 'baudrate': 115200}}}
    module.on_load()
    driver.assert_called_once_with(port='/dev/custom-gps', baudrate=115200)
    assert module.hardware_enabled
    module.on_unload()
    driver.return_value.close.assert_called_once()


def test_subghz_receives_spi_configuration(monkeypatch, tmp_path):
    imported = importlib.import_module('modules.subghz.subghz_module')
    monkeypatch.chdir(tmp_path)
    driver = Mock()
    driver.return_value.initialize.return_value = True
    monkeypatch.setattr(imported, 'CC1101_AVAILABLE', True)
    monkeypatch.setattr(imported, 'CC1101', driver)
    module = imported.SubGHzModule()
    module.config = {'hardware': {'subghz': {
        'enabled': True, 'spi_bus': 3, 'spi_device': 0, 'cs_pin': 24, 'gdo0_pin': 16}}}
    module.on_load()
    driver.assert_called_once_with(spi_bus=3, spi_device=0, cs_pin=24, gdo0_pin=16)
    assert module.hardware_enabled
    module.on_unload()
    driver.return_value.close.assert_called_once()


@pytest.mark.parametrize('mesh_available', [False, True])
def test_lora_uses_hardware_section(monkeypatch, tmp_path, mesh_available, caplog):
    imported = importlib.import_module('modules.lora.lora_module')
    monkeypatch.chdir(tmp_path)
    driver = Mock()
    driver.return_value = Mock(spec=imported.SX1262)
    driver.return_value.initialize.return_value = True
    monkeypatch.setattr(imported, 'SX1262_AVAILABLE', True)
    monkeypatch.setattr(imported, 'SX1262', driver)
    monkeypatch.setattr(imported, 'MESHTASTIC_PROTOCOL_AVAILABLE', mesh_available)
    monkeypatch.setattr(imported, 'RETICULUM_AVAILABLE', False)
    module = imported.LoRaModule()
    module.config = {'hardware': {'lora': {
        'enabled': True, 'spi_bus': 2, 'spi_device': 1,
        'reset_pin': 11, 'busy_pin': 13, 'dio1_pin': 15}}}
    module.on_load()
    driver.assert_called_once_with(spi_bus=2, spi_device=1, reset_pin=11, busy_pin=13, dio1_pin=15)
    assert module.hardware_enabled
    module.on_unload()
    driver.return_value.close.assert_called_once()

    if mesh_available:
        driver.return_value.set_rf_frequency.assert_called_once_with(868000000)
        assert 'Failed to initialize Meshtastic' not in caplog.text


def test_pn532_uses_declared_smbus2_dependency(monkeypatch):
    import sys
    from types import SimpleNamespace
    from modules.nfc.pn532_driver import PN532

    bus = Mock()
    monkeypatch.setitem(sys.modules, 'smbus2', SimpleNamespace(SMBus=bus))
    device = PN532(interface='i2c', i2c_bus=3, i2c_address=0x24)
    bus.assert_called_once_with(3)
    assert device.i2c is bus.return_value
    assert device.i2c_address == 0x24


@pytest.mark.parametrize('contents', ['hardware: []', 'hardware: {gps: null}',
                                      'modules: {autoload: gps}', 'modules: {paths: [2]}'])
def test_invalid_nested_config_rejected_before_startup(tmp_path, contents):
    (tmp_path / 'main.yaml').write_text(contents)
    assert ConfigLoader(str(tmp_path)).load('main.yaml') == {}
