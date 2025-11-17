"""
Configuration Loader - загрузка и валидация YAML конфигов
"""

import yaml
import os
import logging
from typing import Dict, Any, Optional


class ConfigLoader:
    """
    Загрузчик конфигурационных файлов.

    Поддерживает загрузку YAML конфигов с валидацией
    и значениями по умолчанию.
    """

    def __init__(self, config_dir: str = "config"):
        """
        Инициализация ConfigLoader.

        Args:
            config_dir: Директория с конфигами
        """
        self.config_dir = config_dir
        self.logger = logging.getLogger("cyberdeck.config")
        self.configs: Dict[str, Dict[str, Any]] = {}

    def load(self, filename: str) -> Dict[str, Any]:
        """
        Загрузить YAML конфиг.

        Args:
            filename: Имя файла (без пути, ищется в config_dir)

        Returns:
            Dict: Загруженная конфигурация
        """
        filepath = os.path.join(self.config_dir, filename)

        if not os.path.exists(filepath):
            self.logger.warning(f"Config file not found: {filepath}")
            return {}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.configs[filename] = config
                self.logger.info(f"Loaded config: {filename}")
                return config
        except Exception as e:
            self.logger.error(f"Failed to load config {filename}: {e}")
            return {}

    def save(self, filename: str, config: Dict[str, Any]):
        """
        Сохранить конфиг в YAML.

        Args:
            filename: Имя файла
            config: Данные для сохранения
        """
        filepath = os.path.join(self.config_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
                self.configs[filename] = config
                self.logger.info(f"Saved config: {filename}")
        except Exception as e:
            self.logger.error(f"Failed to save config {filename}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить значение из главного конфига.

        Args:
            key: Ключ (поддерживает dot-notation: "hardware.battery.enabled")
            default: Значение по умолчанию

        Returns:
            Any: Значение или default
        """
        if "main.yaml" not in self.configs:
            self.load("main.yaml")

        config = self.configs.get("main.yaml", {})
        keys = key.split('.')

        for k in keys:
            if isinstance(config, dict) and k in config:
                config = config[k]
            else:
                return default

        return config

    def validate(self, config: Dict[str, Any]) -> bool:
        """
        Валидация конфига (базовая проверка структуры).

        Args:
            config: Конфигурация для проверки

        Returns:
            bool: True если валиден
        """
        required_keys = ['system', 'hardware']

        for key in required_keys:
            if key not in config:
                self.logger.error(f"Missing required config key: {key}")
                return False

        return True

    def merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Объединить два конфига (override имеет приоритет).

        Args:
            base: Базовая конфигурация
            override: Переопределяющая конфигурация

        Returns:
            Dict: Объединённая конфигурация
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.merge(result[key], value)
            else:
                result[key] = value

        return result
