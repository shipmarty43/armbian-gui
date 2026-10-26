from unittest.mock import Mock
import pytest
import urwid
from core.dialogs import ActionCancelled
from core.ui_manager import UIManager


class FakeScreen:
    def __init__(self, keys):
        self.keys = iter(keys)
        self.timeouts = []
    def set_input_timeouts(self, **kwargs):
        self.timeouts.append(kwargs)
    def get_cols_rows(self):
        return (80, 24)
    def get_input(self):
        return next(self.keys)
    def draw_screen(self, *args):
        pass


def make_ui(keys):
    ui = UIManager([])
    screen = FakeScreen(keys)
    ui.loop = urwid.MainLoop(ui.frame, screen=screen, unhandled_input=ui._handle_input)
    ui.update_status_bar = Mock()
    return ui, screen


def test_input_edits_default_without_using_global_q_shortcut():
    ui, screen = make_ui([['end', 'q', 'backspace', 'X'], ['enter']])
    assert ui.get_input('Value', 'abc') == 'abcX'
    assert ui.loop.widget is ui.frame
    assert screen.timeouts[-1] == {'max_wait': None}


def test_selection_moves_and_confirms_second_item():
    ui, _ = make_ui([['down'], ['enter']])
    assert ui.show_menu('Select', ['one', 'two', 'three']) == 1


@pytest.mark.parametrize('kind', ['input', 'menu'])
def test_cancel_aborts_action_and_restores_ui(kind):
    ui, _ = make_ui([['esc']])
    previous_handler = ui.loop.unhandled_input
    after = Mock()
    def action():
        if kind == 'input':
            ui.get_input('Value', 'must not be applied')
        else:
            ui.show_menu('Select', ['must not be selected'])
        after()
    ui._run_action(action)
    after.assert_not_called()
    assert ui.loop.widget is ui.frame
    assert ui.loop.unhandled_input == previous_handler


def test_empty_menu_and_missing_loop_do_not_implicitly_choose_default():
    ui = UIManager([])
    with pytest.raises(ActionCancelled):
        ui.show_menu('Empty', [])
    with pytest.raises(RuntimeError, match='running TUI'):
        ui.get_input('Prompt', 'default')


def test_dialog_restores_screen_after_exception():
    ui, screen = make_ui([])
    with pytest.raises(StopIteration):
        ui.get_input('Value')
    assert ui.loop.widget is ui.frame
    assert screen.timeouts[-1] == {'max_wait': None}


def test_progress_does_not_grow_navigation_stack():
    ui = UIManager([])
    original = ui.frame.body
    ui.show_progress(1, 10, 'Work')
    ui.show_progress(9, 10, 'Work')
    assert len(ui.view_stack) == 1
    ui.go_back()
    assert ui.frame.body is original


def test_module_message_argument_order(monkeypatch):
    from test_module_configuration import DummyModule
    ui = Mock()
    monkeypatch.setattr(UIManager, 'get_instance', lambda: ui)
    module = DummyModule('test', 1, [])
    module.show_message('Title', 'Body')
    ui.show_message.assert_called_with('Title', 'Body')
    module.show_message('Body', title='Title')
    ui.show_message.assert_called_with('Title', 'Body')
    module.show_error('Failure')
    ui.show_message.assert_called_with('Error', 'Failure')


def test_mouse_can_cancel_input():
    ui, screen = make_ui([])
    def click_cancel():
        canvas = ui.loop.widget.render((80, 24), focus=True)
        for row, text in enumerate(canvas.text):
            col = text.find(b'Cancel')
            if col >= 0:
                return [('mouse press', 1, col, row)]
        raise AssertionError('Cancel button not visible')
    screen.get_input = click_cancel
    with pytest.raises(ActionCancelled):
        ui.get_input('Value')
    assert ui.loop.widget is ui.frame


def test_action_can_exit_main_loop():
    ui = UIManager([])
    def quit_action():
        raise urwid.ExitMainLoop()
    with pytest.raises(urwid.ExitMainLoop):
        ui._run_action(quit_action)
