"""
Ducky Script Parser - парсер для Rubber Ducky / Flipper Zero payload формата
"""

import time
import logging
from typing import List, Tuple, Optional


class DuckyScriptParser:
    """Parser for Ducky Script payloads"""

    def __init__(self, usb_gadget):
        """
        Initialize parser.

        Args:
            usb_gadget: USBGadgetController instance
        """
        self.logger = logging.getLogger("cyberdeck.duckyscript")
        self.usb = usb_gadget
        self.default_delay = 50  # ms

    def parse_line(self, line: str) -> Optional[Tuple[str, List[str]]]:
        """
        Parse single line of Ducky Script.

        Args:
            line: Line to parse

        Returns:
            Tuple of (command, args) or None
        """
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#') or line.startswith('//'):
            return None

        # Split command and arguments
        parts = line.split(maxsplit=1)
        if not parts:
            return None

        command = parts[0].upper()
        args = parts[1] if len(parts) > 1 else ""

        return (command, args.split())

    def execute_script(self, script: str, callback=None) -> bool:
        """
        Execute Ducky Script.

        Args:
            script: Script content
            callback: Optional callback(line_number, total_lines, command)

        Returns:
            bool: True if successful
        """
        lines = script.split('\n')
        total_lines = len(lines)

        for line_num, line in enumerate(lines, 1):
            parsed = self.parse_line(line)

            if not parsed:
                continue

            command, args = parsed

            if callback:
                callback(line_num, total_lines, command)

            # Execute command
            if not self._execute_command(command, args):
                self.logger.error(f"Failed to execute line {line_num}: {line}")
                return False

        return True

    def _execute_command(self, command: str, args: List[str]) -> bool:
        """Execute single Ducky Script command"""

        # REM - Comment (ignore)
        if command == "REM":
            return True

        # DELAY - Wait (milliseconds)
        elif command == "DELAY":
            if args:
                delay_ms = int(args[0])
                time.sleep(delay_ms / 1000.0)
            return True

        # DEFAULT_DELAY - Set default delay
        elif command == "DEFAULT_DELAY" or command == "DEFAULTDELAY":
            if args:
                self.default_delay = int(args[0])
            return True

        # STRING - Type string
        elif command == "STRING":
            text = ' '.join(args)
            return self.usb.type_string(text, delay=self.default_delay / 1000.0)

        # STRINGLN - Type string + ENTER
        elif command == "STRINGLN":
            text = ' '.join(args)
            self.usb.type_string(text, delay=self.default_delay / 1000.0)
            return self.usb.send_key('ENTER')

        # Single key press
        elif command in self.usb.KEYCODES:
            return self.usb.send_key(command)

        # Modifier + key combinations
        elif command in ["CTRL", "CONTROL", "SHIFT", "ALT", "GUI", "WINDOWS"]:
            # Parse combination (e.g., "CTRL ALT DELETE")
            modifiers = []
            keys = []

            for arg in args:
                arg_upper = arg.upper()
                if arg_upper in ["CTRL", "CONTROL", "SHIFT", "ALT", "GUI", "WINDOWS"]:
                    if arg_upper == "CONTROL":
                        modifiers.append("CTRL")
                    elif arg_upper == "WINDOWS":
                        modifiers.append("GUI")
                    else:
                        modifiers.append(arg_upper)
                else:
                    keys.append(arg_upper)

            # Add first command as modifier
            if command == "CONTROL":
                modifiers.insert(0, "CTRL")
            elif command == "WINDOWS":
                modifiers.insert(0, "GUI")
            else:
                modifiers.insert(0, command)

            # Execute combination
            for key in keys:
                if not self.usb.send_key(key, modifiers):
                    return False

            return True

        # ENTER, SPACE, etc. (direct key names)
        elif command in ["ENTER", "ESC", "ESCAPE", "BACKSPACE", "TAB", "SPACE",
                        "UP", "DOWN", "LEFT", "RIGHT", "DELETE", "HOME", "END",
                        "PAGEUP", "PAGEDOWN", "CAPSLOCK", "NUMLOCK", "SCROLLLOCK"]:
            return self.usb.send_key(command)

        # Function keys
        elif command.startswith('F') and command[1:].isdigit():
            return self.usb.send_key(command)

        # REPEAT - Repeat previous command
        elif command == "REPEAT":
            # Would need to track previous command
            self.logger.warning("REPEAT not fully implemented")
            return True

        else:
            self.logger.warning(f"Unknown command: {command}")
            return True  # Don't fail on unknown commands

    def validate_script(self, script: str) -> Tuple[bool, List[str]]:
        """
        Validate Ducky Script syntax.

        Args:
            script: Script to validate

        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        lines = script.split('\n')

        for line_num, line in enumerate(lines, 1):
            parsed = self.parse_line(line)

            if not parsed:
                continue

            command, args = parsed

            # Check for common errors
            if command == "DELAY" and not args:
                errors.append(f"Line {line_num}: DELAY requires argument")

            elif command == "STRING" and not args:
                errors.append(f"Line {line_num}: STRING requires text")

        return (len(errors) == 0, errors)
