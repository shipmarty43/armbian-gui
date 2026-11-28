from pathlib import Path

import pytest
import yaml

from core.hardware_config import hardware_errors
from core.module_loader import ModuleLoader
from core.radio_lock import acquire_radio

ROOT = Path(__file__).resolve().parents[1]


def profile():
    return yaml.safe_load((ROOT/"config/opi-zero2w-spi1-radios.yaml").read_text())


def test_shared_tui_is_lazy_and_rejects_collisions(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    config=profile()
    ids=["lora","subghz","nrf24"]
    loader=ModuleLoader([str(ROOT/"modules")])
    modules=loader.load_all_modules(module_names=ids,config=config)
    try:
        assert {m.module_id for m in modules}==set(ids),loader.status
        for m in modules:
            item,=m.get_menu_items()
            assert "device information" in item[0]
            assert m.header_diagnostics
    finally:
        loader.unload_all()
    config["hardware"]["nrf24"]["spi_device"]=1
    assert set(hardware_errors(config,ids))=={"nrf24","subghz"}
    config=profile()
    config["hardware"]["nrf24"]["ce_pin"]=26
    assert set(hardware_errors(config,ids))=={"nrf24","subghz"}


def test_lock_uses_header_cs_and_keeps_legacy_inode(tmp_path,monkeypatch):
    import fcntl
    from core import radio_lock
    path=tmp_path/"opi-radio.lock"; path.touch()
    monkeypatch.setattr(radio_lock,"LOCK_PATH",path)
    for i in (1,2): (tmp_path/f"opi-spi1-cs{i}.lock").touch()
    with path.open() as old:
        fcntl.flock(old,fcntl.LOCK_EX)
        with pytest.raises(BlockingIOError): acquire_radio(0)
        with acquire_radio(1), acquire_radio(2):
            with pytest.raises(BlockingIOError): acquire_radio(1)
    with acquire_radio(): pass
    for invalid in (-1,4,False):
        with pytest.raises(ValueError): acquire_radio(invalid)
