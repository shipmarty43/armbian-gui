"""Unpowered SX1262 tests. Only the named QEMU gpio-sim fixture opens GPIO."""
from contextlib import ExitStack
import errno
from functools import partial
from pathlib import Path
import struct
import threading
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call, patch

from core import radio_lock
from core.hardware_config import hardware_errors, lora_settings
from modules.lora import sx1262_driver as radio
from core.sx1262_spi import find_spi, selected_spi_hz


class Route(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        soc = self.root / 'firmware/devicetree/base/soc'
        self.ctrl = soc / 'spi@5011000'
        self.node = self.ctrl / 'radio@0'
        pio = soc / 'pinctrl@300b000'
        self.node.mkdir(parents=True)
        pio.mkdir()
        group = pio / 'spi1-pins'
        group.mkdir()
        (group / 'pins').write_bytes(b'PH6\0PH7\0PH8\0')
        (group / 'function').write_bytes(b'spi1\0')
        (group / 'phandle').write_bytes(struct.pack('>I', 12))
        (self.ctrl / 'pinctrl-0').write_bytes(struct.pack('>I', 12))
        (pio / 'phandle').write_bytes(struct.pack('>I', 88))
        (self.ctrl / 'cs-gpios').write_bytes(struct.pack('>4I', 88, 8, 3, 1))
        (self.node / 'reg').write_bytes(bytes(4))
        (self.node / 'compatible').write_bytes(b'semtech,sx1262\0armbian,spi-dev\0')
        self.dev = self.root / 'class/spidev/spidev7.0/device'
        self.dev.mkdir(parents=True)
        (self.dev / 'of_node').symlink_to(self.node)
        self.find = partial(find_spi, sysfs=self.root)

    def test_saved_clock_and_dt_ceiling(self):
        setting = self.root / 'selected'
        rate = partial(selected_spi_hz, 7, 0, sysfs=self.root, setting=setting)
        prop = self.node / 'spi-max-frequency'
        prop.write_bytes(struct.pack('>I', 16_000_000))
        self.assertEqual(rate(), 2_000_000)
        setting.write_text('16000000\n')
        self.assertEqual(rate(), 16_000_000)
        prop.write_bytes(struct.pack('>I', 2_000_000))
        with self.assertRaises(ValueError):
            rate()
        setting.write_text('2999')
        with self.assertRaises(ValueError):
            rate()

    def test_dynamic_numbering_and_explicit_selection(self):
        self.assertEqual(self.find('auto', 0), (7, 0))
        self.assertEqual(self.find(7, 0), (7, 0))
        with self.assertRaises(OSError):
            self.find(1, 0)
        second = self.root / 'class/spidev/spidev3.0/device'
        second.mkdir(parents=True)
        (second / 'of_node').symlink_to(self.node)
        with self.assertRaises(OSError):
            self.find('auto', 0)

    def test_conflicting_overlays(self):
        peer = self.ctrl / 'spidev@0'
        peer.mkdir()
        (peer / 'reg').write_bytes(bytes(4))
        with self.assertRaisesRegex(ValueError, 'share'):
            self.find('auto', 0)
        (peer / 'status').write_bytes(b'disabled\0')
        self.assertEqual(self.find('auto', 0), (7, 0))
        (self.ctrl / 'pinctrl-0').write_bytes(struct.pack('>2I', 12, 13))
        with self.assertRaisesRegex(ValueError, 'pinmux'):
            self.find('auto', 0)

    def test_wrong_cs_controller_or_peripheral(self):
        for cells in [(88, 8, 3, 0), (99, 8, 3, 1), (88, 8, 4, 1), (0,)]:
            (self.ctrl / 'cs-gpios').write_bytes(struct.pack('>' + 'I' * len(cells), *cells))
            with self.assertRaises(ValueError):
                self.find(7, 0)
        (self.node / 'compatible').write_bytes(b'jedec,spi-nor\0')
        with self.assertRaises(OSError):
            self.find(7, 0)
        (self.dev / 'of_node').unlink()
        (self.dev / 'of_node').symlink_to(self.ctrl.parent / 'spi@5010000/flash@0')
        with self.assertRaises(OSError):
            self.find(7, 0)


def provision_lock(case):
    directory = TemporaryDirectory()
    case.addCleanup(directory.cleanup)
    path = Path(directory.name) / 'opi-radio.lock'
    path.touch()
    replace = patch.object(radio_lock, 'LOCK_PATH', path)
    replace.start()
    case.addCleanup(replace.stop)


class RadioFixture:
    """Script the SPI peripheral responses. Keep separate from the GPIO provider."""
    status = 0x24  # STDBY_RC
    tx_flags = radio.SX1262.TX_DONE
    rx_flags = radio.SX1262.RX_DONE

    def __init__(self, raise_irq, switch_level):
        self.raise_irq = raise_irq
        self.switch_level = switch_level
        self.commands = []
        self.modes = []
        self.flags = 0
        self.payload = b'\0test\xff'
        self.open = Mock()
        self.close = Mock()

    def xfer2(self, packet):
        self.commands.append(bytes(packet))
        cmd = packet[0]
        result = [0] * len(packet)
        if cmd == 0xc0:
            result[1] = self.status
        elif cmd == 0x11:
            result[2] = 1  # LoRa packet type
        elif cmd in (0x82, 0x83):
            self.modes.append((cmd, self.switch_level()))
            self.flags = self.rx_flags if cmd == 0x82 else self.tx_flags
            self.raise_irq(bool(self.flags))
        elif cmd == 0x12:
            result[2:] = self.flags.to_bytes(2, 'big')
        elif cmd == 0x02:
            self.flags &= ~int.from_bytes(packet[1:], 'big')
            self.raise_irq(bool(self.flags))
        elif cmd == 0x13:
            result[2:] = [len(self.payload), 11]
        elif cmd == 0x1e:
            if packet[1:3] != [11, 0] or len(packet) != 3 + len(self.payload):
                raise AssertionError('Driver did not use GetRxBufferStatus offset and length')
            result[3:] = self.payload
        return result


class HostRadio(unittest.TestCase):
    def setUp(self):
        provision_lock(self)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.busy, self.dio, self.switch, self.reset = [Mock() for _ in range(4)]
        self.busy.read.return_value = 0
        self.dio.read.return_value = 0
        self.dio.wait_edge.return_value = None
        self.switch.read.return_value = 0
        self.switch.write.side_effect = lambda value: setattr(self.switch.read, 'return_value', value)
        self.gpio = Mock()
        self.gpio.request_input.side_effect = lambda pin, **opts: {38: self.busy, 36: self.dio}[pin]
        self.gpio.request_output.side_effect = lambda pin, **opts: {12: self.reset, 31: self.switch}[pin]
        self.stack.enter_context(patch.object(radio, 'gpio', self.gpio))
        self.route = self.stack.enter_context(patch.object(radio, 'find_spi', return_value=(7, 0)))
        self.stack.enter_context(patch.object(radio, 'selected_spi_hz', return_value=12_000_000))
        self.spi = RadioFixture(lambda level: setattr(self.dio.read, 'return_value', level), self.switch.read)
        self.stack.enter_context(patch.object(radio, 'spidev', Mock(SpiDev=lambda: self.spi)))
        self.chip = radio.SX1262()
        self.addCleanup(self.chip.close)

    def test_busy_owner_precedes_hardware_and_close_releases(self):
        with radio_lock.acquire_radio():
            self.assertFalse(self.chip.initialize())
            self.route.assert_not_called()
            self.gpio.request_input.assert_not_called()
        self.assertTrue(self.chip.initialize())
        with self.assertRaises(BlockingIOError):
            radio_lock.acquire_radio()
        self.chip.close()
        with radio_lock.acquire_radio():
            pass

    def test_direct_packet_io_and_cleanup(self):
        self.assertTrue(self.chip.initialize())
        self.assertTrue(self.chip.initialize())
        self.spi.open.assert_called_once_with(7, 0)
        self.assertEqual(self.spi.max_speed_hz, 12_000_000)
        self.assertEqual(self.gpio.request_input.call_args_list, [call(38), call(36, edge='rising')])
        self.assertEqual(self.gpio.request_output.call_args_list, [call(31, initial=0), call(12, initial=1)])
        self.assertEqual(self.reset.write.call_args_list, [call(0), call(1)])
        self.assertFalse(self.spi.modes)
        self.assertIn(bytes([0x9d, 1]), self.spi.commands)
        self.assertIn(bytes([0x98, 0x6b, 0x6f]), self.spi.commands)
        self.chip.transmit(self.spi.payload)
        self.assertIn(b'\x0e\0' + self.spi.payload, self.spi.commands)
        self.assertEqual(self.chip.receive(1), self.spi.payload)
        self.assertEqual(self.spi.modes, [(0x83, 0), (0x82, 1)])
        self.assertEqual(self.switch.read(), 0)
        self.chip.close()
        self.chip.close()
        for obj in (self.reset, self.dio, self.busy, self.switch, self.spi):
            obj.close.assert_called_once()

    def test_bad_irq_and_timeout(self):
        self.assertTrue(self.chip.initialize())
        self.spi.rx_flags = self.chip.RX_DONE | 0x0040
        with self.assertRaises(OSError) as cm:
            self.chip.receive()
        self.assertEqual(cm.exception.errno, errno.EBADMSG)
        self.assertEqual(self.switch.read(), 0)
        self.spi.rx_flags = 0
        self.assertIsNone(self.chip.receive(0))
        self.spi.tx_flags = self.chip.TIMEOUT
        with self.assertRaises(TimeoutError):
            self.chip.transmit(b'test')
        with self.assertRaises(ValueError):
            self.chip.transmit(bytes(256))

    def test_open_failure_releases_all_resources_and_can_retry(self):
        self.spi.open.side_effect = OSError('device removed')
        self.assertFalse(self.chip.initialize())
        self.reset.write.assert_not_called()
        self.assertEqual(self.spi.commands, [])
        for obj in (self.reset, self.dio, self.busy, self.switch, self.spi):
            obj.close.assert_called_once()
        self.spi.open.side_effect = None
        self.assertTrue(self.chip.initialize())

    def test_spi_error_restores_rx_switch_and_allows_retry(self):
        self.assertTrue(self.chip.initialize())
        transfer = self.spi.xfer2
        def fail(packet):
            if packet[0] == 0x13:
                raise OSError('receive FIFO unavailable')
            return transfer(packet)
        with patch.object(self.spi, 'xfer2', side_effect=fail), self.assertRaises(OSError):
            self.chip.receive()
        self.assertEqual(self.switch.read(), 0)
        self.assertEqual(self.chip.receive(), self.spi.payload)

    def test_close_serializes_with_active_rx(self):
        self.assertTrue(self.chip.initialize())
        self.spi.rx_flags = 0
        entered, finish, closing = threading.Event(), threading.Event(), threading.Event()
        def wait_edge(timeout):
            if timeout > 0:
                entered.set()
                if not finish.wait(2):
                    raise TimeoutError('fixture did not release the reader')
            return None
        def close():
            closing.set()
            self.chip.close()
        self.dio.wait_edge.side_effect = wait_edge
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(2) as pool:
            reader = pool.submit(self.chip.receive, 1)
            try:
                self.assertTrue(entered.wait(2))
                closer = pool.submit(close)
                self.assertTrue(closing.wait(2))
                self.spi.close.assert_not_called()
            finally:
                finish.set()
            self.assertIsNone(reader.result(timeout=2))
            closer.result(timeout=2)
        self.spi.close.assert_called_once()
        with self.assertRaises(RuntimeError):
            self.chip.transmit(b'test')

    def test_stuck_busy_and_absent_radio(self):
        self.busy.read.return_value = 1
        with patch.object(radio.time, 'monotonic', side_effect=[1, 3]):
            self.assertFalse(self.chip.initialize())
        self.assertFalse(self.spi.commands)
        self.busy.read.return_value = 0
        for status in (0x00, 0xff, 0x28):
            self.spi.status = status
            self.assertFalse(self.chip.initialize())
            self.assertFalse(self.chip.enabled)
        self.assertFalse(self.spi.modes)

    def test_missing_backend_or_route_never_pulses_reset(self):
        with patch.object(radio, 'gpio', None):
            self.assertFalse(self.chip.initialize())
        self.route.side_effect = OSError('not routed')
        self.assertFalse(self.chip.initialize())
        self.gpio.request_input.assert_not_called()
        self.gpio.request_output.assert_not_called()
        self.spi.open.assert_not_called()

    def test_partial_claim_and_interrupted_reset(self):
        self.gpio.request_output.side_effect = [self.switch, OSError(errno.EBUSY, 'in use')]
        self.assertFalse(self.chip.initialize())
        self.spi.open.assert_not_called()
        for line in (self.busy, self.dio, self.switch):
            line.close.assert_called_once()
        self.gpio.request_output.side_effect = [self.switch, self.reset]
        with patch.object(radio.time, 'sleep', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.chip.initialize()
        self.assertEqual(self.reset.write.call_args_list, [call(0), call(1)])
        self.reset.close.assert_called_once()
        self.spi.close.assert_called_once()

    def test_profile_and_conflicts(self):
        for bad in ({'reset_pin': 1}, {'busy_pin': 23}, {'cs_pin': 8}, {'txen_pin': 12},
                    {'frequency': 868}, {'spi_bus': True}, {'coding_rate': 1}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                lora_settings(bad)
        shared = {'hardware': {'lora': {}, 'nfc': {'spi_bus': 7, 'spi_device': 0}}}
        with patch('core.hardware_config.find_spi', return_value=(7, 0)):
            errors = hardware_errors(shared, ['lora', 'nfc'])
            self.assertEqual(set(errors), {'lora', 'nfc'})
            self.assertIn('/dev/spidev7.0', errors['lora'][0])
        for other in (31, 40):
            config = {'hardware': {'lora': {}, 'nfc': {'interface': 'pn532_i2c', 'reset_pin': other}}}
            self.assertEqual(set(hardware_errors(config, ['lora', 'nfc'])), {'lora', 'nfc'})


def is_sim():
    model = Path('/proc/device-tree/model')
    return model.is_file() and model.read_bytes() == b'WiringPi Zero 2W gpio-sim fixture\0'


@unittest.skipUnless(is_sim(), 'requires the WiringPi ARM64 gpio-sim test DT')
class KernelRadio(unittest.TestCase):
    def setUp(self):
        provision_lock(self)

    def test_gpio_ownership_irq_and_recovery(self):
        import wiringpi_zero2w as gpio
        bank = next(Path('/sys/devices/platform').glob('gpio-sim*/gpiochip*'))
        irq = bank / 'sim_gpio24/pull'  # fixture PC12
        switch = bank / 'sim_gpio20/value'  # fixture PI15
        (bank / 'sim_gpio26/pull').write_text('pull-down')  # PI4: BUSY
        spi = RadioFixture(lambda high: irq.write_text('pull-up' if high else 'pull-down'),
                           lambda: int(switch.read_text()))
        with patch.object(radio, 'spidev', Mock(SpiDev=lambda: spi)), patch.object(radio, 'find_spi', return_value=(7, 0)), patch.object(radio, 'selected_spi_hz', return_value=2_000_000):
            chip = radio.SX1262()
            self.addCleanup(chip.close)
            with gpio.request_input(12):
                self.assertFalse(chip.initialize())
                spi.open.assert_not_called()
                for pin in (31, 36, 38):
                    self.assertFalse(gpio.line_info(pin).used)
            self.assertTrue(chip.initialize())
            for pin in (12, 31, 36, 38):
                self.assertTrue(gpio.line_info(pin).used)
            for pin in (8, 10, 40):
                self.assertFalse(gpio.line_info(pin).used)
            for _ in range(70):  # More operations than the kernel edge queue depth.
                chip.transmit(b'loopback')
            self.assertEqual(chip.receive(1), spi.payload)
            self.assertEqual(spi.modes[-2:], [(0x83, 0), (0x82, 1)])
            # Make RX_DONE arrive after SetRx returned, in the kernel event wait.
            def delayed(high):
                if high:
                    timer = threading.Timer(.05, irq.write_text, args=('pull-up',))
                    timer.start()
                    self.addCleanup(timer.join)
                else:
                    irq.write_text('pull-down')
            spi.raise_irq = delayed
            with patch.object(chip._dio1, 'wait_edge', wraps=chip._dio1.wait_edge) as wait:
                self.assertEqual(chip.receive(1), spi.payload)
                self.assertTrue(any(args[0] > 0 for args, _ in wait.call_args_list))
            chip.close()
            for pin in (12, 31, 36, 38):
                self.assertFalse(gpio.line_info(pin).used)

    def test_profile_load_and_unload(self):
        from core.config_loader import ConfigLoader
        from core.module_loader import ModuleLoader
        import wiringpi_zero2w as gpio
        root = Path(__file__).resolve().parents[1]
        config = ConfigLoader(str(root / 'config')).load('opi-zero2w-sx1262.yaml')
        loader = ModuleLoader([str(root / 'modules')])
        self.addCleanup(loader.unload_all)
        spi = RadioFixture(lambda high: None, lambda: 0)
        with patch.object(radio, 'selected_spi_hz', return_value=2_000_000), patch.object(radio, 'find_spi', return_value=(7, 0)), patch.object(radio, 'spidev', Mock(SpiDev=lambda: spi)):
            modules = loader.load_all_modules(module_names=['lora'], config=config)
            self.assertEqual(len(modules), 1, loader.status)
            module = modules[0]
            self.assertTrue(module.hardware_enabled)
            self.assertEqual(module.sx1262.frequency, 433_920_000)
            self.assertIsNone(module.meshtastic)
            self.assertFalse(spi.modes)
            with patch.object(module, 'show_message') as message:
                module.show_status()
                self.assertIn('433.92MHz', message.call_args.args[1])
            loader.unload_all()
            self.assertFalse(module.hardware_enabled)
            for pin in (12, 31, 36, 38):
                self.assertFalse(gpio.line_info(pin).used)

    def test_real_spidev_without_radio(self):
        root = Path('/proc/device-tree/sx1262-spi-test')
        if not root.is_dir():
            self.skipTest('requires sx1262-qemu-spi.dts with SPI_GPIO and SPI_SPIDEV')
        import spidev
        import wiringpi_zero2w as gpio
        dev, = (entry for entry in Path('/sys/class/spidev').glob('spidev*')
                if (entry / 'device/of_node').resolve() == (root / 'radio@0').resolve())
        address = tuple(map(int, dev.name.removeprefix('spidev').split('.')))
        bank = next(Path('/sys/devices/platform').glob('sx1262-test-gpios*/gpiochip*'))
        miso = bank / 'sim_gpio1/pull'
        spi = spidev.SpiDev()
        spi.open(*address)
        try:
            spi.mode = 0
            with TemporaryDirectory() as tmp:
                setting = Path(tmp) / 'spi-hz'
                for expected_rate in (2_000_000, 16_000_000):
                    if expected_rate == 16_000_000:
                        setting.write_text('16000000\n')
                    spi.max_speed_hz = selected_spi_hz(*address, setting=setting)
                    self.assertEqual(spi.max_speed_hz, expected_rate)
                    for bias, expected in (('pull-down', 0x00), ('pull-up', 0xff)):
                        miso.write_text(bias)
                        self.assertEqual(spi.xfer2([0xc0, 0]), [expected, expected])
        finally:
            spi.close()
        with self.assertRaises(OSError):
            find_spi('auto', 0)  # The virtual controller has a different DT path.
        with patch.object(radio, 'find_spi', return_value=address):
            chip = radio.SX1262()
            for bias in ('pull-down', 'pull-up'):
                miso.write_text(bias)
                with self.assertLogs('cyberdeck.sx1262', level='ERROR') as logs:
                    self.assertFalse(chip.initialize())
                self.assertIn('standby status', logs.output[0])
                for pin in (12, 31, 36, 38):
                    self.assertFalse(gpio.line_info(pin).used)


if __name__ == '__main__':
    unittest.main(verbosity=2)
