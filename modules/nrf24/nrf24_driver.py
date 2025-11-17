#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nRF24L01+ Driver для Orange Pi
Сканирование и джамминг 2.4 ГГц диапазона
"""

import spidev
import time
import logging
from typing import List, Optional
from collections import deque

try:
    import OPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# Константы nRF24L01+
NRF24_CONFIG = 0x00
NRF24_EN_AA = 0x01
NRF24_EN_RXADDR = 0x02
NRF24_SETUP_AW = 0x03
NRF24_SETUP_RETR = 0x04
NRF24_RF_CH = 0x05
NRF24_RF_SETUP = 0x06
NRF24_STATUS = 0x07
NRF24_OBSERVE_TX = 0x08
NRF24_RPD = 0x09  # Received Power Detector
NRF24_TX_ADDR = 0x10
NRF24_RX_PW_P0 = 0x11
NRF24_FIFO_STATUS = 0x17
NRF24_DYNPD = 0x1C
NRF24_FEATURE = 0x1D

# Команды
NRF24_R_REGISTER = 0x00
NRF24_W_REGISTER = 0x20
NRF24_W_TX_PAYLOAD = 0xA0
NRF24_FLUSH_RX = 0xE2
NRF24_FLUSH_TX = 0xE1
NRF24_REUSE_TX_PL = 0xE3

# Биты конфигурации
NRF24_PWR_UP = 0x02
NRF24_PRIM_RX = 0x01
NRF24_MASK_MAX_RT = 0x10
NRF24_MASK_TX_DS = 0x20
NRF24_MASK_RX_DR = 0x40
NRF24_EN_CRC = 0x08
NRF24_CRCO = 0x04

# Биты RF_SETUP для LNA
NRF24_LNA_HCURR = 0x01  # Бит 0 - включение высокого усиления LNA
NRF24_CONT_WAVE = 0x80  # Бит 7 - непрерывная несущая
NRF24_PLL_LOCK = 0x10   # Бит 4 - PLL lock для carrier wave

# Биты FIFO_STATUS
NRF24_TX_FULL = 0x20


class NRF24Spectrum:
    """nRF24L01+ спектроанализатор и джаммер для 2.4 ГГц"""

    def __init__(self, ce_pin: int = 7, spi_bus: int = 0, spi_device: int = 0,
                 lna_enable: bool = True, pa_level: int = 3):
        """
        Инициализация спектроанализатора

        Args:
            ce_pin: GPIO пин для CE (по умолчанию PA7)
            spi_bus: SPI шина (обычно 0)
            spi_device: SPI устройство (обычно 0)
            lna_enable: Включить LNA для повышения чувствительности
            pa_level: Уровень мощности PA (0-3):
                     0: -18 dBm (минимум)
                     1: -12 dBm (низкий)
                     2: -6 dBm (средний)
                     3: 0 dBm (высокий для обычного) / +20 dBm (для PA модуля)
        """
        self.logger = logging.getLogger("cyberdeck.nrf24")

        if not GPIO_AVAILABLE:
            self.logger.error("OPi.GPIO not available")
            self.enabled = False
            return

        self.ce_pin = ce_pin
        self.lna_enable = lna_enable
        self.pa_level = pa_level
        self.enabled = False

        # Настройка GPIO
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.ce_pin, GPIO.OUT)
        GPIO.output(self.ce_pin, GPIO.LOW)

        # Настройка SPI
        self.spi = spidev.SpiDev()
        try:
            self.spi.open(spi_bus, spi_device)
            self.spi.max_speed_hz = 8000000
            self.spi.mode = 0
        except Exception as e:
            self.logger.error(f"Failed to open SPI: {e}")
            self.enabled = False
            return

        # Диапазон каналов (0-125, что соответствует 2400-2525 МГц)
        self.num_channels = 126

        # Инициализация радиомодуля
        self.init_radio()
        self.enabled = True

    def write_register(self, reg: int, value: int):
        """Запись в регистр"""
        if isinstance(value, list):
            return self.spi.xfer2([NRF24_W_REGISTER | reg] + value)
        else:
            return self.spi.xfer2([NRF24_W_REGISTER | reg, value])

    def read_register(self, reg: int, length: int = 1):
        """Чтение регистра"""
        data = self.spi.xfer2([NRF24_R_REGISTER | reg] + [0xFF] * length)
        return data[1] if length == 1 else data[1:]

    def ce_high(self):
        """CE в HIGH"""
        GPIO.output(self.ce_pin, GPIO.HIGH)

    def ce_low(self):
        """CE в LOW"""
        GPIO.output(self.ce_pin, GPIO.LOW)

    def init_radio(self):
        """Инициализация радиомодуля для работы в режиме сканирования"""
        time.sleep(0.1)  # Задержка после включения питания

        # Сброс
        self.ce_low()

        # Выключаем автоподтверждение
        self.write_register(NRF24_EN_AA, 0x00)

        # Настраиваем RF: 2 Mbps, заданная мощность + LNA
        rf_setup = 0x08 | (self.pa_level << 1)  # 2Mbps + уровень мощности
        if self.lna_enable:
            rf_setup |= NRF24_LNA_HCURR  # Включаем LNA (бит 0)

        self.write_register(NRF24_RF_SETUP, rf_setup)

        # Включаем RX режим с питанием
        self.write_register(NRF24_CONFIG, NRF24_PWR_UP | NRF24_PRIM_RX)

        # Очистка FIFO
        self.spi.xfer2([NRF24_FLUSH_RX])
        self.spi.xfer2([NRF24_FLUSH_TX])

        time.sleep(0.005)  # Время на включение (5 мс)

        # Проверяем настройку
        rf_value = self.read_register(NRF24_RF_SETUP)
        lna_status = "включен" if (rf_value & NRF24_LNA_HCURR) else "выключен"
        pa_bits = (rf_value >> 1) & 0x03

        self.logger.info(f"nRF24L01+ инициализирован")
        self.logger.info(f"  RF_SETUP: 0x{rf_value:02X}, LNA: {lna_status}, PA level: {pa_bits}")

    def scan_channel(self, channel: int) -> bool:
        """
        Сканирование одного канала

        Args:
            channel: номер канала (0-125)

        Returns:
            True если обнаружена активность
        """
        # Устанавливаем канал
        self.write_register(NRF24_RF_CH, channel)

        # Запускаем прием
        self.ce_high()
        time.sleep(0.0001)  # 100 мкс на прием
        self.ce_low()

        # Читаем RPD (Received Power Detector)
        rpd = self.read_register(NRF24_RPD)

        return rpd > 0

    def scan_spectrum(self) -> List[int]:
        """
        Сканирование всего спектра

        Returns:
            список активности по каналам (0-125)
        """
        spectrum = []
        for channel in range(self.num_channels):
            active = self.scan_channel(channel)
            spectrum.append(1 if active else 0)
        return spectrum

    def setup_jamming_mode(self):
        """Настройка модуля для режима джамминга"""
        # 1. Disable AutoAck
        self.write_register(NRF24_EN_AA, 0x00)

        # 2. Disable retries
        self.write_register(NRF24_SETUP_RETR, 0x00)

        # 3. Set address width to 3 bytes
        self.write_register(NRF24_SETUP_AW, 0x01)  # 3 bytes

        # 4. Set payload size to 5 bytes
        self.write_register(NRF24_RX_PW_P0, 0x05)

        # 5. Disable CRC (ВАЖНО для джамминга!)
        config = NRF24_PWR_UP  # Только питание, без CRC, без PRIM_RX (TX mode)
        self.write_register(NRF24_CONFIG, config)

        # 6. Set PA level to maximum and data rate to 2 Mbps
        rf_setup = (1 << 3) | (self.pa_level << 1)  # bit 3 = RF_DR_HIGH, bits 2-1 = RF_PWR
        if self.lna_enable:
            rf_setup |= NRF24_LNA_HCURR
        self.write_register(NRF24_RF_SETUP, rf_setup)

        # 7. Clear FIFOs
        self.spi.xfer2([NRF24_FLUSH_TX])
        self.spi.xfer2([NRF24_FLUSH_RX])

        time.sleep(0.002)  # 2 мс

        self.logger.info("Режим джамминга настроен")

    def restore_normal_mode(self):
        """Восстановление нормального режима после джамминга"""
        self.write_register(NRF24_EN_AA, 0x00)
        self.write_register(NRF24_SETUP_RETR, 0x00)
        self.write_register(NRF24_SETUP_AW, 0x03)  # 5 bytes address

        # Включаем RX режим
        config = NRF24_PWR_UP | NRF24_PRIM_RX
        self.write_register(NRF24_CONFIG, config)

        # Восстанавливаем RF_SETUP
        rf_setup = 0x08 | (self.pa_level << 1)
        if self.lna_enable:
            rf_setup |= NRF24_LNA_HCURR
        self.write_register(NRF24_RF_SETUP, rf_setup)

        time.sleep(0.005)
        self.logger.info("Возврат в нормальный режим")

    def start_carrier_wave(self, channel: int):
        """Запуск непрерывной несущей на канале"""
        self.write_register(NRF24_RF_CH, channel)

        rf_setup = self.read_register(NRF24_RF_SETUP)
        rf_setup |= 0x90  # CONT_WAVE + PLL_LOCK
        self.write_register(NRF24_RF_SETUP, rf_setup)

        self.ce_high()
        time.sleep(0.00015)  # 150 мкс

    def stop_carrier_wave(self):
        """Остановка непрерывной несущей"""
        self.ce_low()

        rf_setup = self.read_register(NRF24_RF_SETUP)
        rf_setup &= ~(NRF24_CONT_WAVE | NRF24_PLL_LOCK)
        self.write_register(NRF24_RF_SETUP, rf_setup)

    def jam_channel(self, channel: int, duration: float = 0, continuous: bool = True):
        """
        Джамминг одного канала

        Args:
            channel: номер канала (0-125)
            duration: длительность джамминга (0 = мгновенная смена канала)
            continuous: режим непрерывной несущей
        """
        if continuous:
            # Быстрая смена канала
            self.write_register(NRF24_RF_CH, channel)
            if duration > 0:
                time.sleep(duration)
        else:
            # Пакетный режим
            self.write_register(NRF24_RF_CH, channel)

            payload = [0xFF] * 5
            self.spi.xfer2([NRF24_W_TX_PAYLOAD] + payload)

            self.ce_high()
            time.sleep(0.000015)  # 15 мкс
            self.ce_low()

            if duration > 0:
                time.sleep(duration)
            else:
                time.sleep(0.000010)  # 10 мкс минимум

            self.spi.xfer2([NRF24_FLUSH_TX])

    def jam_spectrum(self, channels: Optional[List[int]] = None, hop_delay: float = 0,
                    mode: str = 'continuous', ble_priority: bool = True,
                    callback = None) -> dict:
        """
        Джамминг диапазона каналов с частотным скачком

        Args:
            channels: список каналов для джамминга (None = все Bluetooth каналы)
            hop_delay: задержка между переключениями каналов
            mode: 'continuous' (несущая) или 'packet' (пакеты)
            ble_priority: приоритет BLE рекламным каналам 37, 38, 39
            callback: функция для остановки (должна возвращать True для остановки)

        Returns:
            Статистика джамминга
        """
        if channels is None:
            channels = list(range(2, 81))  # Все 79 Bluetooth каналов

        ble_adv_channels = [37, 38, 39]
        continuous = (mode == 'continuous')

        self.setup_jamming_mode()

        if continuous:
            self.start_carrier_wave(channels[0])

        jam_count = 0
        start_time = time.time()

        try:
            while True:
                # Проверка callback для остановки
                if callback and callback():
                    break

                # Быстрое переключение по всем каналам
                for channel in channels:
                    self.write_register(NRF24_RF_CH, channel)
                    jam_count += 1
                    if hop_delay > 0:
                        time.sleep(hop_delay)

                    if callback and callback():
                        break

                # Приоритет BLE
                if ble_priority:
                    for ble_ch in ble_adv_channels:
                        self.write_register(NRF24_RF_CH, ble_ch)
                        jam_count += 1
                        if hop_delay > 0:
                            time.sleep(hop_delay * 2)

                        if callback and callback():
                            break

        except KeyboardInterrupt:
            pass
        finally:
            if continuous:
                self.stop_carrier_wave()

            self.restore_normal_mode()

        duration = time.time() - start_time

        return {
            'jam_count': jam_count,
            'duration': duration,
            'channels_per_sec': jam_count / duration if duration > 0 else 0
        }

    def cleanup(self):
        """Освобождение ресурсов"""
        self.ce_low()
        if self.spi:
            self.spi.close()
        if GPIO_AVAILABLE:
            GPIO.cleanup()
        self.logger.info("nRF24 ресурсы освобождены")
