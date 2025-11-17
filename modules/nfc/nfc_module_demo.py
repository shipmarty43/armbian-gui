"""
NFC Module - чтение, эмуляция и брутфорс NFC/RFID карт через PN532
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable


class NFCModule(BaseModule):
    """
    Модуль работы с NFC/RFID картами (PN532).

    Функции:
    - Чтение Mifare Classic 1K/4K, Ultralight, NTAG, DESFire
    - Эмуляция карт (HCE mode)
    - Брутфорс ключей Mifare
    - Управление дампами
    """

    def __init__(self):
        super().__init__(
            name="NFC Tools",
            version="1.0.0",
            priority=3
        )

        self.i2c_bus = 0
        self.i2c_address = 0x24
        self.dumps = []
        self.last_card_uid = None

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("NFC module loaded")

        # TODO: Инициализация PN532 через I2C
        # try:
        #     import nfc
        #     self.nfc_device = nfc.ContactlessFrontend('i2c')
        #     self.log_info("PN532 initialized")
        # except Exception as e:
        #     self.log_error(f"Failed to initialize PN532: {e}")

    def on_unload(self):
        """Освобождение ресурсов"""
        self.log_info("NFC module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        return [
            ("Scan & Read", self.scan_and_read),
            ("Emulate Card", self.emulate_card),
            ("Dump Manager", self.dump_manager),
            ("Key Dictionary Attack", self.key_attack),
            ("Protocol Analyzer", self.protocol_analyzer),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        return "NFC: Ready"

    def get_hotkeys(self):
        """Горячие клавиши"""
        return {
            'r': self.scan_and_read,
            'e': self.emulate_card,
            's': self.save_dump,
        }

    # ========== Функции модуля ==========

    def scan_and_read(self):
        """Сканирование и чтение карты"""
        self.log_info("Scanning for NFC card...")

        self.show_message(
            "Scanning",
            "Place NFC card on the reader...\n\n"
            "(Demo mode - simulating card detection)\n\n"
            "Card detected!\n"
            "UID: 04 12 34 56 AB CD\n"
            "Type: Mifare Classic 1K\n"
            "SAK: 08\n"
            "ATQA: 00 04"
        )

        # Симуляция чтения
        self.last_card_uid = "04:12:34:56:AB:CD"

        # Предлагаем прочитать данные
        read_data = self.show_menu(
            "Card Detected",
            [
                "Read all sectors",
                "Read specific sector",
                "Save dump",
                "Cancel"
            ]
        )

        if read_data == 0:
            self.read_all_sectors()
        elif read_data == 1:
            self.read_sector()
        elif read_data == 2:
            self.save_dump()

    def read_all_sectors(self):
        """Чтение всех секторов карты"""
        self.show_message(
            "Reading",
            "Reading all sectors...\n\n"
            "Sector 0: [OK] (Key A: FF FF FF FF FF FF)\n"
            "Sector 1: [OK] (Key A: FF FF FF FF FF FF)\n"
            "Sector 2: [Failed] (Authentication failed)\n"
            "Sector 3: [OK] (Key A: A0 A1 A2 A3 A4 A5)\n"
            "...\n\n"
            "Read complete: 14/16 sectors\n"
            "(Demo mode)"
        )

        self.log_info("Card data read")

    def read_sector(self):
        """Чтение конкретного сектора"""
        sector = self.get_user_input("Enter sector number (0-15):", "0")

        try:
            sector_num = int(sector)
            if 0 <= sector_num <= 15:
                self.show_message(
                    f"Sector {sector_num}",
                    f"Block 0: 04 12 34 56 AB CD 00 00 ...\n"
                    f"Block 1: 00 00 00 00 00 00 00 00 ...\n"
                    f"Block 2: 00 00 00 00 00 00 00 00 ...\n"
                    f"Block 3: FF FF FF FF FF FF FF 07 80 69 ...\n"
                    "(Demo data)"
                )
            else:
                self.show_error("Invalid sector number")
        except ValueError:
            self.show_error("Invalid input")

    def save_dump(self):
        """Сохранение дампа карты"""
        if not self.last_card_uid:
            self.show_error("No card scanned yet")
            return

        filename = self.get_user_input(
            "Enter filename:",
            f"dump_{self.last_card_uid.replace(':', '')}.mfd"
        )

        # Симуляция сохранения
        dump_data = {
            'uid': self.last_card_uid,
            'type': 'Mifare Classic 1K',
            'filename': filename
        }

        self.dumps.append(dump_data)

        self.show_message(
            "Saved",
            f"Dump saved: {filename}\n\n"
            f"UID: {self.last_card_uid}\n"
            "Type: Mifare Classic 1K\n"
            "(Demo mode)"
        )

        self.log_info(f"Dump saved: {filename}")

    def emulate_card(self):
        """Эмуляция карты"""
        if not self.dumps:
            self.show_message(
                "Emulate",
                "No dumps available.\n\n"
                "Read and save a card dump first."
            )
            return

        # Выбор дампа для эмуляции
        dump_names = [
            f"{d['filename']} (UID: {d['uid']})"
            for d in self.dumps
        ]

        idx = self.show_menu("Select Dump to Emulate", dump_names)

        if idx >= 0 and idx < len(self.dumps):
            dump = self.dumps[idx]

            self.show_message(
                "Emulating",
                f"Emulating card:\n\n"
                f"UID: {dump['uid']}\n"
                f"Type: {dump['type']}\n\n"
                "Card emulation active...\n"
                "Press ESC to stop\n"
                "(Demo mode)"
            )

            self.log_info(f"Emulating: {dump['filename']}")

    def dump_manager(self):
        """Управление дампами"""
        if not self.dumps:
            self.show_message(
                "Dump Manager",
                "No dumps saved yet.\n\n"
                "Scan and save a card to create dumps."
            )
            return

        dump_list = "Saved Dumps:\n\n"
        for idx, dump in enumerate(self.dumps, 1):
            dump_list += (
                f"{idx}. {dump['filename']}\n"
                f"   UID: {dump['uid']}\n"
                f"   Type: {dump['type']}\n\n"
            )

        self.show_message("Dump Manager", dump_list)

    def key_attack(self):
        """Брутфорс ключей Mifare"""
        self.show_message(
            "Key Dictionary Attack",
            "Mifare Key Dictionary Attack\n\n"
            "Select dictionary:\n"
            "1. Default keys (common passwords)\n"
            "2. Extended dictionary\n"
            "3. Custom wordlist\n\n"
            "Attack type:\n"
            "- Nested authentication\n"
            "- Hardnested (slower, more effective)\n\n"
            "(Feature in development)"
        )

    def protocol_analyzer(self):
        """Анализ протоколов NFC"""
        self.show_message(
            "Protocol Analyzer",
            "NFC Protocol Analyzer\n\n"
            "Analyzes:\n"
            "- Timing analysis\n"
            "- Anti-collision process\n"
            "- APDU commands (DESFire)\n"
            "- Communication flow\n\n"
            "(Feature in development)"
        )

    def show_settings(self):
        """Настройки модуля"""
        settings_text = (
            "NFC Module Settings\n\n"
            f"I2C Bus: {self.i2c_bus}\n"
            f"I2C Address: 0x{self.i2c_address:02X}\n\n"
            "Supported card types:\n"
            "- Mifare Classic 1K/4K\n"
            "- Mifare Ultralight\n"
            "- NTAG213/215/216\n"
            "- DESFire\n\n"
            "(Settings are read-only in demo mode)"
        )

        self.show_message("Settings", settings_text)
