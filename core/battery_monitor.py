"""
Battery Monitor - мониторинг батареи через MAX17043 (I2C)
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
    Мониторинг батареи через MAX17043.

    I2C адрес: 0x36
    Функции: чтение уровня заряда (%), напряжения
    """

    def __init__(
        self,
        i2c_bus: int = 1,
        i2c_address: int = 0x36,
        poll_interval: int = 5
    ):
        """
        Инициализация монитора батареи.

        Args:
            i2c_bus: Номер I2C шины
            i2c_address: I2C адрес MAX17043
            poll_interval: Интервал опроса (секунды)
        """
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.poll_interval = poll_interval
        self.logger = logging.getLogger("cyberdeck.battery")

        self.enabled = False
        self.soc = 0  # State of Charge (%)
        self.voltage = 0.0  # Напряжение (V)
        self.last_update = 0

        if not SMBUS_AVAILABLE:
            self.logger.warning("smbus2 not available, battery monitoring disabled")
            return

        try:
            self.bus = SMBus(i2c_bus)
            self.enabled = True
            self.logger.info(f"Battery monitor initialized on I2C bus {i2c_bus}")
        except Exception as e:
            self.logger.error(f"Failed to initialize battery monitor: {e}")

    def read_soc(self) -> Optional[int]:
        """
        Прочитать State of Charge (уровень заряда).

        Returns:
            int or None: Процент заряда (0-100)
        """
        if not self.enabled:
            return None

        try:
            # Регистр SOC: 0x04 (2 байта)
            data = self.bus.read_i2c_block_data(self.i2c_address, 0x04, 2)
            soc_raw = (data[0] << 8) | data[1]
            soc = soc_raw / 256.0  # MAX17043 возвращает в 1/256%

            return int(soc)

        except Exception as e:
            self.logger.error(f"Failed to read SOC: {e}")
            return None

    def read_voltage(self) -> Optional[float]:
        """
        Прочитать напряжение батареи.

        Returns:
            float or None: Напряжение (V)
        """
        if not self.enabled:
            return None

        try:
            # Регистр VCELL: 0x02 (2 байта)
            data = self.bus.read_i2c_block_data(self.i2c_address, 0x02, 2)
            vcell_raw = (data[0] << 8) | data[1]
            voltage = vcell_raw * 78.125 / 1000000.0  # LSB = 78.125μV

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

        self.logger.debug(f"Battery: {self.soc}%, {self.voltage}V")
        return True

    def get_status(self) -> Dict[str, any]:
        """
        Получить текущий статус батареи.

        Returns:
            Dict: {"soc": int, "voltage": float, "enabled": bool}
        """
        return {
            "soc": self.soc,
            "voltage": self.voltage,
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
