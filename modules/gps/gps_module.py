"""
GPS Module - геолокация, tracking, wardriving support
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional, Dict
import time
import serial
import re
import os
from datetime import datetime
import json


class GPSModule(BaseModule):
    """
    GPS модуль для геолокации и tracking.

    Функции:
    - Real-time позиция
    - Track recording (GPX export)
    - Waypoint marking
    - Интеграция с wardriving
    """

    def __init__(self):
        super().__init__(
            name="GPS Tracker",
            version="1.0.0",
            priority=5
        )

        self.serial_port = None
        self.device = "/dev/ttyS1"
        self.baudrate = 9600

        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.speed = 0.0
        self.heading = 0.0
        self.satellites = 0
        self.fix_quality = 0
        self.hdop = 0.0

        self.tracking = False
        self.track_points = []
        self.waypoints = []

        self.tracks_dir = "tracks"
        os.makedirs(self.tracks_dir, exist_ok=True)

    def on_load(self):
        """Инициализация модуля"""
        self.log_info("GPS module loading...")

        # Load configuration
        config = self.load_config("config/main.yaml")
        gps_config = config.get('hardware', {}).get('gps', {})

        if not gps_config.get('enabled', False):
            self.log_info("GPS disabled in config")
            self.enabled = False
            return

        self.device = gps_config.get('device', '/dev/ttyS1')
        self.baudrate = gps_config.get('baudrate', 9600)

        try:
            self.serial_port = serial.Serial(
                self.device,
                self.baudrate,
                timeout=1
            )

            self.log_info(f"GPS initialized on {self.device}")
            self.enabled = True

            # Start position update in background
            import threading
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()

        except Exception as e:
            self.log_error(f"Failed to open GPS device: {e}")
            self.enabled = False

    def on_unload(self):
        """Освобождение ресурсов"""
        if self.serial_port:
            self.serial_port.close()
        self.log_info("GPS module unloaded")

    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        if not self.enabled:
            return [
                ("Status: GPS Not Available", lambda: None),
            ]

        return [
            ("Current Position", self.show_position),
            ("Track Recording", self.track_menu),
            ("Waypoints", self.waypoint_menu),
            ("Export GPX", self.export_gpx),
            ("Settings", self.show_settings),
        ]

    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        if not self.enabled:
            return "GPS: Disabled"

        if self.satellites == 0:
            return "GPS: No Fix"

        fix_type = "3D" if self.satellites >= 4 else "2D"
        return f"GPS: {self.satellites} sats, {fix_type} fix"

    # ========== GPS Functions ==========

    def _update_loop(self):
        """Background loop for GPS updates"""
        while self.enabled:
            try:
                if self.serial_port and self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('ascii', errors='ignore')
                    self._parse_nmea(line)

                time.sleep(0.1)

            except Exception as e:
                self.log_error(f"GPS update error: {e}")
                time.sleep(1)

    def _parse_nmea(self, line: str):
        """Parse NMEA sentence"""
        line = line.strip()

        if not line.startswith('$'):
            return

        # GGA - Fix data
        if 'GPGGA' in line or 'GNGGA' in line:
            self._parse_gga(line)

        # RMC - Recommended minimum
        elif 'GPRMC' in line or 'GNRMC' in line:
            self._parse_rmc(line)

        # GSA - Satellites in use
        elif 'GPGSA' in line or 'GNGSA' in line:
            self._parse_gsa(line)

    def _parse_gga(self, line: str):
        """Parse GGA sentence (fix data)"""
        parts = line.split(',')

        if len(parts) < 15:
            return

        try:
            # Fix quality
            self.fix_quality = int(parts[6]) if parts[6] else 0

            if self.fix_quality == 0:
                return

            # Latitude
            lat_str = parts[2]
            lat_dir = parts[3]
            if lat_str:
                lat_deg = int(lat_str[:2])
                lat_min = float(lat_str[2:])
                self.latitude = lat_deg + lat_min / 60.0
                if lat_dir == 'S':
                    self.latitude = -self.latitude

            # Longitude
            lon_str = parts[4]
            lon_dir = parts[5]
            if lon_str:
                lon_deg = int(lon_str[:3])
                lon_min = float(lon_str[3:])
                self.longitude = lon_deg + lon_min / 60.0
                if lon_dir == 'W':
                    self.longitude = -self.longitude

            # Satellites
            self.satellites = int(parts[7]) if parts[7] else 0

            # HDOP
            self.hdop = float(parts[8]) if parts[8] else 0.0

            # Altitude
            self.altitude = float(parts[9]) if parts[9] else 0.0

            # Add to track if recording
            if self.tracking:
                self._add_track_point()

            # Emit event
            self.emit_event("gps.position_update", {
                'latitude': self.latitude,
                'longitude': self.longitude,
                'altitude': self.altitude,
                'satellites': self.satellites
            })

        except (ValueError, IndexError) as e:
            self.log_debug(f"GGA parse error: {e}")

    def _parse_rmc(self, line: str):
        """Parse RMC sentence (speed, heading)"""
        parts = line.split(',')

        if len(parts) < 12:
            return

        try:
            # Speed (knots to km/h)
            if parts[7]:
                self.speed = float(parts[7]) * 1.852

            # Heading
            if parts[8]:
                self.heading = float(parts[8])

        except (ValueError, IndexError):
            pass

    def _parse_gsa(self, line: str):
        """Parse GSA sentence (HDOP, satellites)"""
        # Already handled in GGA
        pass

    def get_position(self) -> Optional[Dict]:
        """
        Get current GPS position.

        Returns:
            Dict with position data or None
        """
        if self.satellites == 0:
            return None

        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed,
            'heading': self.heading,
            'satellites': self.satellites,
            'fix_quality': self.fix_quality,
            'hdop': self.hdop
        }

    def _add_track_point(self):
        """Add current position to track"""
        point = {
            'lat': self.latitude,
            'lon': self.longitude,
            'alt': self.altitude,
            'time': datetime.now().isoformat()
        }

        self.track_points.append(point)

    # ========== UI Functions ==========

    def show_position(self):
        """Show current position"""
        pos_text = "GPS Position\n\n"

        if self.satellites == 0:
            pos_text += "No GPS fix\n\n"
            pos_text += "Waiting for satellites..."
        else:
            fix_type = "3D" if self.satellites >= 4 else "2D"

            pos_text += f"Latitude:  {self.latitude:.6f}° "
            pos_text += "N\n" if self.latitude >= 0 else "S\n"

            pos_text += f"Longitude: {self.longitude:.6f}° "
            pos_text += "E\n" if self.longitude >= 0 else "W\n"

            pos_text += f"Altitude:  {self.altitude:.1f} m\n"
            pos_text += f"Speed:     {self.speed:.1f} km/h\n"
            pos_text += f"Heading:   {self.heading:.0f}°\n\n"

            pos_text += f"Satellites: {self.satellites} ({fix_type} fix)\n"
            pos_text += f"HDOP:       {self.hdop:.1f}\n"
            pos_text += f"Quality:    {['Invalid', 'GPS', 'DGPS'][min(self.fix_quality, 2)]}\n"

        self.show_message("GPS Position", pos_text)

    def track_menu(self):
        """Track recording menu"""
        if self.tracking:
            choice = self.show_menu(
                "Track Recording",
                [
                    f"Stop Recording ({len(self.track_points)} points)",
                    "Cancel"
                ]
            )

            if choice == 0:
                self._stop_tracking()
        else:
            choice = self.show_menu(
                "Track Recording",
                [
                    "Start Recording",
                    "Cancel"
                ]
            )

            if choice == 0:
                self._start_tracking()

    def _start_tracking(self):
        """Start track recording"""
        if self.satellites == 0:
            self.show_error("No GPS fix. Cannot start tracking.")
            return

        self.tracking = True
        self.track_points = []

        self.show_message(
            "Tracking Started",
            "GPS track recording started.\n\n"
            "Use 'Stop Recording' to save track."
        )

        self.log_info("GPS tracking started")

    def _stop_tracking(self):
        """Stop track recording"""
        self.tracking = False

        if len(self.track_points) < 2:
            self.show_message(
                "Tracking Stopped",
                "Track too short to save.\n"
                f"Points: {len(self.track_points)}"
            )
            return

        # Calculate statistics
        total_distance = 0.0
        for i in range(1, len(self.track_points)):
            p1 = self.track_points[i-1]
            p2 = self.track_points[i]

            # Simple distance calculation (Haversine would be better)
            dlat = p2['lat'] - p1['lat']
            dlon = p2['lon'] - p1['lon']
            dist = ((dlat**2 + dlon**2) ** 0.5) * 111.0  # Approx km

            total_distance += dist

        stats_text = f"Track Recording Stopped\n\n"
        stats_text += f"Points: {len(self.track_points)}\n"
        stats_text += f"Distance: {total_distance:.2f} km\n\n"
        stats_text += "Track saved automatically."

        self.show_message("Tracking Stopped", stats_text)
        self.log_info(f"GPS tracking stopped: {len(self.track_points)} points, {total_distance:.2f} km")

    def waypoint_menu(self):
        """Waypoint menu"""
        choice = self.show_menu(
            "Waypoints",
            [
                "Add Current Position",
                "View Waypoints",
                "Cancel"
            ]
        )

        if choice == 0:
            self._add_waypoint()
        elif choice == 1:
            self._view_waypoints()

    def _add_waypoint(self):
        """Add waypoint at current position"""
        if self.satellites == 0:
            self.show_error("No GPS fix. Cannot add waypoint.")
            return

        name = self.get_user_input(
            "Waypoint name:",
            default=f"WPT_{len(self.waypoints)+1}"
        )

        waypoint = {
            'name': name,
            'lat': self.latitude,
            'lon': self.longitude,
            'alt': self.altitude,
            'time': datetime.now().isoformat()
        }

        self.waypoints.append(waypoint)

        self.show_message(
            "Waypoint Added",
            f"Name: {name}\n"
            f"Position: {self.latitude:.6f}, {self.longitude:.6f}"
        )

        self.log_info(f"Waypoint added: {name}")

    def _view_waypoints(self):
        """View saved waypoints"""
        if not self.waypoints:
            self.show_message("Waypoints", "No waypoints saved.")
            return

        wpt_text = "Saved Waypoints\n\n"

        for i, wpt in enumerate(self.waypoints, 1):
            wpt_text += f"{i}. {wpt['name']}\n"
            wpt_text += f"   {wpt['lat']:.6f}, {wpt['lon']:.6f}\n"
            wpt_text += f"   Alt: {wpt['alt']:.1f} m\n\n"

        self.show_message("Waypoints", wpt_text)

    def export_gpx(self):
        """Export track and waypoints to GPX"""
        if not self.track_points and not self.waypoints:
            self.show_message(
                "Export GPX",
                "No track or waypoints to export."
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"track_{timestamp}.gpx"
        filepath = os.path.join(self.tracks_dir, filename)

        # Generate GPX
        gpx = self._generate_gpx()

        with open(filepath, 'w') as f:
            f.write(gpx)

        self.show_message(
            "Export Complete",
            f"Track exported to:\n{filepath}\n\n"
            f"Track points: {len(self.track_points)}\n"
            f"Waypoints: {len(self.waypoints)}"
        )

        self.log_info(f"GPX exported: {filepath}")

    def _generate_gpx(self) -> str:
        """Generate GPX XML"""
        gpx = '<?xml version="1.0"?>\n'
        gpx += '<gpx version="1.1" creator="CyberDeck Interface">\n'

        # Waypoints
        for wpt in self.waypoints:
            gpx += f'  <wpt lat="{wpt["lat"]}" lon="{wpt["lon"]}">\n'
            gpx += f'    <ele>{wpt["alt"]}</ele>\n'
            gpx += f'    <name>{wpt["name"]}</name>\n'
            gpx += f'  </wpt>\n'

        # Track
        if self.track_points:
            gpx += '  <trk>\n'
            gpx += '    <name>CyberDeck Track</name>\n'
            gpx += '    <trkseg>\n'

            for pt in self.track_points:
                gpx += f'      <trkpt lat="{pt["lat"]}" lon="{pt["lon"]}">\n'
                gpx += f'        <ele>{pt["alt"]}</ele>\n'
                gpx += f'        <time>{pt["time"]}</time>\n'
                gpx += '      </trkpt>\n'

            gpx += '    </trkseg>\n'
            gpx += '  </trk>\n'

        gpx += '</gpx>\n'

        return gpx

    def show_settings(self):
        """Настройки модуля"""
        settings_text = "GPS Module Settings\n\n"

        if self.enabled:
            settings_text += f"Device: {self.device}\n"
            settings_text += f"Baudrate: {self.baudrate}\n"
            settings_text += f"Protocol: NMEA\n\n"

            settings_text += f"Satellites: {self.satellites}\n"
            settings_text += f"Fix Quality: {self.fix_quality}\n"
            settings_text += f"HDOP: {self.hdop}\n\n"

            settings_text += f"Track Points: {len(self.track_points)}\n"
            settings_text += f"Waypoints: {len(self.waypoints)}\n"
            settings_text += f"Tracking: {'Active' if self.tracking else 'Inactive'}"
        else:
            settings_text += "Status: Not available\n\n"
            settings_text += f"Device: {self.device}\n"
            settings_text += "Check connection and configuration"

        self.show_message("Settings", settings_text)
