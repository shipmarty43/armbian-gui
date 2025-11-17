"""
Base Module API для CyberDeck Interface v2.0

Все модули должны наследовать класс BaseModule и реализовывать
требуемые методы для интеграции с UI и системой.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Callable, Optional, Dict, Any
import yaml
import json
import logging
import os


class BaseModule(ABC):
    """
    Базовый класс для всех модулей CyberDeck Interface.

    Все модули должны наследовать этот класс и реализовывать
    требуемые методы.
    """

    def __init__(self, name: str, version: str, priority: int = 5):
        """
        Инициализация модуля.

        Args:
            name: Имя модуля (отображается в UI)
            version: Версия модуля (semver)
            priority: Приоритет загрузки (1-10, где 1 - наивысший)
        """
        self.name = name
        self.version = version
        self.priority = priority
        self.enabled = True
        self.config = {}
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Настройка логгера модуля"""
        logger = logging.getLogger(f"cyberdeck.{self.name}")
        logger.setLevel(logging.INFO)
        return logger

    # ========== Lifecycle методы ==========

    def on_load(self):
        """
        Вызывается при загрузке модуля.
        Используйте для инициализации железа, загрузки конфига.
        """
        pass

    def on_unload(self):
        """
        Вызывается при выгрузке модуля.
        Используйте для освобождения ресурсов, закрытия устройств.
        """
        pass

    def on_enable(self):
        """Вызывается при включении модуля"""
        self.enabled = True

    def on_disable(self):
        """Вызывается при выключении модуля"""
        self.enabled = False

    # ========== UI методы ==========

    @abstractmethod
    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """
        Возвращает список пунктов меню модуля.

        Returns:
            List[Tuple[str, Callable]]: [(название, функция), ...]

        Example:
            return [
                ("Read Card", self.read_card),
                ("Emulate Card", self.emulate_card),
                ("Settings", self.show_settings),
            ]
        """
        return []

    def get_status_widget(self) -> Optional[str]:
        """
        Виджет для статус-панели (опционально).

        Returns:
            str or None: Текст для отображения в статус-панели

        Example:
            return f"NFC: Ready"
        """
        return None

    def get_hotkeys(self) -> Dict[str, Callable]:
        """
        Горячие клавиши модуля.

        Returns:
            Dict[str, Callable]: {клавиша: функция}

        Example:
            return {
                'r': self.read_card,
                'e': self.emulate_card,
            }
        """
        return {}

    # ========== UI Helper методы ==========

    def show_message(self, message: str, title: str = "Info"):
        """
        Показать информационное сообщение.

        Args:
            message: Текст сообщения
            title: Заголовок окна
        """
        # Реализуется UI менеджером
        from core.ui_manager import UIManager
        UIManager.get_instance().show_message(title, message)

    def show_error(self, message: str):
        """
        Показать сообщение об ошибке.

        Args:
            message: Текст ошибки
        """
        self.show_message(message, title="Error")

    def get_user_input(self, prompt: str, default: str = "") -> str:
        """
        Запросить ввод от пользователя.

        Args:
            prompt: Текст подсказки
            default: Значение по умолчанию

        Returns:
            str: Введённое значение
        """
        from core.ui_manager import UIManager
        return UIManager.get_instance().get_input(prompt, default)

    def show_menu(self, title: str, items: List[str]) -> int:
        """
        Показать меню выбора.

        Args:
            title: Заголовок меню
            items: Список пунктов

        Returns:
            int: Индекс выбранного пункта (-1 если отмена)
        """
        from core.ui_manager import UIManager
        return UIManager.get_instance().show_menu(title, items)

    def show_progress(self, current: int, total: int, message: str = ""):
        """
        Показать прогресс-бар.

        Args:
            current: Текущее значение
            total: Максимальное значение
            message: Сообщение
        """
        from core.ui_manager import UIManager
        UIManager.get_instance().show_progress(current, total, message)

    # ========== Логирование ==========

    def log_info(self, message: str):
        """Логировать информационное сообщение"""
        self.logger.info(message)

    def log_warning(self, message: str):
        """Логировать предупреждение"""
        self.logger.warning(message)

    def log_error(self, message: str):
        """Логировать ошибку"""
        self.logger.error(message)

    def log_debug(self, message: str):
        """Логировать отладочное сообщение"""
        self.logger.debug(message)

    # ========== Конфигурация ==========

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Загрузить YAML конфиг.

        Args:
            config_path: Путь к файлу конфига

        Returns:
            Dict: Конфигурация
        """
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            return self.config
        return {}

    def save_config(self, config: Dict[str, Any], config_path: str):
        """
        Сохранить конфиг.

        Args:
            config: Конфигурация для сохранения
            config_path: Путь к файлу
        """
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

    # ========== Хранение данных ==========

    def save_data(self, filename: str, data: Any, format: str = "json"):
        """
        Сохранить данные в файл.

        Args:
            filename: Имя файла
            data: Данные для сохранения
            format: Формат ("json", "binary", "text")
        """
        if format == "json":
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        elif format == "binary":
            with open(filename, 'wb') as f:
                f.write(data)
        elif format == "text":
            with open(filename, 'w') as f:
                f.write(str(data))

    def load_data(self, filename: str, format: str = "json") -> Any:
        """
        Загрузить данные из файла.

        Args:
            filename: Имя файла
            format: Формат ("json", "binary", "text")

        Returns:
            Any: Загруженные данные
        """
        if not os.path.exists(filename):
            return None

        if format == "json":
            with open(filename, 'r') as f:
                return json.load(f)
        elif format == "binary":
            with open(filename, 'rb') as f:
                return f.read()
        elif format == "text":
            with open(filename, 'r') as f:
                return f.read()

    # ========== Взаимодействие с другими модулями ==========

    def get_module(self, module_name: str) -> Optional['BaseModule']:
        """
        Получить экземпляр другого модуля.

        Args:
            module_name: Имя модуля

        Returns:
            BaseModule or None: Экземпляр модуля
        """
        from core.module_loader import ModuleLoader
        return ModuleLoader.get_instance().get_module(module_name)

    def subscribe_event(self, event_name: str, callback: Callable):
        """
        Подписаться на событие.

        Args:
            event_name: Имя события (e.g., "gps.position_update")
            callback: Функция-обработчик
        """
        from core.event_bus import EventBus
        EventBus.get_instance().subscribe(event_name, callback)

    def emit_event(self, event_name: str, data: Dict[str, Any]):
        """
        Генерировать событие.

        Args:
            event_name: Имя события
            data: Данные события
        """
        from core.event_bus import EventBus
        EventBus.get_instance().emit(event_name, data)
