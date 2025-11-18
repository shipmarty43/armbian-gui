"""
GPS NMEA Parser
Parses NMEA sentences from GPS modules (UART/Serial)
"""

import time
import logging
import serial
from typing import Optional, Dict
from datetime import datetime


class NMEAParser:
    """Parse NMEA GPS sentences"""
    
    def __init__(self):
        self.logger = logging.getLogger("cyberdeck.gps.parser")
        
    def parse_nmea(self, sentence: str) -> Optional[Dict]:
        """
        Parse NMEA sentence.
        
        Args:
            sentence: NMEA sentence string
            
        Returns:
            dict: Parsed data or None
        """
        try:
            if not sentence.startswith('$'):
                return None
                
            # Remove checksum
            if '*' in sentence:
                sentence = sentence.split('*')[0]
                
            parts = sentence.split(',')
            sentence_type = parts[0][3:]  # Remove $GP prefix
            
            if sentence_type == 'GGA':
                return self._parse_gga(parts)
            elif sentence_type == 'RMC':
                return self._parse_rmc(parts)
            elif sentence_type == 'GSA':
                return self._parse_gsa(parts)
            elif sentence_type == 'GSV':
                return self._parse_gsv(parts)
                
            return None
            
        except Exception as e:
            self.logger.debug(f"Parse error: {e}")
            return None
    
    def _parse_gga(self, parts: list) -> Dict:
        """Parse GGA sentence (Global Positioning System Fix Data)"""
        data = {'type': 'GGA'}
        
        try:
            # Time
            if parts[1]:
                data['time'] = parts[1]
                
            # Latitude
            if parts[2] and parts[3]:
                lat = float(parts[2][:2]) + float(parts[2][2:]) / 60.0
                if parts[3] == 'S':
                    lat = -lat
                data['latitude'] = lat
                
            # Longitude
            if parts[4] and parts[5]:
                lon = float(parts[4][:3]) + float(parts[4][3:]) / 60.0
                if parts[5] == 'W':
                    lon = -lon
                data['longitude'] = lon
                
            # Fix quality
            if parts[6]:
                data['fix_quality'] = int(parts[6])
                
            # Satellites
            if parts[7]:
                data['satellites'] = int(parts[7])
                
            # Altitude
            if parts[9]:
                data['altitude'] = float(parts[9])
                
            return data
            
        except Exception as e:
            self.logger.debug(f"GGA parse error: {e}")
            return data
    
    def _parse_rmc(self, parts: list) -> Dict:
        """Parse RMC sentence (Recommended Minimum)"""
        data = {'type': 'RMC'}
        
        try:
            # Time
            if parts[1]:
                data['time'] = parts[1]
                
            # Status
            if parts[2]:
                data['status'] = parts[2]  # A=active, V=void
                
            # Latitude
            if parts[3] and parts[4]:
                lat = float(parts[3][:2]) + float(parts[3][2:]) / 60.0
                if parts[4] == 'S':
                    lat = -lat
                data['latitude'] = lat
                
            # Longitude
            if parts[5] and parts[6]:
                lon = float(parts[5][:3]) + float(parts[5][3:]) / 60.0
                if parts[6] == 'W':
                    lon = -lon
                data['longitude'] = lon
                
            # Speed (knots)
            if parts[7]:
                data['speed_knots'] = float(parts[7])
                data['speed_kmh'] = float(parts[7]) * 1.852
                
            # Course
            if parts[8]:
                data['course'] = float(parts[8])
                
            # Date
            if parts[9]:
                data['date'] = parts[9]
                
            return data
            
        except Exception as e:
            self.logger.debug(f"RMC parse error: {e}")
            return data
    
    def _parse_gsa(self, parts: list) -> Dict:
        """Parse GSA sentence (GPS DOP and active satellites)"""
        return {'type': 'GSA'}
    
    def _parse_gsv(self, parts: list) -> Dict:
        """Parse GSV sentence (Satellites in view)"""
        return {'type': 'GSV'}


class GPSReader:
    """
    GPS UART/Serial reader.
    
    Reads NMEA sentences from GPS module via serial port.
    """
    
    def __init__(self, port: str = '/dev/ttyS1', baudrate: int = 9600):
        """
        Initialize GPS reader.
        
        Args:
            port: Serial port (e.g., /dev/ttyS1, /dev/ttyAMA0)
            baudrate: Baud rate (default: 9600)
        """
        self.logger = logging.getLogger("cyberdeck.gps.reader")
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.parser = NMEAParser()
        
        self.last_fix = None
        self.enabled = False
        
    def initialize(self) -> bool:
        """
        Initialize GPS serial connection.
        
        Returns:
            bool: True if successful
        """
        try:
            self.serial = serial.Serial(
                self.port,
                self.baudrate,
                timeout=1
            )
            
            self.enabled = True
            self.logger.info(f"GPS initialized on {self.port} @ {self.baudrate}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize GPS: {e}")
            return False
    
    def read(self, timeout: float = 5.0) -> Optional[Dict]:
        """
        Read GPS fix.
        
        Args:
            timeout: Read timeout in seconds
            
        Returns:
            dict: GPS data or None
        """
        if not self.serial:
            return None
            
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                line = self.serial.readline().decode('ascii', errors='ignore').strip()
                
                if line:
                    data = self.parser.parse_nmea(line)
                    if data and data.get('type') == 'GGA':
                        # Got a fix
                        if data.get('fix_quality', 0) > 0:
                            self.last_fix = data
                            return data
                            
            except Exception as e:
                self.logger.debug(f"Read error: {e}")
                
            time.sleep(0.1)
        
        return None
    
    def get_location(self) -> Optional[Tuple[float, float]]:
        """
        Get current location.
        
        Returns:
            Tuple: (latitude, longitude) or None
        """
        fix = self.read(timeout=2.0)
        if fix and 'latitude' in fix and 'longitude' in fix:
            return (fix['latitude'], fix['longitude'])
        return None
    
    def close(self):
        """Close serial connection"""
        if self.serial:
            self.serial.close()
            self.enabled = False
            self.logger.info("GPS closed")
