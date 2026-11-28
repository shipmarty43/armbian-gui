"""Zero 2W peripheral identification. SPI chip select belongs to the kernel."""
from contextlib import ExitStack
from pathlib import Path
import struct
import time

from core.hardware_config import GPIO_KEYS, hardware_errors, lora_settings
from core.radio_lock import acquire_radio
from core.spi_clock import device_clock

TYPES = {"subghz": "CC1101", "nrf24": "nRF24", "nfc": "PN532"}
COMPAT = {"subghz": "ti,cc1101", "nrf24": "nordic,nrf24l01", "nfc": "nxp,pn532"}
ACK = bytes.fromhex("00 00 ff 00 ff 00")
VERSION = bytes.fromhex("00 00 ff 02 fe d4 02 2a 00")
REVERSE = bytes(int(f"{n:08b}"[::-1],2) for n in range(256))


def firmware(write, ready, read, *, now=time.monotonic, sleep=time.sleep):
    def wait():
        end = now()+1.0
        while not ready():
            if now() >= end:
                raise TimeoutError("PN532 ready timeout")
            sleep(0.005)
    write(VERSION)
    wait()
    if read(6) != ACK:
        raise OSError("Invalid PN532 ACK")
    wait()
    frame = read(13)
    if (len(frame) != 13 or frame[:8] != bytes.fromhex("00 00 ff 06 fa d5 03 32")
            or sum(frame[5:-1]) & 255 or frame[-1]):
        raise OSError("Invalid PN532 firmware response")
    return {"IC": "PN532", "firmware": f"{frame[8]}.{frame[9]}", "support": hex(frame[10])}


def spi_status(kind, spi, pins):
    def exchange(data):
        reply = bytes(spi.xfer2(list(data)))
        if len(reply) != len(data):
            raise OSError("Short SPI response")
        return reply
    if kind == "subghz":
        part = exchange([0xf0,0])[1]
        version = exchange([0xf1,0])[1]
        if part != 0 or version in (0,255):
            raise OSError("No valid CC1101 part/version response")
        state = exchange([0xf5,0])[1] & 31
        return dict(part=part, version=version, marcstate=hex(state),
                    **{name:line.read() for name,line in pins.items()})
    if kind == "nrf24":
        status, config = exchange([0,255])
        channel = exchange([5,255])[1]
        if status & 128 or config & 128 or channel > 125 or not (status or config or channel):
            raise OSError("Invalid nRF24 register response")
        rpd = exchange([9,255])[1] & 1
        return dict(status=hex(status),config=hex(config),channel=channel,rpd_latch=rpd)
    # PN532 SPI is LSB-first. Encode every byte on a normal MSB-first spidev.
    def wire(data):
        return exchange(bytes(data).translate(REVERSE)).translate(REVERSE)
    return firmware(lambda frame:wire(b"\x01"+frame), lambda:wire(b"\x02\0")[1] == 1,
                    lambda size:wire(b"\x03"+bytes(size))[1:])


def i2c_firmware(bus, addr, msg):
    def read(n):
        packet=msg.read(addr,n)
        bus.i2c_rdwr(packet)
        return bytes(packet)
    def data(n):
        packet=read(n+1)
        if len(packet)!=n+1 or packet[0]!=1:
            raise OSError("Invalid PN532 I2C readiness byte or response length")
        return packet[1:]
    return firmware(lambda frame:bus.i2c_rdwr(msg.write(addr,frame)),
                    lambda:read(1)==b"\x01", data)


def chip_select(base, controller, cs, header):
    """Resolve the selected kernel CS to a physical pin, including native <0> entries."""
    pio = base/"soc/pinctrl@300b000"
    handle = (pio/"phandle").read_bytes()
    prop = controller/"cs-gpios"
    raw = prop.read_bytes() if prop.exists() else b""
    if len(handle) != 4 or len(raw) % 4:
        raise ValueError("Malformed SPI chip-select map")
    cells = [v[0] for v in struct.iter_unpack(">I",raw)]
    selects = []
    while cells:
        provider = cells.pop(0)
        if not provider:
            selects.append(None)
        elif provider == int.from_bytes(handle,"big") and len(cells) >= 3:
            bank, bit, flags = cells[:3]
            del cells[:3]
            if bit >= 32 or flags != 1:
                raise ValueError("Expected an active-low header GPIO chip select")
            selects.append(bank*32+bit)
        else:
            raise ValueError("Unknown chip-select GPIO provider")
    n = selects[cs] if cs < len(selects) else None
    if n is None:
        if cs not in (0,1):
            raise ValueError("No native header CS at this index")
        pad = ("PH5","PH9")[cs]
        groups = {g.read_bytes():g.parent for g in pio.glob("*/phandle")}
        mux = (controller/"pinctrl-0").read_bytes()
        if not any(g and (g/"function").read_bytes().rstrip(b"\0")==b"spi1" and
                   pad.encode() in (g/"pins").read_bytes().split(b"\0")
                   for g in (groups.get(mux[i:i+4]) for i in range(0,len(mux),4))):
            raise ValueError("Native CS is not muxed to the expected header contact")
        n = 7*32 + (5 if cs == 0 else 9)
    for physical, native, _ in header:
        if native == n:
            return physical
    raise ValueError("Chip select is not routed to the Zero 2W header")


def check_control_pins(config, pad):
    for module, keys in GPIO_KEYS.items():
        section = config.get("hardware",{}).get(module,{})
        if not section.get("enabled"):
            continue
        if module == "lora":
            section = lora_settings(section)
        for key in keys:
            if section.get(key) == pad:
                raise ValueError(f"Kernel CS on physical {pad} conflicts with {module}.{key}")


def identify(kind, config, sysroot=Path("/sys")):
    settings=config["hardware"][kind]
    if not settings.get("enabled"):
        raise ValueError(f"{TYPES[kind]} disabled in this profile")
    # Include every enabled peripheral even if another menu has not opened it.
    problems=hardware_errors(config, config["hardware"].keys())
    if kind in problems:
        raise ValueError("; ".join(problems[kind]))
    base=sysroot/"firmware/devicetree/base"
    if not {b"xunlong,orangepi-zero2w",b"allwinner,sun50i-h618"} <= set((base/"compatible").read_bytes().split(b"\0")):
        raise OSError("Expected Orange Pi Zero 2W")
    with ExitStack() as stack:
        if kind=="nfc" and settings.get("interface")=="pn532_i2c":
            from smbus2 import SMBus, i2c_msg
            n, addr=settings.get("i2c_bus"), settings.get("i2c_address",0x24)
            if type(n) is not int or n < 0 or addr != 0x24:
                raise ValueError("Expected PN532 adapter and 7-bit address 0x24")
            node=(sysroot/f"bus/i2c/devices/i2c-{n}/of_node").resolve()
            if node not in {base/f"soc/i2c@{0x5002000+i*0x400:x}" for i in range(5)}:
                raise ValueError("Expected a header I2C adapter")
            if (sysroot/f"bus/i2c/devices/{n}-0024/driver").exists():
                raise OSError("PN532 address already bound to a kernel driver")
            return i2c_firmware(stack.enter_context(SMBus(n)),addr,i2c_msg)
        import spidev
        import wiringpi_zero2w as gpio
        n, cs=settings["spi_bus"],settings["spi_device"]
        node=(sysroot/f"class/spidev/spidev{n}.{cs}/device/of_node").resolve()
        if (node.parent != base/"soc/spi@5011000" or
                (node/"reg").read_bytes()!=cs.to_bytes(4,"big") or
                any((node/k).exists() for k in ("spi-cpha","spi-cpol","spi-cs-high"))):
            raise ValueError("Expected a mode-0 SPI endpoint on the Zero 2W header")
        ids=(node/"compatible").read_bytes().rstrip(b"\0").decode().split("\0")
        if not set(ids) & {COMPAT[kind],"spidev","rohm,dh2228fv"} or set(ids) & (set(COMPAT.values()) - {COMPAT[kind]} | {"semtech,sx1262"}):
            raise ValueError(f"Unexpected SPI client: {', '.join(ids)}")
        selected = chip_select(base,node.parent,cs,gpio.header_map())
        if settings.get("cs_header",selected) != selected:
            raise ValueError(f"Configured physical CS differs from the kernel route to {selected}")
        check_control_pins(config,selected)
        stack.enter_context(acquire_radio())
        pins={}
        if kind=="nrf24":
            stack.enter_context(gpio.request_output(settings["ce_pin"],initial=0))
        if kind=="subghz":
            for key in ("gdo0_pin","gdo2_pin"):
                if settings.get(key) is not None:
                    pins[key]=stack.enter_context(gpio.request_input(settings[key]))
        spi=spidev.SpiDev()
        stack.callback(spi.close)
        spi.open(n,cs)
        spi.mode=0
        spi.lsbfirst=False
        limit=device_clock(n,cs,500000,{"nfc":5000000,"nrf24":10000000,"subghz":6500000}[kind],sysfs=sysroot)
        spi.max_speed_hz=limit
        if spi.mode!=0 or spi.max_speed_hz!=limit:
            raise OSError("SPI settings did not read back")
        return dict(spi=f"spidev{n}.{cs}", cs_header=selected, clock_hz=limit, **spi_status(kind,spi,pins))


def diagnostic_menu(module,kind):
    def inspect():
        try:
            status=identify(kind,module.get_config())
            module.show_message(TYPES[kind],"\n".join(f"{key}: {v}" for key,v in status.items()))
        except (ImportError,KeyError,OSError,ValueError,RuntimeError) as exc:
            module.show_error(str(exc))
    return [(f"{TYPES[kind]} · device information",inspect)]
