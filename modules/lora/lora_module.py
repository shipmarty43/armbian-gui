"""
LoRa Mesh Networking Module
Integrations: Meshtastic and Reticulum
Hardware: Waveshare SX1262 LoRa HAT on Orange Pi
"""

from core.base_module import BaseModule
from typing import List, Tuple, Callable, Optional
import time
import json
import os

try:
    from .sx1262_driver import SX1262
    SX1262_AVAILABLE = True
except ImportError:
    SX1262_AVAILABLE = False

try:
    import meshtastic
    from meshtastic.serial_interface import SerialInterface
    MESHTASTIC_AVAILABLE = True
except ImportError:
    MESHTASTIC_AVAILABLE = False

try:
    import RNS
    RETICULUM_AVAILABLE = True
except ImportError:
    RETICULUM_AVAILABLE = False


class LoRaModule(BaseModule):
    """
    LoRa Mesh Networking модуль.
    
    Функции:
    - Meshtastic mesh networking
    - Reticulum cryptographic networking
    - Point-to-point LoRa communication
    - Mesh message routing
    - Long-range messaging
    """
    
    def __init__(self):
        super().__init__(
            name="LoRa Mesh",
            version="1.0.0",
            priority=7
        )
        
        self.sx1262 = None
        self.meshtastic_interface = None
        self.reticulum = None
        
        self.mode = "direct"  # direct, meshtastic, reticulum
        self.hardware_enabled = False
        
        # Message storage
        self.messages = []
        self.nodes = []
        
        self.logs_dir = "lora_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def on_load(self):
        """Инициализация модуля"""
        self.log_info("LoRa Mesh module loading...")
        
        # Load config
        config = self.get_config().get('lora', {})
        
        if not config.get('enabled', False):
            self.log_info("LoRa disabled in config")
            return
            
        # Try to initialize SX1262 hardware
        if SX1262_AVAILABLE:
            try:
                spi_bus = config.get('spi_bus', 0)
                spi_device = config.get('spi_device', 0)
                reset_pin = config.get('reset_pin', 18)
                busy_pin = config.get('busy_pin', 24)
                dio1_pin = config.get('dio1_pin', 23)
                
                self.sx1262 = SX1262(
                    spi_bus=spi_bus,
                    spi_device=spi_device,
                    reset_pin=reset_pin,
                    busy_pin=busy_pin,
                    dio1_pin=dio1_pin
                )
                
                if self.sx1262.initialize():
                    self.hardware_enabled = True
                    self.log_info("SX1262 LoRa hardware initialized")
                else:
                    self.log_warning("SX1262 initialization failed")
                    
            except Exception as e:
                self.log_error(f"Failed to initialize SX1262: {e}")
        
        # Try to initialize Meshtastic
        if MESHTASTIC_AVAILABLE:
            try:
                # Meshtastic via serial (if device connected)
                port = config.get('meshtastic_port', None)
                if port:
                    self.meshtastic_interface = SerialInterface(port)
                    self.log_info(f"Meshtastic initialized on {port}")
            except Exception as e:
                self.log_warning(f"Meshtastic not available: {e}")
        
        # Try to initialize Reticulum
        if RETICULUM_AVAILABLE:
            try:
                # Initialize Reticulum
                RNS.loglevel = RNS.LOG_ERROR
                self.reticulum = RNS.Reticulum()
                self.log_info("Reticulum initialized")
            except Exception as e:
                self.log_warning(f"Reticulum not available: {e}")
    
    def on_unload(self):
        """Освобождение ресурсов"""
        if self.sx1262:
            try:
                self.sx1262.close()
            except Exception as e:
                self.log_error(f"Error closing SX1262: {e}")
                
        if self.meshtastic_interface:
            try:
                self.meshtastic_interface.close()
            except:
                pass
    
    def get_menu_items(self) -> List[Tuple[str, Callable]]:
        """Пункты меню модуля"""
        return [
            ("Send Message", self.send_message),
            ("Receive Messages", self.receive_messages),
            ("Mesh Nodes", self.view_nodes),
            ("Select Mode", self.select_mode),
            ("Meshtastic Chat", self.meshtastic_chat),
            ("Reticulum Network", self.reticulum_network),
            ("LoRa Status", self.show_status),
        ]
    
    def get_status_widget(self) -> str:
        """Статус для статус-панели"""
        hw_status = "HW" if self.hardware_enabled else "DEMO"
        return f"LoRa[{hw_status}]: {self.mode.upper()} | {len(self.nodes)} nodes"
    
    def get_hotkeys(self):
        """Горячие клавиши"""
        return {
            's': self.send_message,
            'r': self.receive_messages,
            'n': self.view_nodes,
        }
    
    # ========== Функции модуля ==========
    
    def send_message(self):
        """Отправить сообщение"""
        if not self.hardware_enabled:
            self.show_message(
                "Send Message (DEMO)",
                "LoRa messaging requires hardware.\n\n"
                "Connect Waveshare SX1262 LoRa HAT."
            )
            return
            
        message = self.get_user_input("Message:", default="Hello LoRa!")
        
        if not message:
            return
            
        try:
            if self.mode == "direct":
                # Direct LoRa transmission
                self.sx1262.transmit(message.encode())
                self.show_message(
                    "Message Sent",
                    f"Transmitted via LoRa:\n{message}\n\n"
                    f"Frequency: {self.sx1262.frequency/1e6}MHz\n"
                    f"Power: {self.sx1262.tx_power}dBm"
                )
                
            elif self.mode == "meshtastic" and self.meshtastic_interface:
                # Meshtastic mesh
                self.meshtastic_interface.sendText(message)
                self.show_message(
                    "Message Sent",
                    f"Sent via Meshtastic mesh:\n{message}"
                )
                
            elif self.mode == "reticulum" and self.reticulum:
                # Reticulum network
                self.show_message(
                    "Reticulum Send",
                    "Sending via Reticulum...\n"
                    "(Implementation in progress)"
                )
            else:
                self.show_error("Mode not available")
                
        except Exception as e:
            self.show_error(f"Send error: {e}")
    
    def receive_messages(self):
        """Принять сообщения"""
        if not self.hardware_enabled:
            self.show_message(
                "Receive (DEMO)",
                "No messages.\n\n"
                "Connect hardware to receive LoRa messages."
            )
            return
            
        try:
            if self.mode == "direct":
                # Direct LoRa receive
                self.show_message("Receiving", "Listening for LoRa messages...\nTimeout: 10s")
                
                data = self.sx1262.receive(timeout=10.0)
                
                if data:
                    try:
                        message = data.decode('utf-8', errors='ignore')
                        rssi = self.sx1262.get_rssi()
                        
                        self.messages.append({
                            'message': message,
                            'rssi': rssi,
                            'time': time.time()
                        })
                        
                        self.show_message(
                            "Message Received",
                            f"Received:\n{message}\n\n"
                            f"RSSI: {rssi}dBm"
                        )
                    except:
                        self.show_message("Received", f"Raw data: {data.hex()}")
                else:
                    self.show_message("Receive", "No messages received")
                    
            elif self.mode == "meshtastic" and self.meshtastic_interface:
                # Check Meshtastic messages
                self.show_message(
                    "Meshtastic Receive",
                    "Checking Meshtastic mesh...\n"
                    "(Implementation in progress)"
                )
                
        except Exception as e:
            self.show_error(f"Receive error: {e}")
    
    def view_nodes(self):
        """Просмотр mesh узлов"""
        if self.mode == "meshtastic" and self.meshtastic_interface:
            try:
                # Get Meshtastic nodes
                nodes_text = "Meshtastic Mesh Nodes:\n\n"
                
                # This would list nodes from Meshtastic
                nodes_text += "(Node discovery in progress)\n"
                nodes_text += "Check Meshtastic app for full node list."
                
                self.show_message("Mesh Nodes", nodes_text)
            except Exception as e:
                self.show_error(f"Error getting nodes: {e}")
        else:
            self.show_message(
                "Mesh Nodes",
                f"Direct LoRa mode - no mesh.\n\n"
                f"Switch to Meshtastic or Reticulum\n"
                f"for mesh networking."
            )
    
    def select_mode(self):
        """Выбрать режим работы"""
        modes = []
        
        modes.append("Direct LoRa (Point-to-Point)")
        
        if MESHTASTIC_AVAILABLE:
            modes.append("Meshtastic Mesh")
            
        if RETICULUM_AVAILABLE:
            modes.append("Reticulum Network")
        
        idx = self.show_menu("Select LoRa Mode", modes)
        
        if idx == 0:
            self.mode = "direct"
            self.show_message("Mode", "Mode: Direct LoRa")
        elif idx == 1 and MESHTASTIC_AVAILABLE:
            self.mode = "meshtastic"
            self.show_message("Mode", "Mode: Meshtastic Mesh")
        elif idx == 2 and RETICULUM_AVAILABLE:
            self.mode = "reticulum"
            self.show_message("Mode", "Mode: Reticulum Network")
    
    def meshtastic_chat(self):
        """Meshtastic chat interface"""
        if not MESHTASTIC_AVAILABLE:
            self.show_message(
                "Meshtastic",
                "Meshtastic not installed.\n\n"
                "Install: pip install meshtastic"
            )
            return
            
        if not self.meshtastic_interface:
            self.show_message(
                "Meshtastic",
                "Meshtastic device not connected.\n\n"
                "Connect Meshtastic device via USB\n"
                "or configure in config/main.yaml"
            )
            return
            
        self.show_message(
            "Meshtastic Chat",
            "Meshtastic Mesh Chat\n\n"
            "Features:\n"
            "- Long-range mesh messaging\n"
            "- Automatic routing\n"
            "- Encrypted channels\n"
            "- Position sharing\n\n"
            "Use Meshtastic app for full features."
        )
    
    def reticulum_network(self):
        """Reticulum network interface"""
        if not RETICULUM_AVAILABLE:
            self.show_message(
                "Reticulum",
                "Reticulum not installed.\n\n"
                "Install: pip install rns"
            )
            return
            
        if not self.reticulum:
            self.show_message(
                "Reticulum",
                "Reticulum not initialized.\n\n"
                "Check configuration."
            )
            return
            
        self.show_message(
            "Reticulum Network",
            "Reticulum Cryptographic Network\n\n"
            "Features:\n"
            "- End-to-end encryption\n"
            "- Decentralized routing\n"
            "- Works over any medium (LoRa, WiFi, etc)\n"
            "- Anonymous addressing\n\n"
            f"Network interfaces: {len(self.reticulum.interfaces)}\n"
            f"Status: {'Active' if self.reticulum else 'Inactive'}"
        )
    
    def show_status(self):
        """LoRa status"""
        if self.hardware_enabled and self.sx1262:
            status = (
                "LoRa Hardware Status\n\n"
                f"Device: Waveshare SX1262 LoRa HAT\n"
                f"Status: ENABLED\n\n"
                f"Frequency: {self.sx1262.frequency/1e6}MHz\n"
                f"TX Power: {self.sx1262.tx_power}dBm\n"
                f"Spreading Factor: {self.sx1262.spreading_factor}\n"
                f"Bandwidth: {self.sx1262.bandwidth/1000}kHz\n\n"
                f"Mode: {self.mode.upper()}\n"
                f"Messages: {len(self.messages)}\n\n"
                f"Meshtastic: {'Available' if MESHTASTIC_AVAILABLE else 'Not installed'}\n"
                f"Reticulum: {'Available' if RETICULUM_AVAILABLE else 'Not installed'}\n"
            )
        else:
            status = (
                "LoRa Hardware Status\n\n"
                "Status: DISABLED (Demo Mode)\n\n"
                "To enable:\n"
                "1. Connect Waveshare SX1262 LoRa HAT\n"
                "2. Set enabled=true in config/main.yaml\n"
                "3. Configure GPIO pins for Orange Pi\n\n"
                "Optional integrations:\n"
                "- Meshtastic: pip install meshtastic\n"
                "- Reticulum: pip install rns\n"
            )
            
        self.show_message("LoRa Status", status)
