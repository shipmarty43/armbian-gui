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
            ("System Information", self.system_info),
            ("File Manager", self.file_manager),
            ("Process Monitor", self.process_monitor),
            ("Network Info", self.network_info),
            ("Disk Usage", self.disk_usage),
            ("About", self.about),
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

        License: Custom — No Execution or Use (see LICENSE)
        """

        self.show_message("About CyberDeck Interface", about_text)
