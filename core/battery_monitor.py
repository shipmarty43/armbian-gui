"""
Battery Monitor - мониторинг батареи через UPS I2C модуль
"""

import logging
import time
from typing import Dict, Optional

try:
    from smbus2 import SMBus
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False


class BatteryMonitor:
    """
    Мониторинг DFR0528 через MCU платы, а не напрямую через MAX17043.

    I2C адрес: 0x10 (по умолчанию)
    I2C шина: задаётся по фактическому Linux-адаптеру и распиновке.
    Функции: чтение уровня заряда (%), напряжения (mV)

    Протокол UPS модуля:
    - Регистр 0x03: VCELL_H (старший байт напряжения)
    - Регистр 0x04: VCELL_L (младший байт напряжения)
    - Регистр 0x05: SOC_H (старший байт процента заряда)
    - Регистр 0x06: SOC_L (младший байт процента заряда)

    Формулы:
    - Напряжение (mV) = (((VCELL_H & 0x0F) << 8) + VCELL_L) * 1.25
    - Процент заряда = ((SOC_H << 8) + SOC_L) / 256
    """

    def __init__(
        self,
        i2c_bus: int = 3,
        i2c_address: int = 0x10,
        poll_interval: int = 5
    ):
        """
        Инициализация монитора батареи UPS.

        Args:
            i2c_bus: Настроенный номер Linux I2C-адаптера; не номер TWI в SoC
            i2c_address: I2C адрес UPS модуля (по умолчанию 0x10)
            poll_interval: Интервал опроса (секунды)
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.poll_interval = poll_interval
        self.logger = logging.getLogger("cyberdeck.battery")

        self.enabled = False
        self.valid = False
        self.bus = None
        self.firmware_version = None
        self.soc = 0  # State of Charge (%)
        self.voltage = 0.0  # Напряжение (V)
        self.voltage_mv = 0  # Напряжение (mV)
        self.last_update = None

        if not SMBUS_AVAILABLE:
            self.logger.warning("smbus2 not available, battery monitoring disabled")
            return

        try:
            self.bus = SMBus(i2c_bus)
            # 0x10 may also be occupied by an unrelated device on another bus.
            # DFRobot specifies PID=0xDF at register 0x01 for this HAT.
            if self.bus.read_byte_data(i2c_address, 0x01) != 0xDF:
                raise ValueError('I2C device is not a DFR0528 (unexpected product ID)')
            self.firmware_version = self.bus.read_byte_data(i2c_address, 0x02)
            self.enabled = True
            self.logger.info(f"UPS Battery monitor initialized on I2C bus {i2c_bus}, address 0x{i2c_address:02X}")
        except Exception as e:
            self.logger.error(f"Failed to initialize UPS battery monitor: {e}")
            self.close()

    def read_soc(self) -> Optional[int]:
        """
        Прочитать State of Charge (уровень заряда) из UPS модуля.

        Returns:
            int or None: Процент заряда (0-100)
        """
        if not self.enabled:
            return None

        try:
            # Регистры SOC: 0x05 (старший байт), 0x06 (младший байт)
            soc_h = self.bus.read_byte_data(self.i2c_address, 0x05)
            soc_l = self.bus.read_byte_data(self.i2c_address, 0x06)

            # Use the exact binary fraction, avoiding 50% becoming int(49.9968).
            soc_raw = (soc_h << 8) + soc_l
            soc = soc_raw / 256.0

            return int(min(100, max(0, soc)))  # Ограничиваем 0-100%

        except Exception as e:
            self.logger.error(f"Failed to read SOC: {e}")
            return None

    def read_voltage(self) -> Optional[float]:
        """
        Прочитать напряжение батареи из UPS модуля.

        Returns:
            float or None: Напряжение (V)
        """
        if not self.enabled:
            return None

        try:
            # Регистры VCELL: 0x03 (старший байт), 0x04 (младший байт)
            vcell_h = self.bus.read_byte_data(self.i2c_address, 0x03)
            vcell_l = self.bus.read_byte_data(self.i2c_address, 0x04)

            # Формула из рабочего скрипта: (((VCELL_H & 0x0F) << 8) + VCELL_L) * 1.25
            capacity_mv = (((vcell_h & 0x0F) << 8) + vcell_l) * 1.25

            # Сохраняем в mV и конвертируем в V
            self.voltage_mv = int(capacity_mv)
            voltage = capacity_mv / 1000.0

            return round(voltage, 3)

        except Exception as e:
            self.logger.error(f"Failed to read voltage: {e}")
            return None

    def update(self) -> bool:
        """
        Обновить данные (если прошёл poll_interval).

        Returns:
            bool: True если данные обновлены
        """
        if not self.enabled:
            return False
        current_time = time.monotonic()

        if self.last_update is not None and (current_time - self.last_update) < self.poll_interval:
            return False

        soc = self.read_soc()
        voltage = self.read_voltage()

        self.last_update = current_time
        self.valid = soc is not None and voltage is not None
        if not self.valid:
            return False
        self.soc = soc
        self.voltage = voltage

        self.logger.debug(f"UPS Battery: {self.soc}%, {self.voltage_mv}mV ({self.voltage}V)")
        return True

    def get_status(self) -> Dict[str, any]:
        """
        Получить текущий статус батареи UPS.

        Returns:
            Dict: {
                "soc": int,           # Процент заряда (0-100)
                "voltage": float,     # Напряжение в вольтах
                "voltage_mv": int,    # Напряжение в милливольтах
                "enabled": bool       # Включен ли монитор
            }
        """
        return {
            "soc": self.soc,
            "voltage": self.voltage,
            "voltage_mv": self.voltage_mv,
            "enabled": self.enabled,
            "valid": self.valid,
            "firmware_version": self.firmware_version,
        }

    def get_color(self) -> str:
        """
        Получить цвет индикатора в зависимости от заряда.

        Returns:
            str: "green", "yellow", "red"
        """
        if self.soc > 50:
            return "green"
        elif self.soc > 20:
            return "yellow"
        else:
            return "red"

    def is_low(self, threshold: int = 20) -> bool:
        """
        Проверить низкий заряд.

        Args:
            threshold: Порог (%)

        Returns:
            bool: True если заряд ниже порога
        """
        return self.enabled and self.valid and self.soc < threshold

    def close(self):
        """Закрыть I2C шину"""
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception as error:
                self.logger.warning(f'Failed to close battery I2C bus: {error}')
            self.bus = None
        self.enabled = False
        self.valid = False
