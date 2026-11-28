"""A real terminal process and a separate Flask client share one selected profile."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import sys
import termios
import fcntl
import time

from webui_server import create_app


def test_real_terminal_publishes_and_releases_loader_state(tmp_path,monkeypatch):
    repo=Path(__file__).resolve().parents[1]
    monkeypatch.setenv("XDG_RUNTIME_DIR",str(tmp_path))
    cfg=tmp_path/"profile.yaml"
    cfg.write_text(json.dumps({"system":{"device":"orangepi_zero2w","log_path":str(tmp_path/"logs")},
        "hardware":{"battery":{"enabled":False},"thermal":{"monitoring":False}},
        "modules":{"paths":[str(repo/"modules")],"autoload":["system"]},
        "network":{"wifi":{"interface":"qa-none"},"lte":{"device":str(tmp_path/"no-modem")}}}))
    web=create_app(cfg,token="only-for-test").test_client()
    def state():
        return web.get("/api/modules",auth=("viewer","only-for-test")).get_json()["modules"][0]["loader_state"]
    assert state() is None
    pid,fd=pty.fork()
    if pid==0:
        fcntl.ioctl(0,termios.TIOCSWINSZ,struct.pack("HHHH",30,100,0,0))
        os.chdir(tmp_path)
        os.environ.update(TERM="xterm",PATH=str(tmp_path/"no-external-utilities"))
        os.execv(sys.executable,[sys.executable,str(repo/"core/main.py"),"--config",str(cfg)])
    exited=False
    try:
        received=bytearray()
        end=time.monotonic()+12
        while time.monotonic()<end:
            if select.select([fd],[],[],0.1)[0]:
                received.extend(os.read(fd,8192))
            if state() and b"System" in received:
                break
        assert state() and state().startswith("initialized"), bytes(received[-900:])
        os.write(fd,b"q")
        for _ in range(100):
            if os.waitpid(pid,os.WNOHANG)[0]:
                exited=True;break
            time.sleep(0.05)
        assert exited
        assert state() is None
    finally:
        if not exited:
            try: os.kill(pid,signal.SIGTERM)
            except ProcessLookupError: pass
            os.waitpid(pid,0)
        os.close(fd)
