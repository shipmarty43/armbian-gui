"""
Logger System - централизованное логирование всех сеансов работы
"""

import logging
import os
from datetime import datetime
from typing import Optional


class CyberDeckLogger:
    """
    Централизованная система логирования.

    Логирует все действия в файлы сеансов с ротацией.
    """

    _instance = None

    def __init__(
        self,
        log_dir: str = "logs",
        log_level: str = "INFO",
        max_size_mb: int = 10
    ):
        """
        Инициализация логгера.

        Args:
            log_dir: Директория для логов
            log_level: Уровень логирования
            max_size_mb: Максимальный размер файла лога (MB)
        """
        self.log_dir = log_dir
        self.max_size_bytes = max_size_mb * 1024 * 1024

        # Создаём директорию если не существует
        os.makedirs(log_dir, exist_ok=True)

        # Имя файла с текущей сессией
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"session_{timestamp}.log")

        # Настройка root logger
        self._setup_logging(log_level)

    @classmethod
    def get_instance(cls, **kwargs) -> 'CyberDeckLogger':
        """Получить singleton экземпляр"""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    def _setup_logging(self, log_level: str):
        """
        Настроить logging систему Python.

        Args:
            log_level: Уровень логирования
        """
        # Формат логов
        log_format = (
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        date_format = '%Y-%m-%d %H:%M:%S'

        # Настройка root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))

        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setFormatter(
            logging.Formatter(log_format, date_format)
        )
        root_logger.addHandler(file_handler)

        # Console handler (опционально, для отладки)
        # console_handler = logging.StreamHandler()
        # console_handler.setFormatter(
        #     logging.Formatter(log_format, date_format)
        # )
        # root_logger.addHandler(console_handler)

        logging.info("=" * 60)
        logging.info("CyberDeck Interface - Session Started")
        logging.info("=" * 60)

    def rotate_if_needed(self):
        """Проверить размер лога и создать новый если превышен лимит"""
        if not os.path.exists(self.log_file):
            return

        file_size = os.path.getsize(self.log_file)
        if file_size > self.max_size_bytes:
            logging.info("Log file size limit reached, rotating...")

            # Создаём новый файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_log_file = os.path.join(
                self.log_dir,
                f"session_{timestamp}.log"
            )

            # Переключаем handlers
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
                    root_logger.removeHandler(handler)

            # Создаём новый handler
            file_handler = logging.FileHandler(new_log_file, encoding='utf-8')
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    '%Y-%m-%d %H:%M:%S'
                )
            )
            root_logger.addHandler(file_handler)

            self.log_file = new_log_file
            logging.info("Log rotated to new file")

    def get_log_file(self) -> str:
        """
        Получить путь к текущему файлу лога.

        Returns:
            str: Путь к файлу
        """
        return self.log_file

    def get_recent_logs(self, lines: int = 100) -> str:
        """
        Получить последние N строк из лога.

        Args:
            lines: Количество строк

        Returns:
            str: Содержимое
        """
        if not os.path.exists(self.log_file):
            return ""

        with open(self.log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent)

    def cleanup_old_logs(self, keep_days: int = 7):
        """
        Удалить старые логи.

        Args:
            keep_days: Сколько дней хранить
        """
        if not os.path.exists(self.log_dir):
            return

        current_time = datetime.now().timestamp()
        max_age = keep_days * 24 * 60 * 60  # секунды

        for filename in os.listdir(self.log_dir):
            if not filename.startswith("session_"):
                continue

            filepath = os.path.join(self.log_dir, filename)
            file_time = os.path.getmtime(filepath)

            if (current_time - file_time) > max_age:
                try:
                    os.remove(filepath)
                    logging.info(f"Deleted old log: {filename}")
                except Exception as e:
                    logging.error(f"Failed to delete {filename}: {e}")

    def close(self):
        """Закрыть логгер (вызывается при завершении программы)"""
        logging.info("=" * 60)
        logging.info("CyberDeck Interface - Session Ended")
        logging.info("=" * 60)

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
