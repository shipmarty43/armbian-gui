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
    Мониторинг батареи через UPS I2C модуль.

    I2C адрес: 0x10 (по умолчанию)
    I2C шина: 3 (по умолчанию для Orange Pi Zero 2W UPS HAT)
    Функции: чтение уровня заряда (%), напряжения (mV)

    Протокол UPS модуля:
    - Регистр 0x03: VCELL_H (старший байт напряжения)
    - Регистр 0x04: VCELL_L (младший байт напряжения)
    - Регистр 0x05: SOC_H (старший байт процента заряда)
    - Регистр 0x06: SOC_L (младший байт процента заряда)

    Формулы:
    - Напряжение (mV) = (((VCELL_H & 0x0F) << 8) + VCELL_L) * 1.25
    - Процент заряда = ((SOC_H << 8) + SOC_L) * 0.003906
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
            i2c_bus: Номер I2C шины (по умолчанию 3 для Orange Pi Zero 2W)
            i2c_address: I2C адрес UPS модуля (по умолчанию 0x10)
            poll_interval: Интервал опроса (секунды)
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.poll_interval = poll_interval
        self.logger = logging.getLogger("cyberdeck.battery")

        self.enabled = False
        self.soc = 0  # State of Charge (%)
        self.voltage = 0.0  # Напряжение (V)
        self.voltage_mv = 0  # Напряжение (mV)
        self.last_update = 0

        if not SMBUS_AVAILABLE:
            self.logger.warning("smbus2 not available, battery monitoring disabled")
            return

        try:
            self.bus = SMBus(i2c_bus)
            # Проверяем доступность UPS модуля
            self.bus.read_byte_data(i2c_address, 0x03)
            self.enabled = True
            self.logger.info(f"UPS Battery monitor initialized on I2C bus {i2c_bus}, address 0x{i2c_address:02X}")
        except Exception as e:
            self.logger.error(f"Failed to initialize UPS battery monitor: {e}")

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

            # Формула из рабочего скрипта: ((SOC_H << 8) + SOC_L) * 0.003906
            soc_raw = (soc_h << 8) + soc_l
            soc = soc_raw * 0.003906

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
        current_time = time.time()

        if (current_time - self.last_update) < self.poll_interval:
            return False

        soc = self.read_soc()
        voltage = self.read_voltage()

        if soc is not None:
            self.soc = soc
        if voltage is not None:
            self.voltage = voltage

        self.last_update = current_time

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
            "enabled": self.enabled
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
        return self.soc < threshold

    def close(self):
        """Закрыть I2C шину"""
        if self.enabled and hasattr(self, 'bus'):
            try:
                self.bus.close()
            except:
                pass
