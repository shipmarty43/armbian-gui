"""
Module Loader - динамическая загрузка и управление модулями
"""

import os
import sys
import importlib
import importlib.util
from pathlib import Path
import logging
from typing import List, Optional, Dict
from core.base_module import BaseModule
from core.hardware_config import hardware_errors, module_settings


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
        self.status = {}
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
            if not module_name.isidentifier():
                raise ValueError('Module name must be a Python identifier')
            module_package = f"modules.{module_name}"
            source = next((Path(base) / module_name / '__init__.py'
                           for base in self.module_paths
                           if (Path(base) / module_name / '__init__.py').is_file()), None)
            if source is None:
                raise ImportError(f'{module_name} not found in configured module paths')
            source = source.resolve()
            imported = sys.modules.get(module_package)
            if imported is not None and Path(imported.__file__).resolve() != source:
                raise ImportError(f'{module_package} already imported from another path; restart to change paths')
            if imported is None:
                importlib.import_module('modules')
                spec = importlib.util.spec_from_file_location(module_package, source,
                    submodule_search_locations=[str(source.parent)])
                imported = importlib.util.module_from_spec(spec)
                sys.modules[module_package] = imported
                try:
                    spec.loader.exec_module(imported)
                except BaseException:
                    for key in list(sys.modules):
                        if key == module_package or key.startswith(module_package + '.'):
                            del sys.modules[key]
                    raise

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

    def load_all_modules(self, priority_order: bool = True,
                         module_names: Optional[List[str]] = None,
                         config: Optional[Dict] = None) -> List[BaseModule]:
        """
        Загрузить все обнаруженные модули.

        Args:
            priority_order: Сортировать по приоритету (1 = highest)
            module_names: None discovers all; an empty list loads none.
            config: Application configuration supplied before on_load.

        Returns:
            List[BaseModule]: Список загруженных модулей
        """
        discovered = (self.discover_modules() if module_names is None
                      else list(dict.fromkeys(module_names)))
        loaded = []
        config = config if config is not None else {}
        errors = hardware_errors(config, discovered)

        for module_name in discovered:
            if module_name in self.modules:
                loaded.append(self.modules[module_name])
                continue
            if module_name in errors:
                self.status[module_name] = '; '.join(errors[module_name])
                self.logger.error('%s: %s', module_name, self.status[module_name])
                continue
            if module_settings(config, module_name).get('enabled') is False:
                self.status[module_name] = 'disabled in configuration'
                continue
            module = self.load_module(module_name)
            if module:
                loaded.append(module)
                module.config = config
                module.module_id = module_name
            else:
                self.status[module_name] = "import failed or module not found"

        # Сортировка по приоритету
        if priority_order:
            loaded.sort(key=lambda m: m.priority)

        initialized = []
        for module in loaded:
            module_id = getattr(module, 'module_id', module.name)
            if module_id in self.modules:
                initialized.append(module)
                continue
            try:
                module.on_load()
                ready = module.enabled and (not hasattr(module, 'hardware_enabled') or module.hardware_enabled)
            except BaseException as exc:
                self.status[module_id] = str(exc) or type(exc).__name__
                self.logger.error('Error in %s.on_load(): %s', module.name, exc)
                self._dispose(module)
                if not isinstance(exc, Exception):
                    raise
                continue
            if not ready:
                self.status[module_id] = 'hardware unavailable or initialization failed'
                self._dispose(module)
                continue
            self.status[module_id] = 'initialized (hardware operation not verified)'
            self.modules[module_id] = module
            initialized.append(module)

        self.logger.info(f"Loaded {len(initialized)} modules total")
        return initialized

    def get_module(self, module_name: str) -> Optional[BaseModule]:
        """
        Получить загруженный модуль по имени.

        Args:
            module_name: Имя модуля

        Returns:
            BaseModule or None: Экземпляр модуля
        """
        return self.modules.get(module_name) or next(
            (m for m in self.modules.values() if m.name == module_name), None)

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

            self._dispose(module)
            del self.modules[module_name]
            self.logger.info(f"Unloaded module: {module_name}")

    def _dispose(self, module):
        try:
            module.on_unload()
        except Exception:
            self.logger.exception('Error cleaning up %s', module.name)
        finally:
            module.release_subscriptions()
            module.enabled = False
            if hasattr(module, 'hardware_enabled'):
                module.hardware_enabled = False

    def unload_all(self):
        """Выгрузить все модули"""
        module_names = list(reversed(self.modules))
        for name in module_names:
            self.unload_module(name)
