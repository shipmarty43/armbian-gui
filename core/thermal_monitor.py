"""
Thermal Monitor - мониторинг температуры CPU
"""

import os
import logging
import time
from typing import Dict, List, Optional


class ThermalMonitor:
    """
    Мониторинг температуры процессора.

    Читает данные из /sys/class/thermal/thermal_zone*/temp
    """

    def __init__(
        self,
        zones: List[str] = None,
        poll_interval: int = 2,
        warning_threshold: int = 70,
        critical_threshold: int = 85
    ):
        """
        Инициализация монитора температуры.

        Args:
            zones: Список зон для мониторинга (e.g., ["cpu-thermal"])
            poll_interval: Интервал опроса (секунды)
            warning_threshold: Порог предупреждения (°C)
            critical_threshold: Критический порог (°C)
        """
        if zones is None:
            zones = ["cpu-thermal"]

        self.zones = zones
        self.poll_interval = poll_interval
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.logger = logging.getLogger("cyberdeck.thermal")

        self.temperatures: Dict[str, int] = {}
        self.last_update = 0

        # Найти пути к thermal zones
        self.zone_paths = self._find_zone_paths()
        self.logger.info(
            f"Thermal monitor initialized: {len(self.zone_paths)} zones"
        )

    def _find_zone_paths(self) -> Dict[str, str]:
        """
        Найти пути к thermal zones в /sys.

        Returns:
            Dict[str, str]: {имя_зоны: путь_к_файлу_temp}
        """
        paths = {}
        thermal_base = "/sys/class/thermal"

        if not os.path.exists(thermal_base):
            self.logger.warning(f"Thermal sysfs not found: {thermal_base}")
            return paths

        for entry in os.listdir(thermal_base):
            if not entry.startswith("thermal_zone"):
                continue

            zone_dir = os.path.join(thermal_base, entry)
            type_file = os.path.join(zone_dir, "type")
            temp_file = os.path.join(zone_dir, "temp")

            if not os.path.exists(type_file) or not os.path.exists(temp_file):
                continue

            try:
                with open(type_file, 'r') as f:
                    zone_type = f.read().strip()

                # Проверяем, нужна ли эта зона
                if self.zones and zone_type not in self.zones:
                    continue

                paths[zone_type] = temp_file
                self.logger.debug(f"Found zone: {zone_type} -> {temp_file}")

            except Exception as e:
                self.logger.error(f"Error reading {type_file}: {e}")

        return paths

    def read_temperature(self, zone_name: str) -> Optional[int]:
        """
        Прочитать температуру зоны.

        Args:
            zone_name: Имя зоны

        Returns:
            int or None: Температура в °C
        """
        if zone_name not in self.zone_paths:
            return None

        temp_file = self.zone_paths[zone_name]

        try:
            with open(temp_file, 'r') as f:
                # Температура в millidegrees
                temp_millidegrees = int(f.read().strip())
                temp_celsius = temp_millidegrees // 1000
                return temp_celsius

        except Exception as e:
            self.logger.error(f"Failed to read {temp_file}: {e}")
            return None

    def update(self) -> bool:
        """
        Обновить данные о температуре (если прошёл poll_interval).

        Returns:
            bool: True если данные обновлены
        """
        current_time = time.time()

        if (current_time - self.last_update) < self.poll_interval:
            return False

        for zone_name in self.zone_paths.keys():
            temp = self.read_temperature(zone_name)
            if temp is not None:
                self.temperatures[zone_name] = temp

        self.last_update = current_time

        if self.temperatures:
            self.logger.debug(f"Temperatures: {self.temperatures}")

        return True

    def get_max_temperature(self) -> Optional[int]:
        """
        Получить максимальную температуру среди всех зон.

        Returns:
            int or None: Температура (°C)
        """
        if not self.temperatures:
            return None
        return max(self.temperatures.values())

    def get_status(self) -> Dict[str, any]:
        """
        Получить статус температуры.

        Returns:
            Dict: {"max_temp": int, "zones": Dict, "level": str}
        """
        max_temp = self.get_max_temperature()

        level = "normal"
        if max_temp is not None:
            if max_temp >= self.critical_threshold:
                level = "critical"
            elif max_temp >= self.warning_threshold:
                level = "warning"

        return {
            "max_temp": max_temp,
            "zones": self.temperatures.copy(),
            "level": level
        }

    def get_color(self) -> str:
        """
        Получить цвет индикатора температуры.

        Returns:
            str: "green", "yellow", "orange", "red"
        """
        max_temp = self.get_max_temperature()

        if max_temp is None:
            return "white"

        if max_temp >= self.critical_threshold:
            return "red"
        elif max_temp >= self.warning_threshold:
            return "yellow"
        elif max_temp >= 50:
            return "green"
        else:
            return "green"

    def is_critical(self) -> bool:
        """
        Проверить критическую температуру.

        Returns:
            bool: True если критическая
        """
        max_temp = self.get_max_temperature()
        return max_temp is not None and max_temp >= self.critical_threshold
