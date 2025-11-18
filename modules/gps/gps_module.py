"""
GPS Module for Wardriving and Geolocation
Integrates with WiFi module for GPS-tagged network mapping
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional
import time
import json
import os
from datetime import datetime

try:
    from .gps_parser import GPSReader
    GPS_AVAILABLE = True
except ImportError:
    GPS_AVAILABLE = False


class GPSModule(BaseModule):
    """
    GPS модуль для wardriving и геолокации.
    
    Функции:
    - Чтение GPS координат
    - GPS-tagged wardriving
    - Генерация карт с сетями
    - Экспорт в Wigle CSV
    - KML/GPX треки
    """
    
    def __init__(self):
        super().__init__(
            name="GPS & Wardriving",
            version="1.0.0",
            priority=5
        )
        
        self.gps: Optional[GPSReader] = None
        self.hardware_enabled = False
        self.current_location = None
        self.tracking_enabled = False
        
        # Wardriving data
        self.networks = []
        self.track_points = []
        self.maps_dir = "maps"
        
        os.makedirs(self.maps_dir, exist_ok=True)
    
    def on_load(self):
        """Инициализация модуля"""
        self.log_info("GPS module loading...")
        
        if not GPS_AVAILABLE:
            self.log_warning("GPS parser not available - running in demo mode")
            return
            
        # Load config
        config = self.get_config().get('hardware', {}).get('gps', {})
        
        if not config.get('enabled', False):
            self.log_info("GPS disabled in config")
            return
            
        try:
            port = config.get('uart_port', '/dev/ttyS1')
            baudrate = config.get('baudrate', 9600)
            
            self.gps = GPSReader(port=port, baudrate=baudrate)
            
            if self.gps.initialize():
                self.hardware_enabled = True
                self.log_info(f"GPS initialized on {port}")
            else:
                self.log_warning("GPS initialization failed")
                
        except Exception as e:
            self.log_error(f"Failed to initialize GPS: {e}")
    
    def on_unload(self):
        """Освобождение ресурсов"""
        if self.gps and self.hardware_enabled:
            try:
                self.gps.close()
            except Exception as e:
                self.log_error(f"Error closing GPS: {e}")
    
    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        return [
            ("Get Location", self.get_location),
            ("Start Wardriving", self.start_wardriving),
            ("View Networks", self.view_networks),
            ("Generate Map", self.generate_map),
            ("Export Wigle CSV", self.export_wigle),
            ("GPS Status", self.show_gps_status),
        ]
    
    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        hw_status = "HW" if self.hardware_enabled else "DEMO"
        if self.current_location:
            lat, lon = self.current_location
            return f"GPS[{hw_status}]: {lat:.4f},{lon:.4f}"
        return f"GPS[{hw_status}]: No fix"
    
    def get_hotkeys(self):
        """Горячие клавиши"""
        return {
            'g': self.get_location,
            'w': self.start_wardriving,
            'm': self.generate_map,
        }
    
    # ========== Функции модуля ==========
    
    def get_location(self):
        """Получить текущую локацию"""
        if self.hardware_enabled and self.gps:
            self.show_message("Getting GPS Fix", "Waiting for GPS fix...\nThis may take a minute.")
            
            try:
                location = self.gps.get_location()
                
                if location:
                    lat, lon = location
                    self.current_location = location
                    
                    self.show_message(
                        "GPS Location",
                        f"Location acquired!\n\n"
                        f"Latitude: {lat:.6f}\n"
                        f"Longitude: {lon:.6f}\n\n"
                        f"Altitude: {self.gps.last_fix.get('altitude', 0):.1f}m\n"
                        f"Satellites: {self.gps.last_fix.get('satellites', 0)}"
                    )
                else:
                    self.show_error("No GPS fix acquired.\nCheck antenna and wait longer.")
                    
            except Exception as e:
                self.show_error(f"GPS error: {e}")
        else:
            # Demo mode
            self.show_message(
                "GPS Location (DEMO)",
                "Demo Location:\n\n"
                "Latitude: 55.7558° N\n"
                "Longitude: 37.6173° E\n"
                "Altitude: 156m\n"
                "Satellites: 8\n\n"
                "(Running in DEMO mode)"
            )
    
    def start_wardriving(self):
        """Начать wardriving"""
        if not self.hardware_enabled:
            self.show_message(
                "Wardriving (DEMO)",
                "Wardriving requires GPS hardware.\n\n"
                "Enable GPS in config and connect antenna."
            )
            return
            
        self.show_message(
            "Wardriving",
            "Wardriving mode!\n\n"
            "This mode logs WiFi networks with GPS coordinates.\n\n"
            "Integration with WiFi module required.\n"
            "(Feature in development)"
        )
    
    def view_networks(self):
        """Просмотр найденных сетей"""
        if not self.networks:
            self.show_message(
                "Networks",
                "No networks logged yet.\n\n"
                "Run wardriving to collect networks."
            )
            return
            
        network_list = f"Found Networks: {len(self.networks)}\n\n"
        for net in self.networks[:20]:  # Show first 20
            network_list += f"{net['ssid']}\n"
            network_list += f"  MAC: {net['bssid']}\n"
            network_list += f"  Location: {net['lat']:.4f},{net['lon']:.4f}\n\n"
            
        self.show_message("Networks", network_list)
    
    def generate_map(self):
        """Генерация HTML карты"""
        if not self.networks:
            self.show_error("No networks to map.\nRun wardriving first.")
            return
            
        try:
            # Generate simple HTML map
            html = self._generate_html_map()
            
            filename = f"wardriving_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            filepath = os.path.join(self.maps_dir, filename)
            
            with open(filepath, 'w') as f:
                f.write(html)
                
            self.show_message(
                "Map Generated",
                f"Map saved to:\n{filepath}\n\n"
                f"Networks: {len(self.networks)}\n"
                f"Open in browser to view."
            )
            
        except Exception as e:
            self.show_error(f"Failed to generate map: {e}")
    
    def export_wigle(self):
        """Экспорт в Wigle CSV формат"""
        if not self.networks:
            self.show_error("No networks to export.")
            return
            
        try:
            filename = f"wigle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = os.path.join(self.maps_dir, filename)
            
            with open(filepath, 'w') as f:
                # Wigle CSV header
                f.write("MAC,SSID,AuthMode,FirstSeen,Channel,RSSI,Lat,Lon,AltitudeMeters,AccuracyMeters,Type\n")
                
                for net in self.networks:
                    f.write(f"{net['bssid']},{net['ssid']},{net.get('auth', 'WPA2')},"
                           f"{net.get('time', '')},"
                           f"{net.get('channel', 0)},{net.get('rssi', -100)},"
                           f"{net['lat']},{net['lon']},0,10,WIFI\n")
                    
            self.show_message(
                "Wigle Export",
                f"Exported to:\n{filepath}\n\n"
                f"Networks: {len(self.networks)}\n"
                f"Upload to wigle.net for global database."
            )
            
        except Exception as e:
            self.show_error(f"Export failed: {e}")
    
    def show_gps_status(self):
        """Показать статус GPS"""
        if self.hardware_enabled and self.gps:
            try:
                fix = self.gps.read(timeout=2.0)
                
                if fix:
                    status = (
                        "GPS Hardware Status\n\n"
                        f"Status: ENABLED\n"
                        f"Port: {self.gps.port}\n"
                        f"Baudrate: {self.gps.baudrate}\n\n"
                        f"Fix Quality: {fix.get('fix_quality', 0)}\n"
                        f"Satellites: {fix.get('satellites', 0)}\n"
                        f"Altitude: {fix.get('altitude', 0):.1f}m\n\n"
                        f"Latitude: {fix.get('latitude', 0):.6f}\n"
                        f"Longitude: {fix.get('longitude', 0):.6f}\n"
                    )
                else:
                    status = (
                        "GPS Hardware Status\n\n"
                        f"Status: NO FIX\n"
                        f"Port: {self.gps.port}\n\n"
                        "Waiting for satellites...\n"
                        "Check antenna connection."
                    )
            except Exception as e:
                status = f"GPS Error: {e}"
        else:
            status = (
                "GPS Hardware Status\n\n"
                "Status: DISABLED (Demo Mode)\n\n"
                "To enable:\n"
                "1. Connect GPS module to UART\n"
                "2. Set enabled=true in config/main.yaml\n"
                "3. Configure UART port\n"
            )
            
        self.show_message("GPS Status", status)
    
    # ========== Helper methods ==========
    
    def _generate_html_map(self) -> str:
        """Generate HTML map with networks"""
        # Simple Leaflet.js map
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Wardriving Map</title>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <style>
        #map { height: 100vh; }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([55.7558, 37.6173], 13);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);
        
        var networks = """ + json.dumps(self.networks) + """;
        
        networks.forEach(function(net) {
            var color = net.auth === 'Open' ? 'red' : 'blue';
            L.circleMarker([net.lat, net.lon], {
                radius: 5,
                color: color,
                fillOpacity: 0.5
            }).bindPopup(net.ssid + '<br>' + net.bssid).addTo(map);
        });
        
        if (networks.length > 0) {
            map.fitBounds(networks.map(n => [n.lat, n.lon]));
        }
    </script>
</body>
</html>
"""
        return html
