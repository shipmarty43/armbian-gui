"""
System Module - системные утилиты, файловый менеджер, терминал
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable
import psutil
import os


class SystemModule(BaseModule):
    """
    Системный модуль.

    Функции:
    - Запуск внешних приложений (SDRangel, GQRX, etc.)
    - Файловый менеджер
    - Терминал
    - Системная информация
    - Настройки
    """

    def __init__(self):
        super().__init__(
            name="System Tools",
            version="1.0.0",
            priority=10  # Lowest priority
        )

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("System module loaded")

    def on_unload(self):
        """Освобождение ресурсов"""
        self.log_info("System module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        return [
            ("⚙️  Settings", self.settings_menu),
            ("📊 System Information", self.system_info),
            ("📁 File Manager", self.file_manager),
            ("📈 Process Monitor", self.process_monitor),
            ("🌐 Network Info", self.network_info),
            ("💾 Disk Usage", self.disk_usage),
            ("ℹ️  About", self.about),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        return "System: OK"

    # ========== Функции модуля ==========

    def system_info(self):
        """Системная информация"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # Memory
            mem = psutil.virtual_memory()
            mem_total = mem.total / (1024**3)  # GB
            mem_used = mem.used / (1024**3)
            mem_percent = mem.percent

            # System
            uname = os.uname()

            info_text = (
                "System Information\n\n"
                "=== Hardware ===\n"
                f"Device: {uname.machine}\n"
                f"CPU Cores: {cpu_count}\n"
                f"CPU Usage: {cpu_percent}%\n"
                f"Memory: {mem_used:.1f} / {mem_total:.1f} GB ({mem_percent}%)\n\n"
                "=== Software ===\n"
                f"OS: {uname.sysname}\n"
                f"Kernel: {uname.release}\n"
                f"Hostname: {uname.nodename}\n\n"
                f"Python: {'.'.join(map(str, __import__('sys').version_info[:3]))}\n"
            )

            self.show_message("System Information", info_text)

        except Exception as e:
            self.show_error(f"Failed to get system info: {e}")

    def file_manager(self):
        """Файловый менеджер"""
        current_dir = os.getcwd()

        try:
            entries = os.listdir(current_dir)
            dirs = [e for e in entries if os.path.isdir(e)]
            files = [e for e in entries if os.path.isfile(e)]

            fm_text = f"File Manager\n\nCurrent: {current_dir}\n\n"

            fm_text += "Directories:\n"
            for d in sorted(dirs)[:10]:
                fm_text += f"  📁 {d}\n"

            fm_text += "\nFiles:\n"
            for f in sorted(files)[:10]:
                size = os.path.getsize(f)
                fm_text += f"  📄 {f} ({size} bytes)\n"

            if len(dirs) + len(files) > 20:
                fm_text += f"\n... and {len(dirs) + len(files) - 20} more items"

            self.show_message("File Manager", fm_text)

        except Exception as e:
            self.show_error(f"Failed to list directory: {e}")

    def process_monitor(self):
        """Монитор процессов"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    pinfo = proc.info
                    processes.append(pinfo)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            # Сортируем по CPU usage
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            top_procs = processes[:10]

            proc_text = "Process Monitor\n\nTop 10 by CPU:\n\n"
            proc_text += "PID      Name                    CPU%\n"
            proc_text += "-" * 45 + "\n"

            for p in top_procs:
                pid = p['pid']
                name = (p['name'] or 'Unknown')[:20]
                cpu = p['cpu_percent'] or 0
                proc_text += f"{pid:<8} {name:<20} {cpu:>6.1f}%\n"

            self.show_message("Process Monitor", proc_text)

        except Exception as e:
            self.show_error(f"Failed to get processes: {e}")

    def network_info(self):
        """Информация о сети"""
        try:
            addrs = psutil.net_if_addrs()

            net_text = "Network Interfaces\n\n"

            for interface, addr_list in addrs.items():
                net_text += f"=== {interface} ===\n"

                for addr in addr_list:
                    if addr.family == 2:  # AF_INET (IPv4)
                        net_text += f"  IPv4: {addr.address}\n"
                        net_text += f"  Netmask: {addr.netmask}\n"
                    elif addr.family == 17:  # AF_PACKET (MAC)
                        net_text += f"  MAC: {addr.address}\n"

                net_text += "\n"

            self.show_message("Network Info", net_text)

        except Exception as e:
            self.show_error(f"Failed to get network info: {e}")

    def disk_usage(self):
        """Использование диска"""
        try:
            disk = psutil.disk_usage('/')
            total = disk.total / (1024**3)  # GB
            used = disk.used / (1024**3)
            free = disk.free / (1024**3)
            percent = disk.percent

            disk_text = (
                "Disk Usage\n\n"
                f"Total: {total:.1f} GB\n"
                f"Used:  {used:.1f} GB ({percent}%)\n"
                f"Free:  {free:.1f} GB\n\n"
            )

            # ASCII bar
            bar_length = 40
            used_bars = int(bar_length * percent / 100)
            free_bars = bar_length - used_bars

            disk_text += "[" + "█" * used_bars + "░" * free_bars + "]\n"

            self.show_message("Disk Usage", disk_text)

        except Exception as e:
            self.show_error(f"Failed to get disk usage: {e}")

    def about(self):
        """О программе"""
        about_text = """
        CyberDeck Interface v2.0

        Mobile Security Research Platform

        Features:
        - Sub-GHz Analysis (CC1101)
        - LoRa Mesh Networks (Meshtastic)
        - NFC/RFID Tools (PN532)
        - WiFi Pentesting (hcxtools)
        - SDR Analysis (HackRF/RTL-SDR)
        - BadUSB Payloads
        - GPS Tracking & Wardriving

        Hardware Platform:
        - Orange Pi Zero 2W / Orange Pi 3
        - Modular architecture
        - Vim-style interface

        License: MIT / GPLv3
        """

        self.show_message("About CyberDeck Interface", about_text)

    def settings_menu(self):
        """Меню настроек"""
        choice = self.show_menu(
            "Settings Menu",
            [
                "📝 Edit Configuration (config/main.yaml)",
                "🔧 Hardware Settings",
                "🌐 Network Settings",
                "🎨 UI Settings",
                "📡 Module Settings",
                "💾 Backup Configuration",
                "🔄 Restore Configuration",
                "🔃 Reload Configuration",
                "Back"
            ]
        )

        if choice == 0:
            self.edit_config()
        elif choice == 1:
            self.hardware_settings()
        elif choice == 2:
            self.network_settings()
        elif choice == 3:
            self.ui_settings()
        elif choice == 4:
            self.module_settings()
        elif choice == 5:
            self.backup_config()
        elif choice == 6:
            self.restore_config()
        elif choice == 7:
            self.reload_config()

    def edit_config(self):
        """Редактирование config/main.yaml"""
        config_path = "config/main.yaml"

        try:
            # Читаем текущий конфиг
            if not os.path.exists(config_path):
                self.show_error(f"Configuration file not found: {config_path}")
                return

            with open(config_path, 'r') as f:
                config_content = f.read()

            # Показываем информацию о конфиге
            info = f"Configuration File: {config_path}\n\n"
            info += f"Size: {len(config_content)} bytes\n"
            info += f"Lines: {len(config_content.splitlines())}\n\n"
            info += "To edit configuration:\n\n"
            info += "1. Use external editor:\n"
            info += f"   nano {config_path}\n"
            info += f"   vi {config_path}\n\n"
            info += "2. Or edit directly:\n"
            info += "   The configuration uses YAML format\n\n"
            info += "Options:\n"
            info += "[V] View current config\n"
            info += "[E] Open in nano editor\n"
            info += "[B] Backup config\n"
            info += "[R] Reset to defaults\n"

            choice = self.show_menu(
                "Edit Configuration",
                [
                    "View Current Config",
                    "Open in Nano Editor",
                    "Backup Config",
                    "Reset to Defaults",
                    "Cancel"
                ]
            )

            if choice == 0:
                self.view_config()
            elif choice == 1:
                self.open_in_editor(config_path)
            elif choice == 2:
                self.backup_config()
            elif choice == 3:
                self.reset_config()

        except Exception as e:
            self.show_error(f"Error editing config: {e}")

    def view_config(self):
        """Просмотр конфигурации"""
        config_path = "config/main.yaml"

        try:
            with open(config_path, 'r') as f:
                lines = f.readlines()

            # Показываем по частям (первые 50 строк)
            content = "".join(lines[:50])
            if len(lines) > 50:
                content += f"\n\n... and {len(lines) - 50} more lines"

            self.show_message("Configuration (first 50 lines)", content)

        except Exception as e:
            self.show_error(f"Error reading config: {e}")

    def open_in_editor(self, filepath):
        """Открыть файл в nano редакторе"""
        import subprocess

        try:
            self.show_message(
                "Opening Editor",
                f"Opening {filepath} in nano editor...\n\n"
                "Press Ctrl+X to exit\n"
                "Press Ctrl+O to save\n\n"
                "Press OK to continue"
            )

            # Запускаем nano в фоне
            subprocess.call(['nano', filepath])

            self.show_message(
                "Editor Closed",
                "Configuration may have been modified.\n\n"
                "Restart the application to apply changes."
            )

        except Exception as e:
            self.show_error(f"Error opening editor: {e}")

    def hardware_settings(self):
        """Настройки оборудования"""
        config = self.load_config("config/main.yaml")
        hardware = config.get('hardware', {})

        settings_text = "Hardware Settings\n\n"

        # Battery
        battery = hardware.get('battery', {})
        settings_text += f"🔋 Battery:\n"
        settings_text += f"  Enabled: {battery.get('enabled', False)}\n"
        settings_text += f"  I2C Bus: {battery.get('i2c_bus', 3)}\n"
        settings_text += f"  I2C Address: 0x{battery.get('i2c_address', 0x10):02X}\n\n"

        # LoRa
        lora = hardware.get('lora', {})
        settings_text += f"📡 LoRa (SX1262):\n"
        settings_text += f"  Enabled: {lora.get('enabled', False)}\n"
        settings_text += f"  SPI Bus: {lora.get('spi_bus', 0)}\n"
        settings_text += f"  Frequency: {lora.get('frequency', 868.0)} MHz\n"
        settings_text += f"  SF: {lora.get('spreading_factor', 11)}\n\n"

        # GPS
        gps = hardware.get('gps', {})
        settings_text += f"🛰️  GPS:\n"
        settings_text += f"  Enabled: {gps.get('enabled', False)}\n"
        settings_text += f"  Device: {gps.get('device', '/dev/ttyS1')}\n"
        settings_text += f"  Baudrate: {gps.get('baudrate', 9600)}\n\n"

        # NFC
        nfc = hardware.get('nfc', {})
        settings_text += f"💳 NFC (PN532):\n"
        settings_text += f"  Enabled: {nfc.get('enabled', False)}\n"
        settings_text += f"  Interface: {nfc.get('interface', 'pn532_spi')}\n\n"

        settings_text += "\nTo modify: Edit config/main.yaml"

        self.show_message("Hardware Settings", settings_text)

    def network_settings(self):
        """Настройки сети"""
        config = self.load_config("config/main.yaml")
        network = config.get('network', {})

        settings_text = "Network Settings\n\n"

        # WiFi
        wifi = network.get('wifi', {})
        settings_text += f"📶 WiFi:\n"
        settings_text += f"  Interface: {wifi.get('interface', 'wlan0')}\n"
        settings_text += f"  Monitor Capable: {wifi.get('monitor_capable', True)}\n\n"

        # LTE
        lte = network.get('lte', {})
        settings_text += f"📡 LTE Modem:\n"
        settings_text += f"  Enabled: {lte.get('enabled', False)}\n"
        settings_text += f"  Interface: {lte.get('interface', 'wwan0')}\n"
        settings_text += f"  Device: {lte.get('device', '/dev/ttyUSB2')}\n\n"

        # Ethernet
        eth = network.get('ethernet', {})
        settings_text += f"🔌 Ethernet:\n"
        settings_text += f"  Interface: {eth.get('interface', 'eth0')}\n"
        settings_text += f"  DHCP: {eth.get('dhcp', True)}\n\n"

        settings_text += "\nTo modify: Edit config/main.yaml"

        self.show_message("Network Settings", settings_text)

    def ui_settings(self):
        """Настройки интерфейса"""
        config = self.load_config("config/main.yaml")
        ui = config.get('ui', {})

        settings_text = "UI Settings\n\n"
        settings_text += f"Theme: {ui.get('theme', 'default')}\n"
        settings_text += f"Refresh Rate: {ui.get('refresh_rate', 100)} ms\n"
        settings_text += f"Status Bar: {ui.get('status_bar', True)}\n"
        settings_text += f"Show Tips: {ui.get('show_tips', True)}\n"
        settings_text += f"Vim Mode: {ui.get('vim_mode', True)}\n"
        settings_text += f"Command History: {ui.get('command_history_size', 100)}\n\n"
        settings_text += "To modify: Edit config/main.yaml"

        self.show_message("UI Settings", settings_text)

    def module_settings(self):
        """Настройки модулей"""
        config = self.load_config("config/main.yaml")
        modules = config.get('modules', {})

        settings_text = "Module Settings\n\n"
        settings_text += "Autoload Modules:\n"

        autoload = modules.get('autoload', [])
        for idx, module in enumerate(autoload, 1):
            settings_text += f"  {idx}. {module}\n"

        settings_text += f"\nTotal: {len(autoload)} modules\n"
        settings_text += f"\nPriority Order: {modules.get('priority_order', True)}\n\n"
        settings_text += "To modify: Edit config/main.yaml"

        self.show_message("Module Settings", settings_text)

    def backup_config(self):
        """Создать backup конфигурации"""
        import shutil
        from datetime import datetime

        try:
            config_path = "config/main.yaml"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"config/main.yaml.backup_{timestamp}"

            shutil.copy2(config_path, backup_path)

            self.show_message(
                "Backup Created",
                f"Configuration backed up to:\n\n{backup_path}\n\n"
                f"You can restore it later if needed."
            )

        except Exception as e:
            self.show_error(f"Error creating backup: {e}")

    def restore_config(self):
        """Восстановить конфигурацию из backup"""
        import glob

        try:
            backups = glob.glob("config/main.yaml.backup_*")

            if not backups:
                self.show_message(
                    "No Backups Found",
                    "No configuration backups found.\n\n"
                    "Create a backup first using:\n"
                    "Settings > Backup Configuration"
                )
                return

            # Сортируем по дате (новые первые)
            backups.sort(reverse=True)

            # Показываем список
            backup_list = ["Latest backups:"] + backups[:10] + ["Cancel"]

            choice = self.show_menu("Restore Configuration", backup_list)

            if 0 < choice <= len(backups):
                backup_file = backups[choice - 1]
                self.show_message(
                    "Restore",
                    f"To restore from backup:\n\n"
                    f"1. Stop the application\n"
                    f"2. Run: cp {backup_file} config/main.yaml\n"
                    f"3. Restart the application"
                )

        except Exception as e:
            self.show_error(f"Error listing backups: {e}")

    def reload_config(self):
        """Перезагрузить конфигурацию"""
        self.show_message(
            "Reload Configuration",
            "To reload configuration:\n\n"
            "1. Save your changes to config/main.yaml\n"
            "2. Restart the application:\n"
            "   - Press 'q' to quit\n"
            "   - Run: python core/main.py\n\n"
            "Configuration is loaded on startup."
        )

    def reset_config(self):
        """Сбросить конфигурацию к defaults"""
        self.show_message(
            "Reset Configuration",
            "WARNING: This will reset config to defaults!\n\n"
            "To reset safely:\n\n"
            "1. Backup current config first\n"
            "2. Copy default config:\n"
            "   cp config/main.yaml.example config/main.yaml\n"
            "3. Restart the application\n\n"
            "This feature is not yet automated\n"
            "to prevent accidental data loss."
        )
