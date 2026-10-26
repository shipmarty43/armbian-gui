from types import SimpleNamespace
from unittest.mock import Mock
import importlib
import sys
import pytest
from core.resources import GpioLease


def gpio_mock():
    gpio = Mock(BOARD=1, OUT=2, IN=3, HIGH=1, LOW=0)
    gpio.getmode.return_value = None
    return gpio


def test_gpio_ownership_and_partial_failure():
    gpio = gpio_mock()
    a, b = GpioLease(gpio), GpioLease(gpio)
    a.setup(18, gpio.OUT)
    with pytest.raises(RuntimeError, match='already owned'):
        b.setup(18, gpio.IN)
    b.setup(24, gpio.IN)
    a.close()
    gpio.cleanup.assert_called_once_with(18)
    assert b.pins == [24]
    a.close()
    gpio.cleanup.assert_called_once_with(18)
    b.close()
    gpio.setup.side_effect = OSError('setup failed')
    with pytest.raises(OSError):
        a.setup(18, gpio.OUT)
    assert a.pins == []
    assert not GpioLease._owners


def test_gpio_refuses_conflicting_numbering_mode():
    gpio = gpio_mock()
    gpio.getmode.return_value = 999
    with pytest.raises(RuntimeError, match='numbering'):
        GpioLease(gpio).setup(18, gpio.OUT)
    gpio.setup.assert_not_called()
    gpio.setmode.assert_not_called()
    gpio.cleanup.assert_not_called()


@pytest.mark.parametrize('driver_path,cls_name', [
    ('modules.subghz.cc1101_driver', 'CC1101'),
    ('modules.lora.sx1262_driver', 'SX1262'),
])
def test_spi_initialize_failure_closes_partial_driver(monkeypatch, driver_path, cls_name):
    module = importlib.import_module(driver_path)
    spi = Mock()
    spi.open.side_effect = OSError('device removed')
    gpio = gpio_mock()
    monkeypatch.setattr(module, 'SPI_AVAILABLE', True)
    monkeypatch.setattr(module, 'spidev', SimpleNamespace(SpiDev=lambda: spi), raising=False)
    monkeypatch.setattr(module, 'GPIO_AVAILABLE', True)
    monkeypatch.setattr(module, 'GPIO', gpio, raising=False)
    device = getattr(module, cls_name)()
    assert not device.initialize()
    spi.close.assert_called_once()
    assert device.spi is None
    assert not GpioLease._owners
    device.close()
    spi.close.assert_called_once()


def test_cc1101_standby_failure_still_closes_spi():
    from modules.subghz.cc1101_driver import CC1101
    device = CC1101()
    spi = device.spi = Mock()
    device.enabled = True
    device.enter_idle = Mock(side_effect=OSError('unplugged'))
    device.close()
    spi.close.assert_called_once()
    assert not device.enabled and device.spi is None


def test_pn532_closes_i2c_even_if_spi_close_fails(monkeypatch):
    from modules.nfc.pn532_driver import PN532
    bus = Mock()
    monkeypatch.setitem(sys.modules, 'smbus2', SimpleNamespace(SMBus=lambda _: bus))
    device = PN532(interface='i2c')
    device.spi = Mock()
    device.spi.close.side_effect = OSError('unplugged')
    device.close()
    bus.close.assert_called_once()
    device.close()
    bus.close.assert_called_once()


def test_pn532_failed_constructor_releases_reset_pin(monkeypatch):
    from modules.nfc import pn532_driver as module
    gpio = gpio_mock()
    spi = Mock()
    spi.open.side_effect = OSError('missing SPI')
    monkeypatch.setattr(module, 'GPIO_AVAILABLE', True)
    monkeypatch.setattr(module, 'SPI_AVAILABLE', True)
    monkeypatch.setattr(module, 'GPIO', gpio, raising=False)
    monkeypatch.setattr(module, 'spidev', SimpleNamespace(SpiDev=lambda: spi), raising=False)
    device = module.PN532(reset_pin=18)
    device._hardware_reset = Mock(side_effect=AssertionError("released reset pin"))
    assert not device.initialize()
    device._hardware_reset.assert_not_called()
    spi.close.assert_called_once()
    gpio.cleanup.assert_called_once_with(18)
    device.close()
    assert not GpioLease._owners


def test_nrf_constructor_radio_failure_cleans_spi_and_ce(monkeypatch):
    spi = Mock()
    monkeypatch.setitem(sys.modules, 'spidev', SimpleNamespace(SpiDev=lambda: spi))
    module = importlib.import_module('modules.nrf24.nrf24_driver')
    gpio = gpio_mock()
    monkeypatch.setattr(module, 'GPIO_AVAILABLE', True)
    monkeypatch.setattr(module, 'GPIO', gpio, raising=False)
    monkeypatch.setattr(module.NRF24Spectrum, 'init_radio', Mock(side_effect=OSError('no radio')))
    with pytest.raises(OSError):
        module.NRF24Spectrum(ce_pin=18)
    spi.close.assert_called_once()
    gpio.cleanup.assert_called_once_with(18)
    assert not GpioLease._owners


@pytest.mark.parametrize('failure', ['activate', 'read'])
def test_sdr_stream_closed_after_failure(failure):
    from core.resources import sdr_stream
    device = Mock()
    if failure == 'activate':
        device.activateStream.side_effect = OSError('activation')
    else:
        device.deactivateStream.side_effect = OSError('device removed')
    with pytest.raises(OSError):
        with sdr_stream(device, 0, 'CF32'):
            raise OSError('read')
    device.closeStream.assert_called_once_with(device.setupStream.return_value)


def test_gadget_cleanup_does_not_touch_preexisting_gadget(monkeypatch):
    from modules.badusb.usb_gadget import USBGadgetController
    device = USBGadgetController()
    rmdir = Mock()
    monkeypatch.setattr('os.rmdir', rmdir)
    assert device.cleanup()
    rmdir.assert_not_called()


def test_gadget_cleanup_removes_configfs_dirs_not_attribute_files(monkeypatch):
    from modules.badusb.usb_gadget import USBGadgetController
    device = USBGadgetController()
    device._owned = True
    device.enabled = True
    device._write_file = Mock()
    monkeypatch.setattr('os.path.exists', lambda _: True)
    monkeypatch.setattr('os.path.islink', lambda _: True)
    unlink, rmdir = Mock(), Mock()
    monkeypatch.setattr('os.unlink', unlink)
    monkeypatch.setattr('os.rmdir', rmdir)
    assert device.cleanup()
    device._write_file.assert_called_once_with(device.gadget_path + '/UDC', '')
    unlink.assert_called_once_with(device.gadget_path + '/configs/c.1/hid.usb0')
    assert rmdir.call_count == 5
    assert not device.enabled and not device._owned
    assert device.cleanup()  # no repeated deletion
    assert rmdir.call_count == 5


def test_failed_gadget_setup_attempts_owned_cleanup(monkeypatch):
    from modules.badusb.usb_gadget import USBGadgetController
    device = USBGadgetController()
    monkeypatch.setattr('os.path.exists', lambda _: True)
    monkeypatch.setattr('os.makedirs', Mock())
    device._write_file = Mock(side_effect=OSError('configfs write failed'))
    device.cleanup = Mock(return_value=True)
    assert not device.setup_gadget()
    assert device._owned
    device.cleanup.assert_called_once()


def test_gadget_setup_refuses_existing_directory(monkeypatch):
    from modules.badusb.usb_gadget import USBGadgetController
    device = USBGadgetController()
    monkeypatch.setattr('os.path.exists', lambda _: True)
    monkeypatch.setattr('os.makedirs', Mock(side_effect=FileExistsError))
    device._write_file = Mock()
    assert not device.setup_gadget()
    assert not device._owned
    device._write_file.assert_not_called()
