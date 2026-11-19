"""System Tools inventory uses only the non-claiming GPIO API."""
import errno
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modules.system.system_module import SystemModule


class Inventory(unittest.TestCase):
    def setUp(self):
        self.module = SystemModule()
        self.module.show_menu = Mock(return_value=1)
        self.module.show_message = Mock()

    def test_menu_reads_ownership_and_refreshes_selection(self):
        api = SimpleNamespace(
            header_map=lambda: [(29, 256, "PI0"), (37, 272, "PI16")],
            line_info=Mock(side_effect=[
                SimpleNamespace(used=False, direction="input", consumer=""),
                SimpleNamespace(used=True, direction="output", consumer="test-owner"),
                SimpleNamespace(used=False, direction="input", consumer=""),
            ]),
        )
        with patch.dict(sys.modules, wiringpi_zero2w=api):
            dict(self.module.get_menu_items())["Zero 2W GPIO header"]()
        rows = self.module.show_menu.call_args.args[1]
        self.assertIn("unclaimed", rows[0])
        self.assertIn("test-owner", rows[1])
        heading, body = self.module.show_message.call_args.args
        self.assertIn("PI16", heading)
        self.assertIn("Kernel claim: False", body)

    def test_missing_binding_or_gpio_device(self):
        fail = Mock(side_effect=OSError(errno.ENODEV, "No such device"))
        for api in (None, SimpleNamespace(header_map=fail, line_info=Mock())):
            with patch.dict(sys.modules, wiringpi_zero2w=api):
                self.module.gpio_header()
        self.assertEqual(self.module.show_message.call_count, 2)
        self.module.show_menu.assert_not_called()


if __name__ == "__main__":
    unittest.main()
