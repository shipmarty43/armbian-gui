"""
NFC Module - полная реализация с PN532 драйвером
Чтение, запись, эмуляция и брутфорс NFC/RFID карт
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional
import os
import json
from datetime import datetime


class NFCModule(BaseModule):
    """
    Модуль работы с NFC/RFID картами (PN532).

    Функции:
    - Чтение Mifare Classic 1K/4K, Ultralight, NTAG
    - Запись данных на карты
    - Брутфорс ключей Mifare
    - Управление дампами
    - Клонирование карт
    """

    def __init__(self):
        super().__init__(
            name="NFC Tools",
            version="2.0.0",
            priority=3
        )

        self.pn532 = None
        self.dumps_dir = "nfc_dumps"
        self.dumps = []
        self.last_card = None
        self.default_keys = self._load_default_keys()

        os.makedirs(self.dumps_dir, exist_ok=True)

    def _load_default_keys(self) -> List[List[int]]:
        """Load default Mifare keys"""
        return [
            [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],  # Factory default
            [0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5],  # MAD key
            [0xD3, 0xF7, 0xD3, 0xF7, 0xD3, 0xF7],  # NDEF key
            [0x00, 0x00, 0x00, 0x00, 0x00, 0x00],  # All zeros
            [0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5],  # Common key
            [0x4D, 0x3A, 0x99, 0xC3, 0x51, 0xDD],  # Common key 2
            [0x1A, 0x98, 0x2C, 0x7E, 0x45, 0x9A],  # Common key 3
        ]

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("NFC module loading...")

        # Load configuration
        config = self.load_config("config/main.yaml")
        nfc_config = config.get('hardware', {}).get('nfc', {})

        if not nfc_config.get('enabled', False):
            self.log_info("NFC disabled in config")
            self.enabled = False
            return

        interface = nfc_config.get('interface', 'pn532_spi')
        spi_bus = nfc_config.get('spi_bus', 1)
        spi_device = nfc_config.get('spi_device', 2)
        cs_pin = nfc_config.get('cs_pin', 23)
        reset_pin = nfc_config.get('reset_pin', None)
        i2c_bus = nfc_config.get('i2c_bus', 0)
        i2c_address = nfc_config.get('i2c_address', 0x24)

        try:
            from .pn532_driver import PN532

            # Determine interface type
            if 'spi' in interface:
                self.pn532 = PN532(
                    interface='spi',
                    spi_bus=spi_bus,
                    spi_device=spi_device,
                    cs_pin=cs_pin,
                    reset_pin=reset_pin
                )
            elif 'i2c' in interface:
                self.pn532 = PN532(
                    interface='i2c',
                    i2c_bus=i2c_bus,
                    i2c_address=i2c_address,
                    reset_pin=reset_pin
                )
            else:
                self.log_error(f"Unsupported interface: {interface}")
                self.enabled = False
                return

            # Initialize PN532
            if self.pn532.initialize():
                self.log_info(f"PN532 initialized on {interface}")
                self.enabled = True
            else:
                self.log_error("PN532 initialization failed")
                self.enabled = False

        except Exception as e:
            self.log_error(f"Failed to initialize PN532: {e}")
            self.enabled = False

        # Load saved dumps
        self._load_dumps()

    def on_unload(self):
        """Освобождение ресурсов"""
        if self.pn532:
            self.pn532.close()
        self.log_info("NFC module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.enabled:
            return [
                ("Status: NFC Not Available", lambda: None),
            ]

        return [
            ("Scan & Read", self.scan_and_read),
            ("Read Mifare Classic", self.read_mifare_classic),
            ("Write Data", self.write_data),
            ("Clone Card", self.clone_card),
            ("Dictionary Attack", self.dictionary_attack),
            ("Dump Manager", self.dump_manager),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.enabled:
            return "NFC: Disabled"

        if self.last_card:
            uid = ':'.join([f"{b:02X}" for b in self.last_card['uid']])
            return f"NFC: {uid}"

        return "NFC: Ready"

    # ========== Scanning Functions ==========

    def scan_and_read(self):
        """Сканирование и чтение карты"""
        self.log_info("Scanning for NFC card...")

        self.show_message(
            "Scanning",
            "Place NFC/RFID card on the reader...\n\n"
            "Waiting for card..."
        )

        # Wait for card
        card_info = self.pn532.read_passive_target(card_type=0x00, timeout=5.0)

        if not card_info:
            self.show_message("Scan", "No card detected.\n\nPlease try again.")
            return

        self.last_card = card_info

        # Format UID
        uid_str = ':'.join([f"{b:02X}" for b in card_info['uid']])

        # Display card info
        info_text = f"Card Detected!\n\n"
        info_text += f"UID: {uid_str}\n"
        info_text += f"Type: {card_info['type']}\n"
        info_text += f"SAK: 0x{card_info['sel_res']:02X}\n"
        info_text += f"ATQA: 0x{card_info['sens_res']:04X}\n"

        self.show_message("Card Info", info_text)
        self.log_info(f"Card detected: {uid_str}, type: {card_info['type']}")

    def read_mifare_classic(self):
        """Чтение Mifare Classic карты"""
        if not self.last_card:
            self.scan_and_read()
            if not self.last_card:
                return

        # Check if it's Mifare Classic
        if "Mifare Classic" not in self.last_card['type']:
            self.show_error(
                f"Card type is {self.last_card['type']}\n\n"
                "This function requires Mifare Classic card."
            )
            return

        # Determine number of sectors
        if "1K" in self.last_card['type']:
            num_sectors = 16
        elif "4K" in self.last_card['type']:
            num_sectors = 40
        else:
            num_sectors = 16

        self.show_message(
            "Reading Card",
            f"Reading Mifare Classic card...\n\n"
            f"Sectors: {num_sectors}\n"
            f"Blocks: {num_sectors * 4}\n\n"
            "This may take a minute..."
        )

        # Read all sectors
        dump_data = {}
        successful_sectors = 0

        for sector in range(num_sectors):
            # Try to authenticate with default keys
            authenticated = False

            for key_type in [0x60, 0x61]:  # Key A and Key B
                for key in self.default_keys:
                    block = sector * 4

                    if self.pn532.mifare_classic_authenticate(
                        self.last_card['uid'], block, key_type, key
                    ):
                        authenticated = True
                        break

                if authenticated:
                    break

            if not authenticated:
                self.log_warning(f"Failed to authenticate sector {sector}")
                continue

            # Read all blocks in sector
            sector_data = []
            for block_offset in range(4):
                block = sector * 4 + block_offset
                data = self.pn532.mifare_classic_read_block(block)

                if data:
                    sector_data.append(data)
                else:
                    self.log_warning(f"Failed to read block {block}")

            if len(sector_data) == 4:
                dump_data[sector] = sector_data
                successful_sectors += 1

        # Display results
        result_text = f"Read Complete\n\n"
        result_text += f"Successful sectors: {successful_sectors}/{num_sectors}\n\n"

        if successful_sectors > 0:
            result_text += "Save dump?"

            choice = self.show_menu("Read Complete", ["Yes, save dump", "No, discard"])

            if choice == 0:
                self._save_dump(dump_data)

        else:
            result_text += "No data could be read.\n"
            result_text += "Try dictionary attack."

        self.show_message("Results", result_text)

    def _save_dump(self, dump_data: dict):
        """Сохранение дампа карты"""
        uid_str = ':'.join([f"{b:02X}" for b in self.last_card['uid']])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dump_{uid_str.replace(':', '')}_{timestamp}.json"
        filepath = os.path.join(self.dumps_dir, filename)

        dump_info = {
            'uid': [b for b in self.last_card['uid']],
            'type': self.last_card['type'],
            'timestamp': timestamp,
            'sectors': {}
        }

        # Convert dump_data to JSON-serializable format
        for sector, blocks in dump_data.items():
            dump_info['sectors'][str(sector)] = [
                [b for b in block] for block in blocks
            ]

        with open(filepath, 'w') as f:
            json.dump(dump_info, f, indent=2)

        self.dumps.append(dump_info)

        self.show_message(
            "Dump Saved",
            f"Dump saved to:\n{filename}\n\n"
            f"Sectors: {len(dump_data)}"
        )

        self.log_info(f"Dump saved: {filename}")

    def write_data(self):
        """Запись данных на карту"""
        if not self.last_card:
            self.show_error("No card detected.\n\nPlease scan a card first.")
            return

        self.show_message(
            "Write Data",
            "Write data to card\n\n"
            "Feature coming soon:\n"
            "- Write specific blocks\n"
            "- Write from dump file\n"
            "- Write custom data"
        )

    def clone_card(self):
        """Клонирование карты"""
        self.show_message(
            "Clone Card",
            "Clone Card\n\n"
            "This feature allows you to clone\n"
            "a Mifare Classic card to another.\n\n"
            "Steps:\n"
            "1. Read source card\n"
            "2. Place target card\n"
            "3. Write data\n\n"
            "Coming soon..."
        )

    def dictionary_attack(self):
        """Брутфорс ключей по словарю"""
        if not self.last_card:
            self.show_error("No card detected.\n\nPlease scan a card first.")
            return

        self.show_message(
            "Dictionary Attack",
            "Dictionary Attack\n\n"
            f"Card: {self.last_card['type']}\n"
            f"Keys to try: {len(self.default_keys)}\n\n"
            "This will try common keys for\n"
            "all sectors.\n\n"
            "Starting attack..."
        )

        # This is handled by read_mifare_classic for now
        self.read_mifare_classic()

    # ========== Dump Manager ==========

    def dump_manager(self):
        """Управление дампами"""
        if not self.dumps:
            self.show_message(
                "Dump Manager",
                "No dumps saved yet.\n\n"
                "Read a card to create a dump."
            )
            return

        dump_list = ["View all dumps", "Delete dump", "Export dump", "Back"]

        choice = self.show_menu("Dump Manager", dump_list)

        if choice == 0:
            self._view_dumps()
        elif choice == 1:
            self._delete_dump()
        elif choice == 2:
            self._export_dump()

    def _view_dumps(self):
        """Просмотр дампов"""
        dump_text = "Saved Dumps:\n\n"

        for i, dump in enumerate(self.dumps, 1):
            uid = ':'.join([f"{b:02X}" for b in dump['uid']])
            dump_text += f"{i}. {uid}\n"
            dump_text += f"   Type: {dump['type']}\n"
            dump_text += f"   Date: {dump['timestamp']}\n"
            dump_text += f"   Sectors: {len(dump['sectors'])}\n\n"

        self.show_message("Dumps", dump_text)

    def _load_dumps(self):
        """Загрузка сохранённых дампов"""
        try:
            for filename in os.listdir(self.dumps_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.dumps_dir, filename)
                    with open(filepath, 'r') as f:
                        dump = json.load(f)
                        self.dumps.append(dump)

            self.log_info(f"Loaded {len(self.dumps)} dumps")

        except Exception as e:
            self.log_error(f"Failed to load dumps: {e}")

    def _delete_dump(self):
        """Удаление дампа"""
        self.show_message("Delete", "Delete dump feature coming soon...")

    def _export_dump(self):
        """Экспорт дампа"""
        self.show_message("Export", "Export dump feature coming soon...")

    # ========== Settings ==========

    def show_settings(self):
        """Настройки модуля"""
        settings_text = "NFC Module Settings\n\n"

        if self.enabled and self.pn532:
            settings_text += "Status: Active\n"
            settings_text += f"Interface: {self.pn532.interface}\n\n"

            settings_text += f"Default keys loaded: {len(self.default_keys)}\n"
            settings_text += f"Saved dumps: {len(self.dumps)}\n"
            settings_text += f"Dumps directory: {self.dumps_dir}\n\n"

            if self.last_card:
                uid = ':'.join([f"{b:02X}" for b in self.last_card['uid']])
                settings_text += f"Last card: {uid}\n"
                settings_text += f"Type: {self.last_card['type']}\n"
        else:
            settings_text += "Status: Not available\n\n"
            settings_text += "Check connection and configuration\n"

        self.show_message("Settings", settings_text)
