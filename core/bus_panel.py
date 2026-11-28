"""Client for the installed Orange Pi boot-profile helper."""
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
        if not isinstance(profile, str) or not re.fullmatch(
                r"a733-[a-z0-9-]{1,30}(?:\+[a-z0-9-]{1,12}){0,19}|off|(?:single|shared|(?:i2c[0-4]|uart[2-5]|pwm[1-4])-[a-z][a-z0-9-]{0,12})(?:\+[a-z0-9-]{1,12}){0,13}", profile):
            raise PanelError("Выберите маршрут гребёнки", 400)
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
                             400 if "INVALID:" in proc.stderr else
                             409 if any(m in proc.stderr for m in ("CONFLICT:", "STALE:", "No matching profile change")) else 503)
        return json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise PanelError("Нет ответа от opi-bus-profile") from exc


def report(state):
    if state["profile"] == "a733":
        return "\n".join([", ".join(state["buses"]) or "Контроллеры SPI выключены",
            *(f"{r['bus']} CS{r['cs']} ({r['pin']}) · {r['device']} · режим {r['mode']} · "
              f"предел DT {r['ceiling_hz'] or '—'} Гц {r.get('endpoint') or ''}".rstrip() for r in state["rows"])])
    lines = [PROFILES[state["profile"]]]
    for row in state["rows"]:
        extra = " · ".join(str(row[k]) for k in ("endpoint", "lock") if row.get(k))
        lines.append(f"CS{row['cs']} {row['device']} · вывод {row['pin'] or '?'} ({row['pad'] or '?'}) · "
                     f"{row['requested_hz']} Гц, предел {row['ceiling_hz']} Гц" + (" · " + extra if extra else ""))
    for cs, hz in state.get("parked", {}).items():
        lines.append(f"CS{cs} · сохранено {hz} Гц")
    return "\n".join(lines)


def names(owners):
    return " + ".join(o["label"] for o in owners) or "—"


def menu(ui):
    try:
        state = query("state")
        groups = list(dict.fromkeys(option["group"] for option in state["choices"]))
        items = ["Контакты сейчас и при следующей загрузке", *groups]
        if state["undo"]:
            items.append("Откатить последнее изменение")
        choice = ui.show_menu("Шины и контакты · " + state.get("board", "Zero 2W"), items)
        if choice is None or not 0 <= choice < len(items):
            return
        if choice == 0:
            live = {r["pin"]: r for r in state["live"]["pins"]}
            rows = []
            for row in state["current"]["pins"]:
                now = names(live[row["pin"]]["owners"]) if row["pin"] in live else "нет данных"
                if row["pin"] in live and live[row["pin"]].get("gpio_consumer"):
                    now += " [GPIO: " + live[row["pin"]]["gpio_consumer"] + "]"
                routes = " / ".join(row.get("functions", ()))
                rows.append(f"{row['pin']:2} {row['pad']}   {now} → {names(row['owners'])}" +
                            ("   ·   " + routes if routes else ""))
            source = "DT и GPIO" if state["live"]["gpio_known"] else "DT, сведения gpiochip недоступны"
            ui.show_menu(f"Физический вывод · сейчас ({source}) → следующая загрузка (DT)", rows)
            return
        if choice > len(groups):
            query("undo", token=state["undo"])
        else:
            group = groups[choice - 1]
            options = [o for o in state["choices"] if o["group"] == group]
            heading = group + " · выберите маршрут для предпросмотра"
            if group in ("SPI", "SPI1"):
                heading += "\nСейчас\n" + report(state["live"]) + "\nПри следующей загрузке\n" + report(state["current"])
            index = ui.show_menu(heading, [o["label"] for o in options])
            if index is None or not 0 <= index < len(options):
                return
            profile = options[index]["id"]
            plan = query("preview", profile)
            offer = plan.get("alternative")
            if offer:
                response = ui.show_menu("Конфликт выводов\n" + "\n".join(plan["issues"]),
                                        ["Назад", "Предпросмотр · " + offer["label"]])
                if response != 1:
                    return
                profile = offer["id"]
                plan = query("preview", profile)
            preview = (plan.get("transition") or options[index]["label"]) + "\n" + "\n".join(
                f"{r['pin']} {r['pad']}   {names(r['before'])} → {names(r['after'])}" for r in plan["changes"])
            if plan["warnings"]:
                preview += "\n" + "\n".join(plan["warnings"])
            if group in ("SPI", "SPI1"):
                preview += "\nПосле применения\n" + report(plan["candidate"])
            if plan["issues"]:
                ui.show_menu("Применение заблокировано\n" + "\n".join(plan["issues"]) + "\n" + preview, ["Назад"])
                return
            if not plan["changed"]:
                ui.show_message("Профиль уже выбран", preview)
                return
            if ui.show_menu(preview, ["Назад", "Сохранить для следующей загрузки"]) != 1:
                return
            query("apply", profile, plan["token"])
        ui.show_message("Шины и контакты", "Сохранено для следующей загрузки.")
    except PanelError as exc:
        ui.show_error(str(exc))
