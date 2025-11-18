"""
Web UI Server for CyberDeck Remote Access
Flask-based web interface for remote control
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import threading
import logging
import os

app = Flask(__name__)
CORS(app)

# Global state
cyberdeck_state = {
    'modules': [],
    'status': 'idle',
    'gps_location': None,
    'networks_found': 0,
    'last_signal': None
}


@app.route('/')
def index():
    """Main dashboard"""
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    """Get CyberDeck status"""
    return jsonify(cyberdeck_state)


@app.route('/api/modules')
def get_modules():
    """List available modules"""
    return jsonify({
        'modules': [
            {'name': 'SubGHz', 'enabled': True, 'status': 'ready'},
            {'name': 'NFC', 'enabled': True, 'status': 'ready'},
            {'name': 'WiFi', 'enabled': True, 'status': 'idle'},
            {'name': 'GPS', 'enabled': True, 'status': 'no_fix'},
            {'name': 'SDR', 'enabled': True, 'status': 'idle'},
        ]
    })


@app.route('/api/subghz/capture', methods=['POST'])
def subghz_capture():
    """Capture Sub-GHz signal"""
    data = request.json
    freq = data.get('frequency', 433.92)
    duration = data.get('duration', 5)
    
    # TODO: Integrate with actual SubGHz module
    
    return jsonify({
        'success': True,
        'message': f'Capturing {freq}MHz for {duration}s',
        'signal_id': 'sig_001'
    })


@app.route('/api/gps/location')
def gps_location():
    """Get GPS location"""
    # TODO: Integrate with GPS module
    return jsonify({
        'latitude': 55.7558,
        'longitude': 37.6173,
        'altitude': 156,
        'satellites': 8
    })


@app.route('/api/wifi/scan')
def wifi_scan():
    """Scan WiFi networks"""
    # TODO: Integrate with WiFi module
    return jsonify({
        'networks': [
            {'ssid': 'TestNetwork', 'bssid': '00:11:22:33:44:55', 'rssi': -45, 'channel': 6},
            {'ssid': 'Demo_AP', 'bssid': 'AA:BB:CC:DD:EE:FF', 'rssi': -65, 'channel': 11},
        ]
    })


def run_webui(host='0.0.0.0', port=5000):
    """Run Web UI server"""
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    # Create templates directory
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    print("CyberDeck Web UI Server")
    print(f"Starting on http://0.0.0.0:5000")
    print("Access from any browser on local network")
    
    run_webui()
