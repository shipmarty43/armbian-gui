import subprocess
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from core.resources import stop_process
from modules.wifi.hcxtools_wrapper import HCXToolsWrapper


def test_child_is_killed_reaped_and_pipes_closed_on_timeout():
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired('child', 5), 0]
    stop_process(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2
    process.stdout.close.assert_called_once()
    process.stderr.close.assert_called_once()


def wrapper(monkeypatch, tmp_path):
    monkeypatch.setattr(HCXToolsWrapper, '_check_tool', lambda *args: False)
    return HCXToolsWrapper(str(tmp_path))


def test_interrupt_stops_child(monkeypatch, tmp_path):
    owner = wrapper(monkeypatch, tmp_path)
    process = Mock(stdout=None, stderr=None)
    process.poll.return_value = None
    monkeypatch.setattr(subprocess, 'Popen', Mock(return_value=process))
    monkeypatch.setattr('modules.wifi.hcxtools_wrapper.time.sleep', Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        owner._run_timed_process(['test-command'], 10)
    process.terminate.assert_called_once()
    process.wait.assert_called_once()
    assert not owner._processes


def test_no_interface_change_on_unload_without_ownership(monkeypatch, tmp_path):
    owner = wrapper(monkeypatch, tmp_path)
    run = Mock()
    monkeypatch.setattr(subprocess, 'run', run)
    owner.set_managed_mode('wlan0')
    owner.close()
    run.assert_not_called()


def test_partial_monitor_failure_restores_original_down_state(monkeypatch, tmp_path):
    owner = wrapper(monkeypatch, tmp_path)
    run = Mock(side_effect=[SimpleNamespace(stdout='Interface wlan0\n\ttype managed\n'),
                           SimpleNamespace(stdout='[{"flags": []}]'),
                           None, subprocess.CalledProcessError(1, 'iw'), None, None, None])
    monkeypatch.setattr(subprocess, 'run', run)
    assert not owner.set_monitor_mode('wlan0')
    assert run.call_args_list[-1].args[0] == ['ip', 'link', 'set', 'wlan0', 'down']
    assert not owner._changed_interfaces
