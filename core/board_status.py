"""Read OS telemetry for the terminal and web dashboards without opening peripherals."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
import time

from core.hardware_config import hardware_errors, module_settings


def value(path):
    try:
        return path.read_text().strip().rstrip("\0")
    except (OSError, UnicodeError):
        return None


def modules(config):
    names = config.get("modules", {}).get("autoload", [])
    errors = hardware_errors(config, names)
    result = []
    for name in names:
        try:
            enabled = module_settings(config, name).get("enabled", True)
        except ValueError:
            enabled = False
        result.append(dict(name=name, enabled=enabled, configuration="conflict" if name in errors else
                           "selected" if enabled else "disabled", errors=errors.get(name, [])))
    return result


def gnss(path, now):
    raw = value(path)
    try:
        data = json.loads(raw) if raw else {}
        fix = data.get("fix") or {}
        age = now - float(fix["time"])
        snapshot_age = now - float(data["generated"])
        lat, lon = float(fix["lat"]), float(fix["lon"])
        if (not -1 <= age <= 10 or not -1 <= snapshot_age <= 10 or
                not -90 <= lat <= 90 or not -180 <= lon <= 180):
            return None
        return dict(latitude=lat,longitude=lon,source=data.get("source"),age_seconds=round(max(0,age),1))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return None


def _sessions():
    return Path(os.environ.get("XDG_RUNTIME_DIR") or
                ("/run" if os.getuid() == 0 else f"/run/user/{os.getuid()}")) / "armbian-gui"


def _profile(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


@contextmanager
def loader_session(config, states, directory=None):
    """Keep a session discoverable only while its owner holds the file lock."""
    directory = directory or _sessions()
    directory.mkdir(mode=0o700,exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        raise PermissionError("Expected a private runtime directory")
    with tempfile.NamedTemporaryFile(dir=directory,prefix="tui-",mode="w+") as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        json.dump(dict(profile=_profile(config),states=dict(states)),stream)
        stream.flush()
        yield


def live_modules(config, directory=None):
    directory = directory or _sessions()
    try:
        if directory.is_symlink() or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
            return {}
        files = list(directory.glob("tui-*"))
    except OSError:
        return {}
    digest = _profile(config)
    latest, states = 0, {}
    for path in files:
        try:
            with path.open() as stream:
                try:
                    fcntl.flock(stream,fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    stamp=os.fstat(stream.fileno()).st_mtime_ns
                    session=json.load(stream)
                    if stamp > latest and session.get("profile")==digest and isinstance(session.get("states"),dict):
                        latest, states = stamp, session["states"]
        except (OSError,ValueError,AttributeError):
            continue
    return states


def snapshot(config, sysroot=Path("/sys"), gnss_path=Path("/run/opi-gnss/status.json"), now=time.time):
    temps, batteries = {}, {}
    for z in sorted((sysroot/"class/thermal").glob("thermal_zone*")):
        try:
            celsius = int(value(z/"temp")) / 1000
        except (TypeError, ValueError):
            continue
        temps[z.name] = dict(sensor=value(z/"type"), celsius=celsius)
    for dev in sorted((sysroot/"class/power_supply").glob("*")):
        if value(dev/"type") == "Battery":
            capacity=value(dev/"capacity")
            batteries[dev.name] = dict(percent=int(capacity) if capacity and capacity.isdecimal()
                                       and 0 <= int(capacity) <= 100 else None, state=value(dev/"status"))
    fans = {}
    for dev in sorted((sysroot/"class/hwmon").glob("hwmon*")):
        if value(dev/"name") not in ("pwmfan","pwm_fan") and value(dev/"device/of_node/compatible") != "pwm-fan":
            continue
        duty, rpm = value(dev/"pwm1"), value(dev/"fan1_input")
        fans[dev.name] = dict(duty_percent=round(100*int(duty)/255,1) if duty and duty.isdecimal()
                              and int(duty)<=255 else None, rpm=int(rpm) if rpm and rpm.isdecimal() else None)
    links = {p.name:value(p/"operstate") for p in sorted((sysroot/"class/net").glob("*"))}
    inventory = modules(config)
    loaded = live_modules(config)
    for row in inventory:
        row["loader_state"] = loaded.get(row["name"])
    return dict(board=value(sysroot/"firmware/devicetree/base/model"), kernel=platform.release(),
                temperatures=temps,batteries=batteries,fans=fans,interfaces=links,modules=inventory,
                gps_location=gnss(gnss_path,now()))


def format_report(state):
    lines = [state["board"] or "Board model unavailable", "Linux " + state["kernel"]]
    for name, sensor in state["temperatures"].items():
        lines.append(f"{sensor['sensor'] or name}: {sensor['celsius']:g} °C")
    for name, battery in state["batteries"].items():
        level = "unknown" if battery["percent"] is None else f"{battery['percent']}%"
        lines.append(f"{name}: {level}, {battery['state'] or 'unknown'}")
    for name, fan in state.get("fans",{}).items():
        duty = f"{fan['duty_percent']}%" if fan['duty_percent'] is not None else "unknown duty"
        rpm = f"{fan['rpm']} RPM" if fan['rpm'] is not None else "no tachometer reading"
        lines.append(f"Fan {name}: {duty}, {rpm}")
    lines.extend(f"{name}: {status or 'unknown'}" for name,status in state["interfaces"].items())
    fix = state["gps_location"]
    lines.append(f"GNSS {fix['source']}: {fix['latitude']}, {fix['longitude']}" if fix else "GNSS: no fresh fix")
    for module in state["modules"]:
        lines.append(module["name"] + ": " + (module.get("loader_state") or ", ".join(module["errors"]) or module["configuration"]))
    return "\n".join(lines)
