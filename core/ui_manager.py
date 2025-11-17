"""
UI Manager - управление интерфейсом на основе urwid
"""

import urwid
import logging
from typing import List, Tuple, Callable, Optional, Dict, Any
from datetime import datetime


class SelectableText(urwid.Text):
    """
    Текстовый виджет с поддержкой выбора и клика мыши.

    Позволяет кликать на элементы списка как кнопки.
    """

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class ClickableListItem(urwid.WidgetWrap):
    """
    Элемент списка с поддержкой клика мыши.

    Args:
        text: Отображаемый текст
        callback: Функция, вызываемая при клике
        attr_map: Карта атрибутов для нормального состояния
        focus_map: Карта атрибутов для фокуса
    """

    signals = ['click']

    def __init__(self, text: str, callback: Callable = None,
                 attr_map: str = 'menu_item', focus_map: str = 'menu_focus'):
        self.callback = callback
        self._text = text

        # Создаём кнопку для лучшей поддержки мыши
        self.button = urwid.Button(text)
        self.button._label.align = 'left'

        if callback:
            urwid.connect_signal(self.button, 'click', lambda btn: callback())

        wrapped = urwid.AttrMap(self.button, attr_map, focus_map)
        super().__init__(wrapped)

    def mouse_event(self, size, event, button, col, row, focus):
        """Обработка событий мыши"""
        if event == 'mouse press' and button == 1:  # Левая кнопка мыши
            if self.callback:
                self.callback()
            return True
        return super().mouse_event(size, event, button, col, row, focus)


class MouseScrollListBox(urwid.ListBox):
    """
    ListBox с поддержкой прокрутки колесом мыши.

    Обрабатывает события прокрутки колеса мыши для лучшего
    UX на сенсорных экранах и при использовании мыши.
    """

    def mouse_event(self, size, event, button, col, row, focus):
        """Обработка событий мыши, включая прокрутку колесом"""
        # Прокрутка колесом мыши вверх (button 4)
        if event == 'mouse press' and button == 4:
            self.keypress(size, 'up')
            self.keypress(size, 'up')
            self.keypress(size, 'up')
            return True

        # Прокрутка колесом мыши вниз (button 5)
        elif event == 'mouse press' and button == 5:
            self.keypress(size, 'down')
            self.keypress(size, 'down')
            self.keypress(size, 'down')
            return True

        # Передать остальные события родительскому классу
        return super().mouse_event(size, event, button, col, row, focus)


class UIManager:
    """
    Менеджер пользовательского интерфейса.

    Реализует:
    - Главное меню
    - Статус-панель
    - Vim-style навигацию
    - Диалоговые окна
    - Поддержка мыши/сенсорного экрана
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
        status_text = urwid.Text("CyberDeck Interface v3.0 🖱️", align='center')
        return urwid.AttrMap(status_text, 'status_normal')

    def _create_footer(self) -> urwid.AttrMap:
        """
        Создать футер с подсказками клавиш.

        Returns:
            urwid.AttrMap: Футер виджет
        """
        footer_text = urwid.Text(
            "j/k:Navigate  Enter/Click:Select  Scroll:Wheel  q:Quit  ?:Help",
            align='center'
        )
        return urwid.AttrMap(footer_text, 'footer')

    def _create_main_menu(self) -> MouseScrollListBox:
        """
        Создать главное меню с поддержкой мыши.

        Returns:
            MouseScrollListBox: Меню виджет
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
            " ██████╗ ███████╗ ██████╗██╗  ██╗  v3.0",
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

        # Пункты меню из модулей с поддержкой кликов мыши
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

        # Используем MouseScrollListBox для поддержки прокрутки колесом мыши
        return MouseScrollListBox(urwid.SimpleFocusListWalker(menu_items))

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
        CyberDeck Interface v3.0 - Help

        Keyboard Navigation:
        j / ↓       - Move down
        k / ↑       - Move up
        h / ← / Esc - Go back
        l / →       - Select
        Enter       - Confirm
        q           - Quit

        Mouse/Touchscreen Support:
        Left Click  - Select button/menu item
        Scroll Up   - Move up in list
        Scroll Down - Move down in list
        Drag        - Scroll through content

        Commands (press ':'):
        :quit     - Exit application
        :help     - Show help
        :log view - View logs

        Features:
        - Full mouse and touchscreen support
        - All buttons are clickable
        - Mouse wheel scrolling
        - Vim-style keyboard navigation
        - Dynamic module loading
        - Each module has its own hotkeys
        """
        self.show_message("Help", help_text)

    def show_module_view(self, module):
        """
        Показать интерфейс модуля с поддержкой кликов мыши.

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
            urwid.AttrMap(
                urwid.Text(f"=== {module.name} ===", align='center'),
                'header'
            )
        )
        menu_items.append(urwid.Divider())

        # Создаём кнопки для каждого пункта меню
        for title, callback in menu_items_data:
            button = urwid.Button(title)
            urwid.connect_signal(button, 'click', lambda b, cb=callback: cb())
            menu_items.append(
                urwid.AttrMap(button, 'menu_item', 'menu_focus')
            )

        menu_items.append(urwid.Divider())

        # Кнопка возврата
        back_btn = urwid.Button("[ESC] Back to Main Menu")
        urwid.connect_signal(back_btn, 'click', lambda b: self.go_back())
        menu_items.append(
            urwid.AttrMap(back_btn, 'menu_item', 'menu_focus')
        )

        # Используем MouseScrollListBox для поддержки прокрутки
        listbox = MouseScrollListBox(urwid.SimpleFocusListWalker(menu_items))

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

        # ВАЖНО: Сохраняем текущий body ДО создания overlay
        current_body = self.frame.body

        # Создаем overlay с сохраненным body как базой
        overlay = urwid.Overlay(
            box,
            current_body,  # Используем сохраненную ссылку, не self.frame.body
            align='center',
            width=('relative', 80),
            valign='middle',
            height=('relative', 60)
        )

        # Сохраняем в стек и устанавливаем overlay
        self.view_stack.append(current_body)
        self.frame.body = overlay

    def close_overlay(self):
        """Закрыть overlay"""
        if self.view_stack:
            previous_body = self.view_stack.pop()
            self.frame.body = previous_body

    def update_status_bar(self):
        """Обновить статус-панель с данными мониторов"""
        status_parts = []

        # Батарея
        if self.battery_monitor and hasattr(self.battery_monitor, 'enabled') and self.battery_monitor.enabled:
            try:
                self.battery_monitor.update()
                battery = self.battery_monitor.get_status()
                if battery and 'soc' in battery:
                    status_parts.append(f"🔋{battery['soc']}%")
            except Exception as e:
                self.logger.debug(f"Battery monitor error: {e}")

        # WiFi
        if self.network_monitor:
            try:
                self.network_monitor.update()
                network = self.network_monitor.get_status()
                if network and 'wifi' in network:
                    status_parts.append(f"📶{network['wifi']['signal']}/4")
                if network and 'lte' in network:
                    status_parts.append(f"📡{network['lte']['signal']}/5")
            except Exception as e:
                self.logger.debug(f"Network monitor error: {e}")

        # Температура
        if self.thermal_monitor:
            try:
                self.thermal_monitor.update()
                thermal = self.thermal_monitor.get_status()
                if thermal and thermal.get('max_temp'):
                    status_parts.append(f"🌡️{thermal['max_temp']}°C")
            except Exception as e:
                self.logger.debug(f"Thermal monitor error: {e}")

        # Время
        current_time = datetime.now().strftime("%H:%M")
        status_parts.append(f"🕐{current_time}")

        # IP
        if self.network_monitor:
            try:
                ip = self.network_monitor.get_primary_ip()
                if ip and ip != "N/A":
                    status_parts.append(f"📍{ip}")
            except Exception as e:
                self.logger.debug(f"IP retrieval error: {e}")

        # Объединяем
        status_text = " | ".join(status_parts) if status_parts else "CyberDeck v3.0"
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
        Обработчик глобальных клавиш и событий мыши.

        Args:
            key: Нажатая клавиша или событие мыши
        """
        # Обработка событий мыши
        if isinstance(key, tuple) and key[0] == 'mouse press':
            # key = ('mouse press', button, col, row)
            button = key[1]
            col = key[2]
            row = key[3]

            self.logger.debug(f"Mouse click: button={button}, col={col}, row={row}")

            # Левая кнопка мыши - уже обрабатывается виджетами
            # Средняя кнопка - можно использовать для дополнительных действий
            # Правая кнопка - контекстное меню (будущее)

            return

        # Обработка прокрутки колесом мыши
        elif isinstance(key, tuple) and key[0] == 'mouse drag':
            # Прокрутка уже обрабатывается urwid
            return

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
