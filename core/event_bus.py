"""
Event Bus - система pub/sub для обмена событиями между модулями
"""

from typing import Dict, List, Callable, Any
import logging


class EventBus:
    """
    Singleton класс для централизованного управления событиями.

    Модули могут подписываться на события и генерировать их,
    обеспечивая слабую связанность компонентов системы.
    """

    _instance = None

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger("cyberdeck.eventbus")

    @classmethod
    def get_instance(cls) -> 'EventBus':
        """Получить singleton экземпляр"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, event_name: str, callback: Callable):
        """
        Подписаться на событие.

        Args:
            event_name: Имя события (рекомендуется формат "module.event")
            callback: Функция-обработчик callback(data: Dict)
        """
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        self.subscribers[event_name].append(callback)
        self.logger.debug(f"Subscribed to event: {event_name}")

    def unsubscribe(self, event_name: str, callback: Callable):
        """
        Отписаться от события.

        Args:
            event_name: Имя события
            callback: Функция-обработчик для удаления
        """
        if event_name in self.subscribers:
            try:
                self.subscribers[event_name].remove(callback)
                self.logger.debug(f"Unsubscribed from event: {event_name}")
            except ValueError:
                pass

    def emit(self, event_name: str, data: Dict[str, Any]):
        """
        Генерировать событие.

        Args:
            event_name: Имя события
            data: Данные события (словарь)
        """
        self.logger.debug(f"Emitting event: {event_name}")

        if event_name in self.subscribers:
            for callback in self.subscribers[event_name]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(
                        f"Error in event callback for {event_name}: {e}"
                    )

    def clear_all(self):
        """Очистить все подписки (для тестирования)"""
        self.subscribers.clear()
        self.logger.debug("Cleared all event subscriptions")
