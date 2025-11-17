"""
Network Monitor - мониторинг WiFi и LTE сигнала
"""

import os
import subprocess
import logging
import time
import re
from typing import Dict, Optional


class NetworkMonitor:
    """
    Мониторинг сетевых интерфейсов.

    - WiFi: сила сигнала, SSID, IP
    - LTE: сила сигнала (через AT команды)
    - Ethernet: статус подключения
    """

    def __init__(
        self,
        wifi_interface: str = "wlan0",
        lte_device: str = "/dev/ttyUSB2",
        poll_interval: int = 5
    ):
        """
        Инициализация монитора сети.

        Args:
            wifi_interface: Интерфейс WiFi
            lte_device: Устройство LTE модема
            poll_interval: Интервал опроса (секунды)
        """
        self.wifi_interface = wifi_interface
        self.lte_device = lte_device
        self.poll_interval = poll_interval
        self.logger = logging.getLogger("cyberdeck.network")

        self.wifi_signal = 0  # 0-4
        self.wifi_ssid = ""
        self.wifi_ip = ""

        self.lte_signal = 0  # 0-5
        self.lte_operator = ""

        self.last_update = 0

    def read_wifi_signal(self) -> Optional[int]:
        """
        Прочитать силу WiFi сигнала.

        Returns:
            int or None: Сила сигнала 0-4 (4 = лучший)
        """
        try:
            # Читаем /proc/net/wireless
            wireless_file = "/proc/net/wireless"
            if not os.path.exists(wireless_file):
                return None

            with open(wireless_file, 'r') as f:
                lines = f.readlines()

            for line in lines:
                if self.wifi_interface in line:
                    # Формат: wlan0: 0000   60.  -50.  -256        0
                    parts = line.split()
                    if len(parts) >= 4:
                        # Качество сигнала (link quality)
                        link_quality_str = parts[2]
                        link_quality = int(link_quality_str.rstrip('.'))

                        # Конвертируем в 0-4
                        signal_bars = min(4, link_quality // 15)
                        return signal_bars

        except Exception as e:
            self.logger.error(f"Failed to read WiFi signal: {e}")

        return None

    def read_wifi_ssid(self) -> str:
        """
        Прочитать SSID подключенной сети.

        Returns:
            str: SSID или пустая строка
        """
        try:
            result = subprocess.check_output(
                ["iwgetid", self.wifi_interface, "-r"],
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            return result.decode().strip()
        except:
            return ""

    def read_wifi_ip(self) -> str:
        """
        Прочитать IP адрес WiFi интерфейса.

        Returns:
            str: IP адрес или пустая строка
        """
        try:
            result = subprocess.check_output(
                ["ip", "-4", "addr", "show", self.wifi_interface],
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            output = result.decode()

            # Ищем inet X.X.X.X
            match = re.search(r'inet\s+([\d.]+)', output)
            if match:
                return match.group(1)

        except:
            pass

        return ""

    def read_lte_signal(self) -> Optional[int]:
        """
        Прочитать силу LTE сигнала через AT команду.

        Returns:
            int or None: Сила сигнала 0-5 (5 = лучший)
        """
        if not os.path.exists(self.lte_device):
            return None

        try:
            # Отправляем AT+CSQ (Signal Quality Report)
            result = subprocess.run(
                ["echo", "-e", "AT+CSQ\\r"],
                stdout=subprocess.PIPE,
                timeout=1,
                check=False
            )

            if result.returncode != 0:
                return None

            # Парсим ответ: +CSQ: <rssi>,<ber>
            output = result.stdout.decode()
            match = re.search(r'\+CSQ:\s*(\d+),', output)

            if match:
                rssi = int(match.group(1))
                # RSSI: 0-31 (99 = не известен)
                if rssi == 99:
                    return 0

                # Конвертируем в 0-5
                signal_bars = min(5, rssi // 6)
                return signal_bars

        except Exception as e:
            self.logger.error(f"Failed to read LTE signal: {e}")

        return None

    def update(self) -> bool:
        """
        Обновить данные о сети (если прошёл poll_interval).

        Returns:
            bool: True если данные обновлены
        """
        current_time = time.time()

        if (current_time - self.last_update) < self.poll_interval:
            return False

        # WiFi
        signal = self.read_wifi_signal()
        if signal is not None:
            self.wifi_signal = signal

        self.wifi_ssid = self.read_wifi_ssid()
        self.wifi_ip = self.read_wifi_ip()

        # LTE
        lte_signal = self.read_lte_signal()
        if lte_signal is not None:
            self.lte_signal = lte_signal

        self.last_update = current_time

        self.logger.debug(
            f"Network: WiFi {self.wifi_signal}/4, "
            f"LTE {self.lte_signal}/5"
        )

        return True

    def get_status(self) -> Dict[str, any]:
        """
        Получить статус сети.

        Returns:
            Dict: Информация о сети
        """
        return {
            "wifi": {
                "signal": self.wifi_signal,
                "ssid": self.wifi_ssid,
                "ip": self.wifi_ip
            },
            "lte": {
                "signal": self.lte_signal,
                "operator": self.lte_operator
            }
        }

    def get_primary_ip(self) -> str:
        """
        Получить основной IP адрес.

        Returns:
            str: IP адрес
        """
        if self.wifi_ip:
            return self.wifi_ip

        # Пробуем eth0
        try:
            result = subprocess.check_output(
                ["ip", "-4", "addr", "show", "eth0"],
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            output = result.decode()
            match = re.search(r'inet\s+([\d.]+)', output)
            if match:
                return match.group(1)
        except:
            pass

        return "N/A"
