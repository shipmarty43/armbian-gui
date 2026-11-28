import json
import time
import pytest
from core.board_status import snapshot, gnss
from webui_server import create_app


def test_shared_snapshot_and_access(tmp_path):
    model=tmp_path/"firmware/devicetree/base/model"; model.parent.mkdir(parents=True); model.write_bytes(b"Orange Pi\0")
    battery=tmp_path/"class/power_supply/BAT0"; battery.mkdir(parents=True)
    for name,value in (("type","Battery"),("capacity","51"),("status","Unknown")):
        (battery/name).write_text(value)
    fan=tmp_path/"class/hwmon/hwmon2"; fan.mkdir(parents=True)
    (fan/"name").write_text("pwmfan"); (fan/"pwm1").write_text("128")
    fix=tmp_path/"fix"; now=time.time()
    fix.write_text(json.dumps(dict(generated=now,source="waveshare",fix=dict(time=now,lat=50.1,lon=31.2))))
    profile=tmp_path/"profile.yaml"; profile.write_text('modules:\n  autoload: [system]\n')
    app=create_app(profile,token="test-password", collect=lambda c:snapshot(c,tmp_path,fix,lambda:now))
    client=app.test_client(); headers={"Authorization":"Bearer test-password"}
    for path in ("/","/api/modules","/api/status","/api/gps/location","/static/dashboard.js"):
        assert client.get(path).status_code==401
    assert client.get("/api/status",auth=("wrong","test-password")).status_code==401
    assert client.get("/",auth=("viewer","test-password")).status_code==200
    response=client.get("/api/status",headers=headers)
    assert response.json["board"]=="Orange Pi"
    assert response.json["batteries"]=={"BAT0":{"percent":51,"state":"Unknown"}}
    assert response.json["fans"]["hwmon2"]=={"duty_percent":50.2,"rpm":None}
    assert response.json["gps_location"]["source"]=="waveshare"
    assert response.json["modules"][0]["configuration"]=="selected"
    assert response.headers["Cache-Control"]=="no-store"
    assert "Access-Control-Allow-Origin" not in response.headers
    assert client.post("/api/subghz/capture",headers=headers).status_code==501
    assert gnss(fix,now+70) is None
    fix.unlink(); assert client.get("/api/gps/location",headers=headers).status_code==503
    assert create_app(profile,token="").test_client().get("/").status_code==503


def test_firmware_frame_and_registers():
    from core.header_peripherals import firmware,spi_status,ACK,VERSION
    frame=bytes.fromhex("00 00 ff 06 fa d5 03 32 01 06 07 e8 00")
    def query(response):
        io=iter((ACK,response))
        written=[]
        out=firmware(written.append,lambda:True,lambda n:next(io))
        assert written==[VERSION]
        return out
    assert query(frame)["firmware"]=="1.6"
    with pytest.raises(OSError): query(frame[:-2]+b"\0\0")
    class Spi:
        def __init__(self, values): self.values=iter(values); self.sent=[]
        def xfer2(self, buf): self.sent.append(buf); return next(self.values)
    spi=Spi(([1,0],[1,20],[1,1])); assert spi_status("subghz",spi,{})["version"]==20
    assert spi.sent==[[0xf0,0],[0xf1,0],[0xf5,0]]
    spi=Spi(([14,8],[14,8],[14,0])); assert spi_status("nrf24",spi,{})["channel"]==8
    assert spi.sent==[[0,255],[5,255],[9,255]]
    with pytest.raises(OSError): spi_status("nrf24",Spi(([255,255],[255,255])),{})


def test_kernel_selects_and_pin_conflicts(tmp_path):
    import struct
    from core.header_peripherals import chip_select, check_control_pins
    ctl=tmp_path/"soc/spi@5011000"; pio=tmp_path/"soc/pinctrl@300b000"
    group=pio/"cs0"; ctl.mkdir(parents=True); group.mkdir(parents=True)
    cell=lambda n: struct.pack(">I",n)
    (pio/"phandle").write_bytes(cell(7)); (group/"phandle").write_bytes(cell(8))
    (group/"pins").write_bytes(b"PH5\0"); (group/"function").write_bytes(b"spi1\0")
    (ctl/"pinctrl-0").write_bytes(cell(8))
    (ctl/"cs-gpios").write_bytes(cell(0)+struct.pack(">4I",7,8,3,1))
    header=[(24,229,"PH5"),(40,259,"PI3")]
    assert chip_select(tmp_path,ctl,0,header)==24
    assert chip_select(tmp_path,ctl,1,header)==40
    with pytest.raises(ValueError,match="conflicts"):
        check_control_pins({"hardware":{"nrf24":{"enabled":True,"ce_pin":40}}},40)
    with pytest.raises(ValueError,match="index"):
        chip_select(tmp_path,ctl,2,header)


def test_pn532_i2c_uses_raw_messages_with_ready_byte():
    from core.header_peripherals import i2c_firmware,ACK,VERSION
    frame=bytes.fromhex("00 00 ff 06 fa d5 03 32 01 06 07 e8 00")
    class Message(bytearray):
        @staticmethod
        def write(addr,data):
            assert addr==0x24 and data==VERSION
            m=Message(data); m.write_op=True; return m
        @staticmethod
        def read(addr,n):
            assert addr==0x24
            m=Message(n); m.write_op=False; return m
    class Bus:
        def __init__(self): self.responses=iter((b"\x01",b"\x01"+ACK,b"\x01",b"\x01"+frame))
        def i2c_rdwr(self,m):
            if not m.write_op:
                result=next(self.responses); assert len(m)==len(result); m[:]=result
    assert i2c_firmware(Bus(),0x24,Message)["IC"]=="PN532"


def test_tui_board_page_shows_same_state(monkeypatch):
    from modules.system.system_module import SystemModule
    from core import board_status
    module=SystemModule()
    monkeypatch.setattr(module,"get_config",lambda: {})
    state=dict(board="Orange Pi",kernel="fixture",temperatures={},batteries={"UPS":dict(percent=51,state="Unknown")},
               interfaces={},modules=[],gps_location=None)
    monkeypatch.setattr(board_status,"snapshot",lambda config:state)
    seen=[]
    monkeypatch.setattr(module,"show_message",lambda title,body:seen.append((title,body)))
    dict(module.get_menu_items())["Board telemetry"]()
    assert "51%, Unknown" in seen[0][1]


def test_runtime_follows_live_tui_and_exact_profile(tmp_path):
    from core.board_status import loader_session,live_modules
    directory=tmp_path/"private"; cfg={"modules":{"autoload":["system"]}}
    with loader_session(cfg,{"system":"loaded"},directory):
        assert live_modules(cfg,directory)=={"system":"loaded"}
        assert live_modules({},directory)=={}
    assert live_modules(cfg,directory)=={}


@pytest.mark.parametrize("module_name,kind,entry", [
    ("modules.subghz.subghz_module","subghz","SubGHzModule"),
    ("modules.nfc.nfc_module","nfc","NFCModule"),
    ("modules.nrf24.nrf24_module","nrf24","NRF24Module")])
def test_board_tui_opens_devices_only_on_identification(module_name,kind,entry,monkeypatch,tmp_path):
    import importlib
    from core import header_peripherals
    monkeypatch.chdir(tmp_path)
    module=getattr(importlib.import_module(module_name),entry)()
    cfg={"system":{"device":"orangepi_zero2w"},"hardware":{kind:{"enabled":True}}}
    monkeypatch.setattr(module,"get_config",lambda:cfg)
    calls=[]
    monkeypatch.setattr(header_peripherals,"identify",lambda k,c:(calls.append(k) or {"test":42}))
    monkeypatch.setattr(module,"show_message",lambda title,body:calls.append(body))
    module.on_load()
    option,=module.get_menu_items()
    assert calls==[]
    option[1]()
    assert calls==[kind,"test: 42"]
    module.on_unload()


def test_spi_probe_releases_every_descriptor_on_error(tmp_path,monkeypatch):
    import sys
    from contextlib import contextmanager
    from types import SimpleNamespace
    from core import header_peripherals as hp
    base=tmp_path/"firmware/devicetree/base"
    pio=base/"soc/pinctrl@300b000"; group=pio/"cs0"; group.mkdir(parents=True)
    ctl=base/"soc/spi@5011000"; target=ctl/"client@0"; target.mkdir(parents=True)
    base.joinpath("compatible").write_bytes(b"xunlong,orangepi-zero2w\0allwinner,sun50i-h618\0")
    cell=lambda n:n.to_bytes(4,"big")
    for p,data in ((pio/"phandle",cell(4)),(group/"phandle",cell(5)),(group/"pins",b"PH5\0"),
                   (group/"function",b"spi1\0"),(ctl/"pinctrl-0",cell(5)),(target/"reg",cell(0)),
                   (target/"compatible",b"rohm,dh2228fv\0"),(target/"spi-max-frequency",cell(200000))):
        p.write_bytes(data)
    spi_node=tmp_path/"class/spidev/spidev7.0/device"; spi_node.mkdir(parents=True)
    (spi_node/"of_node").symlink_to(target)
    events=[]
    @contextmanager
    def owned(what):
        events.append(what)
        try: yield
        finally: events.append("close-"+what)
    class Spi:
        def open(self,b,c): events.append(f"spi{b}.{c}")
        def xfer2(self,msg): raise OSError("test SPI failure")
        def close(self): events.append("close-spi")
    monkeypatch.setattr(hp,"acquire_radio",lambda:owned("lock"))
    monkeypatch.setitem(sys.modules,"spidev",SimpleNamespace(SpiDev=Spi))
    monkeypatch.setitem(sys.modules,"wiringpi_zero2w",SimpleNamespace(header_map=lambda:[(24,229,"PH5")],
        request_output=lambda pin,initial:owned(f"ce{pin}={initial}")))
    cfg={"hardware":{"nrf24":{"enabled":True,"spi_bus":7,"spi_device":0,"ce_pin":18,"cs_header":24}}}
    with pytest.raises(OSError,match="test SPI failure"): hp.identify("nrf24",cfg,tmp_path)
    assert events==["lock","ce18=0","spi7.0","close-spi","close-ce18=0","close-lock"]
    events.clear(); cfg["hardware"]["nrf24"]["cs_header"]=26
    with pytest.raises(ValueError,match="CS differs"): hp.identify("nrf24",cfg,tmp_path)
    assert events==[]


def test_web_gpio_reads_both_board_profiles_without_claims(tmp_path,monkeypatch):
    import sys
    from types import SimpleNamespace
    from core import board_status
    import webui_server
    prop=tmp_path/"firmware/devicetree/base/compatible"; prop.parent.mkdir(parents=True)
    profile=tmp_path/"profile"; profile.write_text("{}")
    client=create_app(profile,token="test").test_client()
    monkeypatch.setattr(webui_server,"gpio_binding",lambda:board_status.gpio_binding(tmp_path))
    assert client.get("/api/gpio").status_code==401
    for board,soc,lib,native,pad in (("zero2w","allwinner,sun50i-h618","wiringpi_zero2w",270,"PI14"),
                                      ("zero3w","arm,sun60iw2p1","wiringpi_zero3w",354,"PL2")):
        prop.write_bytes(f"xunlong,orangepi-{board}\0{soc}\0".encode())
        api=SimpleNamespace(header_map=lambda:[(16,native,pad)],
                            line_info=lambda pin:SimpleNamespace(used=True,consumer="fixture",direction="input"))
        monkeypatch.setitem(sys.modules,lib,api)
        response=client.get("/api/gpio",auth=("viewer","test"))
        assert response.json["pins"]==[dict(pin=16,native=native,name=pad,used=True,consumer="fixture",direction="input")]


def test_pn532_spi_bit_order_ack_and_deadline():
    from core.header_peripherals import spi_status, firmware, ACK, VERSION
    frame=bytes.fromhex("00 00 ff 06 fa d5 03 32 01 06 07 e8 00")
    transactions=iter(((b"\x01"+VERSION, bytes(10)),(b"\x02\0",b"\0\x01"),
                       (b"\x03"+bytes(6),b"\0"+ACK),(b"\x02\0",b"\0\x01"),
                       (b"\x03"+bytes(13),b"\0"+frame)))
    reverse=lambda data: [int(f"{n:08b}"[::-1],2) for n in data]
    class Spi:
        def xfer2(self, buf):
            request,reply=next(transactions)
            assert buf==reverse(request)
            return reverse(reply)
    assert spi_status("nfc",Spi(),{})["support"]=="0x7"
    assert list(transactions)==[]
    clock=iter((0,2))
    with pytest.raises(TimeoutError):
        firmware(lambda _:None,lambda:False,lambda _:None,now=lambda:next(clock),sleep=lambda _:None)
    with pytest.raises(OSError,match="ACK"):
        firmware(lambda _:None,lambda:True,lambda _:bytes(6))
