"""Synchronous dialogs for the existing synchronous module API.

Reuse the running screen and MainLoop's input dispatcher. Do not start a second
terminal screen or recursively run urwid's event loop. Background alarms resume
when the dialog closes; status polling is performed while waiting for input.
"""
import threading
import time
import urwid


class ActionCancelled(BaseException):
    """Control flow caught at the UI action boundary, like ExitMainLoop.

    Module-level `except Exception` must not turn cancellation into a default
    value and accidentally continue the action.
    """


class Dialog:
    def __init__(self, title, items=None, default=''):
        self.done = False
        self.cancelled = False
        self.result = None
        self.edit = None
        if items is None:
            self.edit = urwid.Edit(edit_text=default)
            rows = [urwid.Text(title), self.edit, urwid.Divider(),
                    urwid.Button('OK', lambda _: self.accept(self.edit.edit_text))]
        else:
            rows = [urwid.Text(title), urwid.Divider()]
            rows.extend(urwid.Button(str(item), lambda _, i=i: self.accept(i))
                        for i, item in enumerate(items))
        rows.append(urwid.Button('Cancel', lambda _: self.cancel()))
        self.listbox = urwid.ListBox(urwid.SimpleFocusListWalker(rows))
        self.listbox.focus_position = 1 if self.edit is not None else 2
        self.widget = urwid.LineBox(self.listbox, title='Esc: cancel • ↑/↓: move • Enter: select')

    def accept(self, value):
        self.result, self.done = value, True

    def cancel(self):
        self.cancelled = self.done = True

    def unhandled(self, key):
        if key == 'esc':
            self.cancel()
        elif key == 'enter' and self.edit is not None:
            self.accept(self.edit.edit_text)
        elif key in ('tab', 'shift tab'):
            self.listbox.keypress(self.size, 'down' if key == 'tab' else 'up')

    def run(self, loop, poll_status):
        if loop is None:
            raise RuntimeError('Interactive input requires a running TUI')
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('Dialogs must run on the UI thread')
        previous, handler = loop.widget, loop.unhandled_input
        loop.widget = urwid.Overlay(self.widget, previous, 'center', ('relative', 90),
                                    'middle', ('relative', 80))
        loop.unhandled_input = self.unhandled
        loop.screen.set_input_timeouts(max_wait=0.1)
        last_poll = 0.0
        try:
            while not self.done:
                cols, rows = loop.screen.get_cols_rows()
                self.size = (max(1, int(cols * .9) - 2), max(1, int(rows * .8) - 2))
                if time.monotonic() - last_poll >= 1:
                    poll_status()
                    last_poll = time.monotonic()
                loop.draw_screen()
                loop.process_input(loop.screen.get_input())
            if self.cancelled:
                raise ActionCancelled()
            return self.result
        finally:
            loop.widget, loop.unhandled_input = previous, handler
            loop.screen.set_input_timeouts(max_wait=None)
            loop.draw_screen()
