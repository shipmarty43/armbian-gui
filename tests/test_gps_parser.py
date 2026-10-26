"""Load the actual parser even on hosts without pyserial or GPS hardware."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_parser_import_and_position_without_opening_uart(monkeypatch):
    serial_port = Mock(side_effect=AssertionError('must not open hardware'))
    monkeypatch.setitem(sys.modules, 'serial', SimpleNamespace(Serial=serial_port))
    path = Path(__file__).resolve().parents[1] / 'modules/gps/gps_parser.py'
    spec = importlib.util.spec_from_file_location('gps_parser_under_test', path)
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)

    parsed = parser_module.NMEAParser().parse_nmea(
        '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47'
    )
    assert parsed['latitude'] == pytest.approx(48.1173)
    assert parsed['longitude'] == pytest.approx(11.5166667)
    assert parsed['fix_quality'] == 1
    serial_port.assert_not_called()
