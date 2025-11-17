"""
UI Manager - управление интерфейсом на основе urwid
"""

import urwid
import logging
from typing import List, Tuple, Callable, Optional, Dict, Any
from datetime import datetime


class UIManager:
    """
    Менеджер пользовательского интерфейса.

    Реализует:
    - Главное меню
    - Статус-панель
    - Vim-style навигацию
    - Диалоговые окна
    """

    _instance = None

    def __init__(self, modules: List = None):
        """
        Инициализация UI Manager.

        Args:
            modules: Список загруженных модулей
        """
        if modules is None:
            modules = []

        self.modules = modules
        self.logger = logging.getLogger("cyberdeck.ui")

        # Мониторы (будут установлены позже)
        self.battery_monitor = None
        self.thermal_monitor = None
        self.network_monitor = None

        # Создаём UI компоненты
        self.status_bar = self._create_status_bar()
        self.main_menu = self._create_main_menu()
        self.footer = self._create_footer()

        # Главный фрейм
        self.frame = urwid.Frame(
            body=self.main_menu,
            header=self.status_bar,
            footer=self.footer
        )

        # Текущий активный виджет
        self.current_view = "main_menu"
        self.view_stack = []

        # Palette (цветовая схема)
        self.palette = self._create_palette()

    @classmethod
    def get_instance(cls, modules: List = None) -> 'UIManager':
        """Получить singleton экземпляр"""
        if cls._instance is None:
            cls._instance = cls(modules)
        return cls._instance

    def set_monitors(self, battery=None, thermal=None, network=None):
        """
        Установить системные мониторы.

        Args:
            battery: BatteryMonitor instance
            thermal: ThermalMonitor instance
            network: NetworkMonitor instance
        """
        self.battery_monitor = battery
        self.thermal_monitor = thermal
        self.network_monitor = network

    def _create_palette(self) -> List[Tuple]:
        """
        Создать цветовую схему.

        Returns:
            List[Tuple]: urwid palette
        """
        return [
            # (name, foreground, background, mono, fg_high, bg_high)
            ('banner', 'light cyan', 'default'),
            ('header', 'white', 'dark blue'),
            ('footer', 'white', 'dark gray'),
            ('status_normal', 'white', 'dark blue'),
            ('status_warning', 'yellow', 'dark blue'),
            ('status_critical', 'light red', 'dark blue'),
            ('menu_item', 'white', 'default'),
            ('menu_focus', 'white', 'dark cyan'),
            ('button', 'white', 'dark gray'),
            ('button_focus', 'white', 'dark cyan'),
            ('error', 'light red', 'default'),
            ('success', 'light green', 'default'),
        ]

    def _create_status_bar(self) -> urwid.AttrMap:
        """
        Создать статус-панель (верхняя).

        Returns:
            urwid.AttrMap: Статус-бар виджет
        """
        status_text = urwid.Text("CyberDeck Interface v2.0", align='center')
        return urwid.AttrMap(status_text, 'status_normal')

    def _create_footer(self) -> urwid.AttrMap:
        """
        Создать футер с подсказками клавиш.

        Returns:
            urwid.AttrMap: Футер виджет
        """
        footer_text = urwid.Text(
            "j/k:Navigate  Enter:Select  q:Quit  ?:Help  ::Command",
            align='center'
        )
        return urwid.AttrMap(footer_text, 'footer')

    def _create_main_menu(self) -> urwid.ListBox:
        """
        Создать главное меню.

        Returns:
            urwid.ListBox: Меню виджет
        """
        menu_items = []

        # Баннер
        banner = [
            "  ██████╗██╗   ██╗██████╗ ███████╗██████╗ ",
            " ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗",
            " ██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝",
            " ██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗",
            " ╚██████╗   ██║   ██████╔╝███████╗██║  ██║",
            "  ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝",
            "",
            " ██████╗ ███████╗ ██████╗██╗  ██╗  v2.0",
            " ██╔══██╗██╔════╝██╔════╝██║ ██╔╝",
            " ██║  ██║█████╗  ██║     █████╔╝ ",
            " ██║  ██║██╔══╝  ██║     ██╔═██╗ ",
            " ██████╔╝███████╗╚██████╗██║  ██╗",
            " ╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝",
            "",
        ]

        for line in banner:
            menu_items.append(
                urwid.AttrMap(
                    urwid.Text(('banner', line), align='center'),
                    None
                )
            )

        menu_items.append(urwid.Divider())

        # Пункты меню из модулей
        for idx, module in enumerate(self.modules, 1):
            button_text = f"[{idx}] {module.name}"
            button = urwid.Button(button_text)
            urwid.connect_signal(
                button,
                'click',
                self._on_module_selected,
                module
            )
            menu_items.append(
                urwid.AttrMap(button, 'menu_item', 'menu_focus')
            )

        # Дополнительные пункты
        menu_items.append(urwid.Divider())

        settings_btn = urwid.Button("[S] Settings")
        urwid.connect_signal(settings_btn, 'click', self._on_settings)
        menu_items.append(
            urwid.AttrMap(settings_btn, 'menu_item', 'menu_focus')
        )

        help_btn = urwid.Button("[?] Help")
        urwid.connect_signal(help_btn, 'click', self._on_help)
        menu_items.append(
            urwid.AttrMap(help_btn, 'menu_item', 'menu_focus')
        )

        return urwid.ListBox(urwid.SimpleFocusListWalker(menu_items))

    def _on_module_selected(self, button, module):
        """Обработчик выбора модуля"""
        self.logger.info(f"Selected module: {module.name}")
        self.show_module_view(module)

    def _on_settings(self, button):
        """Обработчик настроек"""
        self.show_message("Settings", "Settings panel coming soon...")

    def _on_help(self, button):
        """Обработчик справки"""
        help_text = """
        CyberDeck Interface v2.0 - Help

        Navigation:
        j / ↓ - Move down
        k / ↑ - Move up
        h / ← - Go back
        l / → - Select
        Enter - Confirm
        q - Quit
        Esc - Cancel

        Commands (press ':'):
        :quit - Exit application
        :help - Show help
        :log view - View logs

        Modules are loaded dynamically.
        Each module has its own hotkeys.
        """
        self.show_message("Help", help_text)

    def show_module_view(self, module):
        """
        Показать интерфейс модуля.

        Args:
            module: BaseModule instance
        """
        # Получаем пункты меню модуля
        menu_items_data = module.get_menu_items()

        if not menu_items_data:
            self.show_message(
                module.name,
                "This module has no menu items yet."
            )
            return

        # Создаём меню модуля
        menu_items = []
        menu_items.append(
            urwid.Text(f"=== {module.name} ===", align='center')
        )
        menu_items.append(urwid.Divider())

        for title, callback in menu_items_data:
            button = urwid.Button(title)
            urwid.connect_signal(button, 'click', lambda b, cb=callback: cb())
            menu_items.append(
                urwid.AttrMap(button, 'menu_item', 'menu_focus')
            )

        menu_items.append(urwid.Divider())

        back_btn = urwid.Button("[ESC] Back to Main Menu")
        urwid.connect_signal(back_btn, 'click', lambda b: self.go_back())
        menu_items.append(
            urwid.AttrMap(back_btn, 'menu_item', 'menu_focus')
        )

        listbox = urwid.ListBox(urwid.SimpleFocusListWalker(menu_items))

        # Сохраняем текущий вид и показываем новый
        self.view_stack.append(self.frame.body)
        self.frame.body = listbox
        self.current_view = f"module_{module.name}"

    def go_back(self):
        """Вернуться к предыдущему виду"""
        if self.view_stack:
            previous_view = self.view_stack.pop()
            self.frame.body = previous_view
            self.current_view = "previous"
            self.logger.info("Returned to previous view")

    def show_message(self, title: str, message: str):
        """
        Показать информационное сообщение.

        Args:
            title: Заголовок
            message: Текст сообщения
        """
        # Создаём диалог
        text_widget = urwid.Text(message)
        filler = urwid.Filler(text_widget, valign='top')
        padding = urwid.Padding(filler, left=2, right=2)

        ok_button = urwid.Button("OK")
        urwid.connect_signal(ok_button, 'click', lambda b: self.close_overlay())

        button_padding = urwid.Padding(
            urwid.AttrMap(ok_button, 'button', 'button_focus'),
            align='center',
            width=10
        )

        pile = urwid.Pile([
            padding,
            urwid.Divider(),
            button_padding
        ])

        box = urwid.LineBox(pile, title=title)

        # Показываем как overlay
        overlay = urwid.Overlay(
            box,
            self.frame,
            align='center',
            width=('relative', 60),
            valign='middle',
            height=('relative', 40)
        )

        self.view_stack.append(self.frame)
        self.overlay = overlay

    def close_overlay(self):
        """Закрыть overlay"""
        if self.view_stack:
            self.view_stack.pop()

    def update_status_bar(self):
        """Обновить статус-панель с данными мониторов"""
        status_parts = []

        # Батарея
        if self.battery_monitor and self.battery_monitor.enabled:
            self.battery_monitor.update()
            battery = self.battery_monitor.get_status()
            status_parts.append(f"🔋{battery['soc']}%")

        # WiFi
        if self.network_monitor:
            self.network_monitor.update()
            network = self.network_monitor.get_status()
            status_parts.append(f"📶{network['wifi']['signal']}/4")
            status_parts.append(f"📡{network['lte']['signal']}/5")

        # Температура
        if self.thermal_monitor:
            self.thermal_monitor.update()
            thermal = self.thermal_monitor.get_status()
            if thermal['max_temp']:
                status_parts.append(f"🌡️{thermal['max_temp']}°C")

        # Время
        current_time = datetime.now().strftime("%H:%M")
        status_parts.append(f"🕐{current_time}")

        # IP
        if self.network_monitor:
            ip = self.network_monitor.get_primary_ip()
            status_parts.append(f"📍{ip}")

        # Объединяем
        status_text = " | ".join(status_parts)
        self.status_bar.original_widget.set_text(status_text)

    def run(self):
        """Запустить главный цикл UI"""
        # Создаём Screen с поддержкой мыши (для сенсорных экранов)
        screen = urwid.raw_display.Screen()

        loop = urwid.MainLoop(
            self.frame,
            palette=self.palette,
            screen=screen,
            unhandled_input=self._handle_input
        )

        # Включаем поддержку мыши/сенсорного экрана
        screen.set_mouse_tracking(True)

        # Периодическое обновление статус-бара
        def update_callback(loop, user_data):
            self.update_status_bar()
            loop.set_alarm_in(1, update_callback)

        loop.set_alarm_in(1, update_callback)

        self.logger.info("Starting UI main loop with mouse/touchscreen support")
        loop.run()

    def _handle_input(self, key):
        """
        Обработчик глобальных клавиш.

        Args:
            key: Нажатая клавиша
        """
        # Vim-style navigation
        if key in ('j', 'down'):
            # Уже обрабатывается urwid
            pass
        elif key in ('k', 'up'):
            pass
        elif key in ('h', 'left', 'esc'):
            self.go_back()
        elif key in ('l', 'right'):
            pass

        # Quit
        elif key == 'q':
            raise urwid.ExitMainLoop()

        # Help
        elif key == '?':
            self._on_help(None)

        # Command mode
        elif key == ':':
            # TODO: Implement command line
            pass

    def get_input(self, prompt: str, default: str = "") -> str:
        """
        Запросить ввод от пользователя.

        Args:
            prompt: Текст подсказки
            default: Значение по умолчанию

        Returns:
            str: Введённое значение
        """
        # TODO: Implement input dialog
        return default

    def show_menu(self, title: str, items: List[str]) -> int:
        """
        Показать меню выбора.

        Args:
            title: Заголовок меню
            items: Список пунктов

        Returns:
            int: Индекс выбранного пункта
        """
        # TODO: Implement selection menu
        return 0

    def show_progress(self, current: int, total: int, message: str = ""):
        """
        Показать прогресс-бар.

        Args:
            current: Текущее значение
            total: Максимальное значение
            message: Сообщение
        """
        # TODO: Implement progress bar
        pass
