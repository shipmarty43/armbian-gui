#!/usr/bin/env python3
"""
CyberDeck Interface v2.0 - Main Entry Point

Мобильная исследовательская платформа на базе Orange Pi
для работы с беспроводными протоколами, NFC/RFID, SDR и пентестингом WiFi.
"""

import sys
import os
import logging
import argparse

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.logger import CyberDeckLogger
from core.config_loader import ConfigLoader
from core.module_loader import ModuleLoader
from core.event_bus import EventBus
from core.battery_monitor import BatteryMonitor
from core.thermal_monitor import ThermalMonitor
from core.network_monitor import NetworkMonitor
from core.ui_manager import UIManager


def parse_args():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='CyberDeck Interface v2.0 - Mobile Security Research Platform'
    )

    parser.add_argument(
        '-c', '--config',
        default='main.yaml',
        help='Path to main configuration file (relative to config/ directory)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Override log level from config'
    )

    parser.add_argument(
        '--no-ui',
        action='store_true',
        help='Run without UI (headless mode)'
    )

    return parser.parse_args()


def main():
    """Главная функция приложения"""

    args = parse_args()

    # 1. Инициализация конфигурации
    config_loader = ConfigLoader()
    config = config_loader.load(args.config)

    if not config:
        print(f"Error: Failed to load config from {args.config}")
        print("Creating default configuration...")
        # TODO: Создать дефолтный конфиг
        return 1

    # 2. Инициализация логгера
    log_level = args.log_level or config.get('system', {}).get('log_level', 'INFO')
    log_path = config.get('system', {}).get('log_path', 'logs/')

    logger_instance = CyberDeckLogger(
        log_dir=log_path,
        log_level=log_level,
        max_size_mb=config.get('system', {}).get('log_rotation', 10)
    )

    logger = logging.getLogger("cyberdeck.main")
    logger.info("="*60)
    logger.info("CyberDeck Interface v2.0 Starting...")
    logger.info("="*60)

    # 3. Инициализация системных мониторов
    battery_monitor = None
    thermal_monitor = None
    network_monitor = None

    # Battery Monitor
    if config.get('hardware', {}).get('battery', {}).get('enabled', False):
        battery_config = config['hardware']['battery']
        battery_monitor = BatteryMonitor(
            i2c_bus=battery_config.get('i2c_bus', 1),
            i2c_address=battery_config.get('i2c_address', 0x36),
            poll_interval=battery_config.get('poll_interval', 5)
        )
        logger.info("Battery monitor initialized")

    # Thermal Monitor
    if config.get('hardware', {}).get('thermal', {}).get('monitoring', True):
        thermal_config = config['hardware']['thermal']
        thermal_monitor = ThermalMonitor(
            zones=thermal_config.get('zones', ['cpu-thermal']),
            poll_interval=thermal_config.get('poll_interval', 2),
            warning_threshold=thermal_config.get('warning_threshold', 70),
            critical_threshold=thermal_config.get('critical_threshold', 85)
        )
        logger.info("Thermal monitor initialized")

    # Network Monitor
    network_config = config.get('network', {})
    wifi_interface = network_config.get('wifi', {}).get('interface', 'wlan0')
    lte_device = network_config.get('lte', {}).get('device', '/dev/ttyUSB2')

    network_monitor = NetworkMonitor(
        wifi_interface=wifi_interface,
        lte_device=lte_device,
        poll_interval=5
    )
    logger.info("Network monitor initialized")

    # 4. Загрузка модулей
    module_paths = config.get('modules', {}).get('paths', ['modules'])
    autoload_modules = config.get('modules', {}).get('autoload', [])
    priority_order = config.get('modules', {}).get('priority_order', True)

    module_loader = ModuleLoader.get_instance(module_paths)
    loaded_modules = module_loader.load_all_modules(priority_order=priority_order)

    logger.info(f"Loaded {len(loaded_modules)} modules")
    for module in loaded_modules:
        logger.info(
            f"  - {module.name} v{module.version} "
            f"(priority: {module.priority})"
        )

    # 5. Инициализация EventBus
    event_bus = EventBus.get_instance()
    logger.info("EventBus initialized")

    # 6. Запуск UI
    if not args.no_ui:
        try:
            ui_manager = UIManager.get_instance(loaded_modules)
            ui_manager.set_monitors(
                battery=battery_monitor,
                thermal=thermal_monitor,
                network=network_monitor
            )

            logger.info("Starting UI...")
            ui_manager.run()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")

        except Exception as e:
            logger.error(f"UI error: {e}", exc_info=True)
            return 1

    else:
        # Headless mode
        logger.info("Running in headless mode (no UI)")
        logger.info("Press Ctrl+C to exit...")

        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")

    # 7. Cleanup
    logger.info("Shutting down...")

    # Выгрузить модули
    module_loader.unload_all()

    # Закрыть мониторы
    if battery_monitor:
        battery_monitor.close()

    # Закрыть логгер
    logger_instance.close()

    logger.info("CyberDeck Interface stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
