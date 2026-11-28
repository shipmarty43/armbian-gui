"""Client for the installed Zero 2W boot-profile helper."""
import json
import os
from pathlib import Path
import re
import subprocess

HELPERS = (Path("/opt/armbian-config-zero2w/bin/opi-bus-profile"), Path("/usr/bin/opi-bus-profile"))
PROFILES = {"single": "SX1262", "shared": "SX1262 + CC1101 + nRF24", "off": "Выключен",
            "external": "Другой маршрут SPI1", "unknown": "Нет данных"}


class PanelError(RuntimeError):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def validate(action, profile=None, token=None):
    if action not in ("state", "preview", "apply", "undo"):
        raise PanelError("Неизвестная операция", 400)
    args = [action]
    if action in ("apply", "preview"):
        if not isinstance(profile, str) or profile not in ("shared", "single", "off"):
            raise PanelError("Выберите профиль SPI1", 400)
        args.append(profile)
    elif profile is not None:
        raise PanelError("Лишний профиль", 400)
    if action in ("apply", "undo"):
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
            raise PanelError("Требуется актуальная версия конфигурации", 400)
        args.append(token)
    elif token is not None:
        raise PanelError("Лишняя версия", 400)
    return args


def query(action, profile=None, token=None, *, operator=True):
    args = validate(action, profile, token)
    helper = next((p for p in HELPERS if p.is_file()), None)
    if not helper:
        raise PanelError("Установите пакет конфигуратора с opi-bus-profile.")
    cmd = [str(helper), *args]
    # The journal under /boot is private. An operator reads it through the same
    # narrow sudo grant used to apply/undo. Unprivileged reads still show the bus.
    elevation = operator and os.geteuid() != 0
    try:
        kwargs = dict(text=True, capture_output=True, timeout=90)
        if elevation and Path("/usr/bin/sudo").is_file():
            proc = subprocess.run(["/usr/bin/sudo", "-n", "--", *cmd], **kwargs)
            if proc.returncode and action in ("state", "preview") and proc.stderr.startswith("sudo:"):
                proc = subprocess.run(cmd, **kwargs)
        else:
            proc = subprocess.run(cmd, **kwargs)
        if proc.returncode:
            detail = proc.stderr.strip().splitlines()
            raise PanelError(detail[-1] if detail else "Операция отклонена",
                             409 if "STALE:" in proc.stderr or "No matching profile change" in proc.stderr else 503)
        return json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise PanelError("Нет ответа от opi-bus-profile") from exc


def report(state):
    lines = [PROFILES[state["profile"]]]
    for row in state["rows"]:
        extra = " · ".join(str(row[k]) for k in ("endpoint", "lock") if row.get(k))
        lines.append(f"CS{row['cs']} {row['device']} · вывод {row['pin'] or '?'} ({row['pad'] or '?'}) · "
                     f"{row['requested_hz']} Гц, предел {row['ceiling_hz']} Гц" + (" · " + extra if extra else ""))
    for cs, hz in state.get("parked", {}).items():
        lines.append(f"CS{cs} · сохранено {hz} Гц")
    return "\n".join(lines)


def menu(ui):
    try:
        state = query("state")
        title = ("Шины и контакты · SPI1 · CLK 23 / MOSI 19 / MISO 21\n"
                 "Сейчас\n" + report(state["live"]) + "\nПри следующей загрузке\n" + report(state["current"]))
        profiles = ("single", "shared", "off")
        items = [PROFILES[p] for p in profiles]
        if state["undo"]:
            items.append("Откатить последнее изменение")
        choice = ui.show_menu(title, items)
        if choice is None or not 0 <= choice < len(items):
            return
        if choice == len(profiles):
            query("undo", token=state["undo"])
        else:
            profile = profiles[choice]
            plan = query("preview", profile)
            preview = "Выбрано\n" + report(plan["current"]) + "\nПосле применения\n" + report(plan["candidate"])
            if not plan["changed"]:
                ui.show_message("Профиль уже выбран", preview)
                return
            if ui.show_menu(preview, ["Назад", "Сохранить для следующей загрузки"]) != 1:
                return
            query("apply", profile, plan["token"])
        ui.show_message("Шины и контакты", "Сохранено для следующей загрузки.")
    except PanelError as exc:
        ui.show_error(str(exc))
