"""
Module Loader - динамическая загрузка и управление модулями
"""

import os
import sys
import importlib
import logging
from typing import List, Optional, Dict
from core.base_module import BaseModule


class ModuleLoader:
    """
    Загрузчик модулей.

    Сканирует директории модулей, загружает их динамически
    и управляет жизненным циклом.
    """

    _instance = None

    def __init__(self, module_paths: List[str] = None):
        """
        Инициализация ModuleLoader.

        Args:
            module_paths: Список путей для поиска модулей
        """
        if module_paths is None:
            module_paths = ["modules"]

        self.module_paths = module_paths
        self.modules: Dict[str, BaseModule] = {}
        self.logger = logging.getLogger("cyberdeck.moduleloader")

    @classmethod
    def get_instance(cls, module_paths: List[str] = None) -> 'ModuleLoader':
        """Получить singleton экземпляр"""
        if cls._instance is None:
            cls._instance = cls(module_paths)
        return cls._instance

    def discover_modules(self) -> List[str]:
        """
        Обнаружить доступные модули.

        Returns:
            List[str]: Список имён модулей
        """
        discovered = []

        for base_path in self.module_paths:
            if not os.path.exists(base_path):
                continue

            for module_dir in os.listdir(base_path):
                module_path = os.path.join(base_path, module_dir)

                if not os.path.isdir(module_path):
                    continue

                # Проверяем наличие __init__.py
                init_file = os.path.join(module_path, '__init__.py')
                if os.path.exists(init_file):
                    discovered.append(module_dir)

        self.logger.info(f"Discovered {len(discovered)} modules: {discovered}")
        return discovered

    def load_module(self, module_name: str) -> Optional[BaseModule]:
        """
        Загрузить модуль.

        Args:
            module_name: Имя модуля (имя директории)

        Returns:
            BaseModule or None: Экземпляр модуля
        """
        try:
            # Импортируем модуль
            module_package = f"modules.{module_name}"
            imported = importlib.import_module(module_package)

            # Ищем класс, наследующий BaseModule
            module_class = None
            for attr_name in dir(imported):
                attr = getattr(imported, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, BaseModule) and
                    attr != BaseModule):
                    module_class = attr
                    break

            if module_class is None:
                self.logger.error(
                    f"No BaseModule subclass found in {module_name}"
                )
                return None

            # Создаём экземпляр
            instance = module_class()
            self.logger.info(
                f"Loaded module: {instance.name} v{instance.version} "
                f"(priority: {instance.priority})"
            )

            return instance

        except Exception as e:
            self.logger.error(f"Failed to load module {module_name}: {e}")
            return None

    def load_all_modules(self, priority_order: bool = True) -> List[BaseModule]:
        """
        Загрузить все обнаруженные модули.

        Args:
            priority_order: Сортировать по приоритету (1 = highest)

        Returns:
            List[BaseModule]: Список загруженных модулей
        """
        discovered = self.discover_modules()
        loaded = []

        for module_name in discovered:
            module = self.load_module(module_name)
            if module:
                loaded.append(module)
                self.modules[module.name] = module

                # Вызываем on_load
                try:
                    module.on_load()
                except Exception as e:
                    self.logger.error(
                        f"Error in {module.name}.on_load(): {e}"
                    )

        # Сортировка по приоритету
        if priority_order:
            loaded.sort(key=lambda m: m.priority)

        self.logger.info(f"Loaded {len(loaded)} modules total")
        return loaded

    def get_module(self, module_name: str) -> Optional[BaseModule]:
        """
        Получить загруженный модуль по имени.

        Args:
            module_name: Имя модуля

        Returns:
            BaseModule or None: Экземпляр модуля
        """
        return self.modules.get(module_name)

    def get_all_modules(self) -> List[BaseModule]:
        """
        Получить все загруженные модули.

        Returns:
            List[BaseModule]: Список модулей
        """
        return list(self.modules.values())

    def unload_module(self, module_name: str):
        """
        Выгрузить модуль.

        Args:
            module_name: Имя модуля
        """
        if module_name in self.modules:
            module = self.modules[module_name]

            try:
                module.on_unload()
            except Exception as e:
                self.logger.error(
                    f"Error in {module_name}.on_unload(): {e}"
                )

            del self.modules[module_name]
            self.logger.info(f"Unloaded module: {module_name}")

    def unload_all(self):
        """Выгрузить все модули"""
        module_names = list(self.modules.keys())
        for name in module_names:
            self.unload_module(name)
