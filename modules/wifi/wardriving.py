"""
Wardriving - WiFi network mapping с GPS синхронизацией
"""

import subprocess
import time
import re
import os
import json
from datetime import datetime
from typing import List, Dict, Optional


class WardrivingScanner:
    """Wardriving сканер WiFi сетей с GPS"""

    def __init__(self, interface: str, gps_module=None):
        """
        Initialize wardriving scanner.

        Args:
            interface: WiFi interface
            gps_module: GPS module instance
        """
        self.interface = interface
        self.gps_module = gps_module
        self.networks = []
        self.scanning = False

        self.output_dir = "maps"
        os.makedirs(self.output_dir, exist_ok=True)

    def start_scan(self, duration: int = 3600):
        """
        Start wardriving scan.

        Args:
            duration: Scan duration in seconds (0 = infinite)
        """
        self.scanning = True
        self.networks = []

        start_time = time.time()

        while self.scanning:
            if duration > 0 and (time.time() - start_time) > duration:
                break

            # Scan networks
            networks = self._scan_networks()

            # Get GPS position
            gps_pos = None
            if self.gps_module:
                gps_pos = self.gps_module.get_position()

            # Add networks with GPS coordinates
            for network in networks:
                network['gps'] = gps_pos
                network['timestamp'] = datetime.now().isoformat()

                # Check if network already exists (update position)
                existing = next(
                    (n for n in self.networks if n['bssid'] == network['bssid']),
                    None
                )

                if existing:
                    # Update signal strength and position
                    existing['signal'] = network['signal']
                    existing['gps'] = gps_pos
                else:
                    self.networks.append(network)

            time.sleep(1)  # Scan interval

    def stop_scan(self):
        """Stop scanning"""
        self.scanning = False

    def _scan_networks(self) -> List[Dict]:
        """
        Scan WiFi networks.

        Returns:
            List of networks
        """
        networks = []

        try:
            # Use iwlist for scanning
            result = subprocess.check_output(
                ['iwlist', self.interface, 'scan'],
                stderr=subprocess.DEVNULL,
                timeout=5
            )

            output = result.decode('utf-8', errors='ignore')

            # Parse output
            current_network = None

            for line in output.split('\n'):
                line = line.strip()

                # New cell
                if 'Cell' in line and 'Address:' in line:
                    if current_network:
                        networks.append(current_network)

                    bssid_match = re.search(r'Address: ([0-9A-Fa-f:]{17})', line)
                    current_network = {
                        'bssid': bssid_match.group(1) if bssid_match else 'Unknown',
                        'ssid': '',
                        'channel': 0,
                        'signal': -100,
                        'encryption': 'Unknown',
                        'frequency': 0.0
                    }

                # ESSID
                elif 'ESSID:' in line:
                    essid_match = re.search(r'ESSID:"(.+?)"', line)
                    if essid_match and current_network:
                        current_network['ssid'] = essid_match.group(1)

                # Channel
                elif 'Channel' in line:
                    channel_match = re.search(r'Channel[:\s]+(\d+)', line)
                    if channel_match and current_network:
                        current_network['channel'] = int(channel_match.group(1))

                # Frequency
                elif 'Frequency:' in line:
                    freq_match = re.search(r'Frequency:([\d.]+)', line)
                    if freq_match and current_network:
                        current_network['frequency'] = float(freq_match.group(1))

                # Signal
                elif 'Signal level' in line:
                    signal_match = re.search(r'Signal level[=:]\s*(-?\d+)', line)
                    if signal_match and current_network:
                        current_network['signal'] = int(signal_match.group(1))

                # Encryption
                elif 'Encryption key:on' in line:
                    if current_network:
                        current_network['encryption'] = 'WEP'

                elif 'WPA' in line:
                    if current_network:
                        if 'WPA3' in line:
                            current_network['encryption'] = 'WPA3'
                        elif 'WPA2' in line:
                            current_network['encryption'] = 'WPA2'
                        else:
                            current_network['encryption'] = 'WPA'

            # Add last network
            if current_network:
                networks.append(current_network)

        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            print(f"Scan error: {e}")

        return networks

    def export_to_wigle(self, filename: str):
        """
        Export to Wigle CSV format.

        Args:
            filename: Output filename
        """
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w') as f:
            # Header
            f.write("WigleWifi-1.4,appRelease=CyberDeck,model=OrangePi,release=1.0\n")
            f.write("MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,CurrentLatitude,CurrentLongitude,AltitudeMeters,AccuracyMeters,Type\n")

            # Data
            for network in self.networks:
                mac = network['bssid']
                ssid = network['ssid']
                auth = network['encryption']
                first_seen = network['timestamp']
                channel = network['channel']
                rssi = network['signal']

                # GPS data
                if network.get('gps'):
                    lat = network['gps']['latitude']
                    lon = network['gps']['longitude']
                    alt = network['gps']['altitude']
                    acc = network['gps'].get('hdop', 0) * 5  # Approximate
                else:
                    lat = lon = alt = acc = 0

                wifi_type = 'WIFI'

                f.write(f"{mac},{ssid},{auth},{first_seen},{channel},{rssi},{lat},{lon},{alt},{acc},{wifi_type}\n")

        return filepath

    def generate_html_map(self, filename: str):
        """
        Generate interactive HTML map.

        Args:
            filename: Output filename
        """
        filepath = os.path.join(self.output_dir, filename)

        # Calculate center
        lats = [n['gps']['latitude'] for n in self.networks if n.get('gps')]
        lons = [n['gps']['longitude'] for n in self.networks if n.get('gps')]

        if not lats:
            center_lat, center_lon = 0, 0
        else:
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Wardriving Map - CyberDeck Interface</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 100vh; }}
        .legend {{
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2);
        }}
        .legend-item {{
            margin: 5px 0;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            display: inline-block;
            margin-right: 5px;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([{center_lat}, {center_lon}], 13);

        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);

        var networks = {json.dumps(self.networks)};

        networks.forEach(function(network) {{
            if (!network.gps) return;

            var color;
            if (network.encryption === 'Open' || network.encryption === 'Unknown') {{
                color = 'green';
            }} else if (network.encryption === 'WPA3') {{
                color = 'purple';
            }} else if (network.encryption === 'WPA2') {{
                color = 'red';
            }} else {{
                color = 'orange';
            }}

            var marker = L.circleMarker(
                [network.gps.latitude, network.gps.longitude],
                {{
                    radius: 8,
                    fillColor: color,
                    color: '#000',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                }}
            );

            var popupContent = '<b>' + (network.ssid || '(Hidden)') + '</b><br>';
            popupContent += 'BSSID: ' + network.bssid + '<br>';
            popupContent += 'Channel: ' + network.channel + '<br>';
            popupContent += 'Signal: ' + network.signal + ' dBm<br>';
            popupContent += 'Encryption: ' + network.encryption;

            marker.bindPopup(popupContent);
            marker.addTo(map);
        }});

        // Legend
        var legend = L.control({{position: 'bottomright'}});

        legend.onAdd = function (map) {{
            var div = L.DomUtil.create('div', 'legend');

            div.innerHTML = '<h4>WiFi Security</h4>';
            div.innerHTML += '<div class="legend-item"><span class="legend-color" style="background:green"></span>Open</div>';
            div.innerHTML += '<div class="legend-item"><span class="legend-color" style="background:orange"></span>WEP/WPA</div>';
            div.innerHTML += '<div class="legend-item"><span class="legend-color" style="background:red"></span>WPA2</div>';
            div.innerHTML += '<div class="legend-item"><span class="legend-color" style="background:purple"></span>WPA3</div>';
            div.innerHTML += '<hr>';
            div.innerHTML += '<div>Total Networks: ' + networks.length + '</div>';

            return div;
        }};

        legend.addTo(map);
    </script>
</body>
</html>
"""

        with open(filepath, 'w') as f:
            f.write(html)

        return filepath

    def get_statistics(self) -> Dict:
        """Get wardriving statistics"""
        total = len(self.networks)

        if total == 0:
            return {
                'total': 0,
                'open': 0,
                'wpa': 0,
                'wpa2': 0,
                'wpa3': 0,
                '2.4ghz': 0,
                '5ghz': 0
            }

        open_count = sum(1 for n in self.networks if n['encryption'] in ['Open', 'Unknown'])
        wpa_count = sum(1 for n in self.networks if 'WPA' in n['encryption'] and 'WPA2' not in n['encryption'] and 'WPA3' not in n['encryption'])
        wpa2_count = sum(1 for n in self.networks if 'WPA2' in n['encryption'])
        wpa3_count = sum(1 for n in self.networks if 'WPA3' in n['encryption'])

        freq_2_4 = sum(1 for n in self.networks if n['frequency'] < 3.0)
        freq_5 = sum(1 for n in self.networks if n['frequency'] >= 5.0)

        return {
            'total': total,
            'open': open_count,
            'wpa': wpa_count,
            'wpa2': wpa2_count,
            'wpa3': wpa3_count,
            '2.4ghz': freq_2_4,
            '5ghz': freq_5
        }
