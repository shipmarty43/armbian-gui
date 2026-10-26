from unittest.mock import Mock
from core.hardware_config import hardware_errors
from core.module_loader import ModuleLoader
from test_module_configuration import DummyModule


def test_conflicts_mark_both_modules_and_not_unrelated_modules():
    config = {'hardware': {
        'nrf24': {'enabled': True, 'spi_bus': 1, 'spi_device': 1, 'ce_pin': 18},
        'lora': {'enabled': True, 'spi_bus': 1, 'spi_device': 1, 'reset_pin': 18, 'busy_pin': 24, 'dio1_pin': 23}}}
    errors = hardware_errors(config, ['nrf24', 'lora', 'system'])
    assert set(errors) == {'nrf24', 'lora'}
    assert any('spidev1.1' in e for e in errors['nrf24'])
    assert any('GPIO 18' in e for e in errors['lora'])
    config['hardware']['lora']['enabled'] = False
    assert not hardware_errors(config, ['nrf24', 'lora'])


def test_disabled_module_never_imported(monkeypatch):
    loader = ModuleLoader()
    load = Mock()
    monkeypatch.setattr(loader, 'load_module', load)
    assert loader.load_all_modules(module_names=['gps'], config={'hardware': {'gps': {'enabled': False}}}) == []
    load.assert_not_called()


def test_failed_hardware_is_unloaded_even_when_on_load_swallowed_error(monkeypatch):
    events = []
    module = DummyModule('Radio', 1, events)
    module.hardware_enabled = False
    loader = ModuleLoader()
    monkeypatch.setattr(loader, 'load_module', lambda name: module)
    assert loader.load_all_modules(module_names=['radio']) == []
    assert ('closed', 'Radio') in events
    assert 'unavailable' in loader.status['radio']


def test_package_ids_support_lookup_and_no_duplicate_initialization(monkeypatch):
    events = []
    module = DummyModule('Long Display Name', 1, events)
    loader = ModuleLoader()
    monkeypatch.setattr(loader, 'load_module', lambda name: module)
    loader.load_all_modules(module_names=['radio'])
    loader.load_all_modules(module_names=['radio'])
    assert len(events) == 1
    assert loader.get_module('radio') is module
    assert loader.get_module('Long Display Name') is module


def test_interrupt_during_load_releases_current_module(monkeypatch):
    import pytest
    events = []
    module = DummyModule('Interrupt', 1, events)
    module.on_load = Mock(side_effect=KeyboardInterrupt)
    loader = ModuleLoader()
    monkeypatch.setattr(loader, 'load_module', lambda name: module)
    with pytest.raises(KeyboardInterrupt):
        loader.load_all_modules(module_names=['interrupt'])
    assert events == [('closed', 'Interrupt')]
    assert not loader.modules


def test_external_path_loads_discovered_package(tmp_path):
    package = tmp_path / 'fixture_external'
    package.mkdir()
    (package / '__init__.py').write_text('from .driver import Example\n')
    (package / 'driver.py').write_text('''from core.base_module import BaseModule
class Example(BaseModule):
    def __init__(self): super().__init__('External fixture', '1')
    def get_menu_items(self): return []
''')
    loader = ModuleLoader([str(tmp_path)])
    modules = loader.load_all_modules()
    assert [m.name for m in modules] == ['External fixture']
    assert loader.get_module('fixture_external') is modules[0]
    loader.unload_all()
