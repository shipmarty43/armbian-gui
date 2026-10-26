from unittest.mock import patch

import pytest

from core.cpu_power import CpuPowerManager


@pytest.fixture
def power(tmp_path):
    policy = tmp_path / 'policy0'
    policy.mkdir()
    values = {
        'scaling_driver': 'cpufreq-dt', 'scaling_governor': 'ondemand',
        'scaling_available_governors': 'performance powersave ondemand schedutil',
        'scaling_min_freq': '480000', 'scaling_max_freq': '1512000',
        'cpuinfo_max_freq': '1512000', 'scaling_cur_freq': '1008000',
        'scaling_available_frequencies': '480000 1008000 1512000',
    }
    for name, value in values.items():
        (policy / name).write_text(value + '\n')
    return CpuPowerManager(tmp_path)


def test_governor_and_frequency_use_os_interface(power):
    assert power.policies()[0]['current_khz'] == 1008000
    assert power.set_governor('policy0', 'schedutil')['governor'] == 'schedutil'
    state = power.set_max_frequency('policy0', 1008000)
    assert state['max_khz'] == 1008000
    assert state['min_khz'] == 480000


@pytest.mark.parametrize('frequency', [0, 2000000, 999999, '1008000', True])
def test_invalid_frequency_never_changes_policy(power, frequency):
    with pytest.raises(ValueError):
        power.set_max_frequency('policy0', frequency)
    assert power.status('policy0')['max_khz'] == 1512000


def test_invalid_governor_and_path_rejected(power):
    with pytest.raises(ValueError):
        power.set_governor('policy0', 'not-a-governor')
    with pytest.raises(ValueError):
        power.set_governor('../policy0', 'performance')
    assert power.status('policy0')['governor'] == 'ondemand'


def test_missing_cpufreq_and_optional_frequency_table(tmp_path, power):
    assert CpuPowerManager(tmp_path / 'missing').policies() == []
    (power.root / 'policy0/scaling_available_frequencies').unlink()
    (power.root / 'policy0/scaling_cur_freq').unlink()
    state = power.status('policy0')
    assert state['frequencies_khz'] == [] and state['current_khz'] is None


def test_permission_denial_has_no_fallback_to_privileged_commands(power):
    with patch('pathlib.Path.write_text', side_effect=PermissionError):
        with pytest.raises(PermissionError, match='no privileges were elevated'):
            power.set_governor('policy0', 'performance')
    assert power.status('policy0')['governor'] == 'ondemand'


def test_driver_readback_mismatch_is_reported(power):
    with patch('pathlib.Path.write_text'):
        with pytest.raises(RuntimeError, match='Kernel reports'):
            power.set_governor('policy0', 'performance')


def test_ui_settings_change_fake_policy_and_preserve_back_stack(power):
    pytest.importorskip('urwid')
    from core.ui_manager import UIManager
    ui = UIManager([])
    ui.cpu_power = power
    main = ui.frame.body
    ui._on_settings(None)
    assert ui.current_view == 'cpu_settings'
    assert len(ui.view_stack) == 1
    # Render and activate the actual button callback, never real sysfs.
    assert ui.frame.body.render((80, 24)).rows() == 24
    buttons = [getattr(row, 'original_widget', row) for row in ui.frame.body.body]
    next(b for b in buttons if hasattr(b, 'get_label') and
         b.get_label() == 'Governor: schedutil')._emit('click')
    assert power.status('policy0')['governor'] == 'schedutil'
    assert len(ui.view_stack) == 1
    ui.go_back()
    assert ui.frame.body is main
