"""Authenticated board telemetry. Set OPI_WEB_TOKEN and select the same YAML profile as the TUI."""
import argparse
import hmac
import ipaddress
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request
import yaml

from core.board_status import gpio_binding, gpio_inventory, snapshot
from core.config_loader import ConfigLoader

DEFAULT_CONFIG = Path(__file__).resolve().parent/"config/main.yaml"


def create_app(config_file=None, *, token=None, collect=snapshot):
    app = Flask(__name__)
    path = Path(config_file or os.environ.get("OPI_CONFIG", DEFAULT_CONFIG))
    def credentials():
        return token if token is not None else os.environ.get("OPI_WEB_TOKEN","")

    @app.before_request
    def authorize():
        expected = credentials()
        if not expected:
            return jsonify(error="Dashboard access is not configured"),503
        auth = request.authorization
        supplied = ""
        if auth and auth.type == "basic" and auth.username == "viewer":
            supplied = auth.password or ""
        elif request.headers.get("Authorization","").startswith("Bearer "):
            supplied = request.headers["Authorization"][7:]
        if not hmac.compare_digest(expected.encode(),supplied.encode()):
            return jsonify(error="Authentication required"),401,{"WWW-Authenticate":'Basic realm="Orange Pi", charset="UTF-8"'}

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; frame-ancestors 'none'"
        return response

    def data():
        with path.open() as stream:
            config = yaml.safe_load(stream)
        if not isinstance(config,dict):
            raise ValueError("Invalid configuration")
        ConfigLoader._check_structure(config)
        return collect(config)

    @app.errorhandler(OSError)
    @app.errorhandler(ValueError)
    @app.errorhandler(yaml.YAMLError)
    def unavailable(exc):
        app.logger.warning("Board status unavailable: %s",exc)
        return jsonify(error="Board status unavailable"),503

    @app.get("/")
    def index():
        return render_template("dashboard.html")

    @app.get("/api/status")
    def status():
        return jsonify(data())

    @app.get("/api/modules")
    def inventory():
        return jsonify(modules=data()["modules"])

    @app.get("/api/gpio")
    def gpio():
        try:
            return jsonify(pins=gpio_inventory(gpio_binding()))
        except (OSError,ImportError,RuntimeError):
            return jsonify(error="GPIO inventory unavailable"),503

    @app.get("/api/gps/location")
    def location():
        fix = data()["gps_location"]
        return jsonify(fix) if fix else (jsonify(error="No fresh GNSS fix"),503)

    @app.post("/api/subghz/capture")
    @app.get("/api/wifi/scan")
    def unavailable_action():
        return jsonify(error="No capture or scan provider in the web service"),501

    return app


app = create_app()


def run_webui(host="127.0.0.1",port=5000,config_file=None,cert=None,key=None):
    if not os.environ.get("OPI_WEB_TOKEN"):
        raise SystemExit("Set OPI_WEB_TOKEN for the viewer account")
    try:
        local = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = False
    if bool(cert) != bool(key) or not local and not cert:
        raise SystemExit("Use --tls-cert and --tls-key for a remote listener, or forward localhost over SSH")
    create_app(config_file).run(host=host,port=port,debug=False,threaded=True,
                                ssl_context=(cert,key) if cert else None)


if __name__ == "__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--host",default="127.0.0.1"); cli.add_argument("--port",type=int,default=5000)
    cli.add_argument("--config",type=Path)
    cli.add_argument("--tls-cert"); cli.add_argument("--tls-key")
    opts=cli.parse_args()
    run_webui(opts.host,opts.port,opts.config,opts.tls_cert,opts.tls_key)
