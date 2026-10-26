from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from core import main as app


@pytest.mark.parametrize('failure', ['ui_init', 'ui_run', 'network_init', 'module_load', 'normal'])
def test_all_startup_and_runtime_paths_close_acquired_resources(monkeypatch, failure):
    monkeypatch.setattr(app, 'parse_args', lambda: SimpleNamespace(config='test', log_level=None, no_ui=False))
    config = {'hardware': {'battery': {'enabled': True}, 'thermal': {'monitoring': False}}}
    monkeypatch.setattr(app.ConfigLoader, 'load', lambda *args: config)
    logger = Mock()
    battery = Mock()
    loader = Mock(status={}, modules={})
    loader.load_all_modules.return_value = []
    ui = Mock()
    if failure == 'ui_run':
        ui.run.side_effect = RuntimeError('UI failed')
    if failure == 'module_load':
        loader.load_all_modules.side_effect = RuntimeError('module failed')
    monkeypatch.setattr(app, 'CyberDeckLogger', Mock(return_value=logger))
    monkeypatch.setattr(app, 'BatteryMonitor', Mock(return_value=battery))
    monkeypatch.setattr(app, 'NetworkMonitor', Mock(side_effect=RuntimeError('network failed') if failure == 'network_init' else None))
    monkeypatch.setattr(app.ModuleLoader, 'get_instance', Mock(return_value=loader))
    monkeypatch.setattr(app.UIManager, 'get_instance', Mock(return_value=ui, side_effect=RuntimeError('UI init failed') if failure == 'ui_init' else None))
    assert app.main() == (0 if failure == 'normal' else 1)
    battery.close.assert_called_once()
    logger.close.assert_called_once()
    if failure != 'network_init':
        loader.unload_all.assert_called_once()


@pytest.mark.parametrize('module_name,result', [('system', 0), ('missing_test_module', 1)])
def test_config_check_never_initializes_hardware(monkeypatch, module_name, result):
    monkeypatch.setattr(app, 'parse_args', lambda: SimpleNamespace(config='test', check_config=True))
    config = {'hardware': {'battery': {'enabled': True}},
              'modules': {'paths': ['modules'], 'autoload': [module_name]}}
    monkeypatch.setattr(app.ConfigLoader, 'load', lambda *args: config)
    forbidden = Mock(side_effect=AssertionError('hardware initialization during validation'))
    monkeypatch.setattr(app, 'BatteryMonitor', forbidden)
    monkeypatch.setattr(app, 'CyberDeckLogger', forbidden)
    assert app.main() == result
    forbidden.assert_not_called()
