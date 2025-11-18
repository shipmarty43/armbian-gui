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
    from .meshtastic_protocol import MeshtasticProtocol, get_meshtastic_lora_config
    MESHTASTIC_PROTOCOL_AVAILABLE = True
except ImportError:
    MESHTASTIC_PROTOCOL_AVAILABLE = False

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
        self.meshtastic = None  # Meshtastic protocol handler
        self.reticulum = None

        self.mode = "direct"  # direct, meshtastic, reticulum
        self.hardware_enabled = False

        # Message storage
        self.messages = []
        self.nodes = []

        # Mesh monitoring
        self.mesh_monitoring = False
        self.mesh_thread = None
        
        self.logs_dir = "lora_logs"
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def on_load(self):
        """Инициализация модуля"""
        self.log_info("LoRa Mesh module loading...")

        # Load config
        main_config = self.load_config("config/main.yaml")
        config = main_config.get('hardware', {}).get('lora', {})

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

                    # Initialize Meshtastic protocol on this hardware
                    if MESHTASTIC_PROTOCOL_AVAILABLE:
                        try:
                            node_id = config.get('node_id', None)
                            self.meshtastic = MeshtasticProtocol(node_id=node_id)

                            # Configure LoRa for Meshtastic
                            mesh_config = get_meshtastic_lora_config()
                            self.sx1262.set_frequency(mesh_config['frequency'])
                            self.sx1262.spreading_factor = mesh_config['spreading_factor']
                            self.sx1262.bandwidth = mesh_config['bandwidth']
                            self.sx1262.tx_power = mesh_config['tx_power']

                            self.log_info(f"Meshtastic protocol initialized on hardware")
                            self.log_info(f"Node ID: 0x{self.meshtastic.node_id:08X}")
                        except Exception as e:
                            self.log_error(f"Failed to initialize Meshtastic protocol: {e}")
                else:
                    self.log_warning("SX1262 initialization failed")

            except Exception as e:
                self.log_error(f"Failed to initialize SX1262: {e}")
        
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
        # Stop mesh monitoring
        self.mesh_monitoring = False
        if self.mesh_thread:
            self.mesh_thread.join(timeout=2.0)

        if self.sx1262:
            try:
                self.sx1262.close()
            except Exception as e:
                self.log_error(f"Error closing SX1262: {e}")
    
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

            elif self.mode == "meshtastic" and self.meshtastic:
                # Meshtastic mesh on hardware
                packet = self.meshtastic.send_text(message)
                encoded = self.meshtastic.encode_packet(packet)
                self.sx1262.transmit(encoded)

                self.show_message(
                    "Message Sent",
                    f"Sent via Meshtastic mesh:\n{message}\n\n"
                    f"From: 0x{self.meshtastic.node_id:08X}\n"
                    f"To: Broadcast\n"
                    f"Packet ID: 0x{packet.id:08X}\n"
                    f"Hops: {packet.hop_limit}"
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

            elif self.mode == "meshtastic" and self.meshtastic:
                # Meshtastic mesh receive
                self.show_message("Receiving", "Listening for Meshtastic packets...\nTimeout: 30s")

                data = self.sx1262.receive(timeout=30.0)

                if data:
                    packet = self.meshtastic.decode_packet(data)

                    if packet:
                        # Process packet
                        message_text = self.meshtastic.process_received_packet(packet)
                        rssi = self.sx1262.get_rssi()

                        result = f"Meshtastic Packet Received\n\n"
                        result += f"From: 0x{packet.from_node:08X}\n"
                        result += f"To: {'Broadcast' if packet.to == self.meshtastic.BROADCAST_ADDR else f'0x{packet.to:08X}'}\n"
                        result += f"RSSI: {rssi}dBm\n"
                        result += f"Hops: {packet.hop_limit}\n\n"

                        if message_text:
                            result += f"Message:\n{message_text}"

                            self.messages.append({
                                'message': message_text,
                                'from': packet.from_node,
                                'rssi': rssi,
                                'time': time.time()
                            })
                        else:
                            result += f"Type: Port {packet.port_num}"

                        # Check if should rebroadcast
                        if self.meshtastic.should_rebroadcast(packet):
                            result += f"\n\n[Rebroadcasting...]"
                            rebroadcast = self.meshtastic.rebroadcast_packet(packet)
                            encoded = self.meshtastic.encode_packet(rebroadcast)

                            # Random delay for mesh protocol
                            delay = random.randint(*self.meshtastic.REBROADCAST_DELAY_MS) / 1000.0
                            time.sleep(delay)
                            self.sx1262.transmit(encoded)

                        self.show_message("Meshtastic Received", result)
                    else:
                        self.show_message("Receive", "Invalid Meshtastic packet")
                else:
                    self.show_message("Receive", "No packets received")
                
        except Exception as e:
            self.show_error(f"Receive error: {e}")
    
    def view_nodes(self):
        """Просмотр mesh узлов"""
        if self.mode == "meshtastic" and self.meshtastic:
            try:
                # Get Meshtastic nodes
                nodes = self.meshtastic.get_mesh_nodes()

                nodes_text = f"Meshtastic Mesh Nodes: {len(nodes)}\n\n"
                nodes_text += f"My Node ID: 0x{self.meshtastic.node_id:08X}\n\n"

                if nodes:
                    for node in nodes:
                        nodes_text += f"Node: 0x{node['id']:08X}\n"
                        nodes_text += f"  RSSI: {node['rssi']}dBm\n"
                        nodes_text += f"  SNR: {node['snr']:.1f}dB\n"
                        nodes_text += f"  Last seen: {int(time.time() - node['last_seen'])}s ago\n\n"
                else:
                    nodes_text += "No nodes discovered yet.\n"
                    nodes_text += "Send messages to discover nodes."

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

        if MESHTASTIC_PROTOCOL_AVAILABLE and self.meshtastic:
            modes.append("Meshtastic Mesh")

        if RETICULUM_AVAILABLE:
            modes.append("Reticulum Network")
        
        idx = self.show_menu("Select LoRa Mode", modes)
        
        if idx == 0:
            self.mode = "direct"
            # Restore direct LoRa settings
            if self.sx1262:
                self.sx1262.set_frequency(433920000)  # 433.92 MHz
                self.sx1262.spreading_factor = 7
                self.sx1262.tx_power = 22
            self.show_message("Mode", "Mode: Direct LoRa\n\nLoRa configured for direct TX/RX")
        elif idx == 1 and self.meshtastic:
            self.mode = "meshtastic"
            # Configure for Meshtastic
            if self.sx1262:
                mesh_config = get_meshtastic_lora_config()
                self.sx1262.set_frequency(mesh_config['frequency'])
                self.sx1262.spreading_factor = mesh_config['spreading_factor']
            self.show_message("Mode", f"Mode: Meshtastic Mesh\n\nNode: 0x{self.meshtastic.node_id:08X}\n\nLoRa configured for mesh networking")
        elif idx == 2 and RETICULUM_AVAILABLE:
            self.mode = "reticulum"
            self.show_message("Mode", "Mode: Reticulum Network")
    
    def meshtastic_chat(self):
        """Meshtastic chat interface"""
        if not self.meshtastic:
            self.show_message(
                "Meshtastic",
                "Meshtastic protocol not initialized.\n\n"
                "Check hardware configuration."
            )
            return

        # Send node info broadcast
        try:
            node_packet = self.meshtastic.send_node_info()
            encoded = self.meshtastic.encode_packet(node_packet)
            self.sx1262.transmit(encoded)

            self.show_message(
                "Meshtastic Chat",
                f"Meshtastic Mesh Ready\n\n"
                f"Node ID: 0x{self.meshtastic.node_id:08X}\n"
                f"Mode: {self.mode.upper()}\n\n"
                f"Features:\n"
                f"- Long-range mesh messaging\n"
                f"- Automatic packet routing\n"
                f"- Hop limit: 3\n"
                f"- Managed flooding algorithm\n\n"
                f"Node info broadcast sent!\n"
                f"Listen for other nodes..."
            )
        except Exception as e:
            self.show_error(f"Error: {e}")
    
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
