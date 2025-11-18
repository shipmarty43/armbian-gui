"""
Meshtastic Protocol Implementation for Python
Direct mesh networking using SX1262 LoRa chip

Based on Meshtastic protocol specification:
- Protocol Buffers for packet structure
- Managed Flooding mesh algorithm
- LoRa modulation parameters
"""

import time
import struct
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import IntEnum
import random


class PortNum(IntEnum):
    """Meshtastic port numbers"""
    UNKNOWN_APP = 0
    TEXT_MESSAGE_APP = 1
    REMOTE_HARDWARE_APP = 2
    POSITION_APP = 3
    NODEINFO_APP = 4
    ROUTING_APP = 5
    ADMIN_APP = 6
    TEXT_MESSAGE_COMPRESSED_APP = 7
    WAYPOINT_APP = 8
    AUDIO_APP = 9
    DETECTION_SENSOR_APP = 10
    REPLY_APP = 32
    IP_TUNNEL_APP = 33
    PAXCOUNTER_APP = 34
    SERIAL_APP = 35
    STORE_FORWARD_APP = 36
    RANGE_TEST_APP = 37
    TELEMETRY_APP = 38
    ZPS_APP = 39
    SIMULATOR_APP = 40
    TRACEROUTE_APP = 41
    PRIVATE_APP = 256


@dataclass
class MeshPacket:
    """Meshtastic mesh packet structure"""
    # Header
    to: int  # Destination node ID
    from_node: int  # Source node ID
    id: int  # Packet ID
    hop_limit: int = 3  # Max hops
    want_ack: bool = False
    
    # Payload
    port_num: int = PortNum.TEXT_MESSAGE_APP
    payload: bytes = b''
    
    # Routing
    rx_time: int = 0
    rx_snr: float = 0.0
    rx_rssi: int = 0
    hop_start: int = 0


class MeshtasticProtocol:
    """
    Meshtastic protocol implementation.
    
    Implements:
    - Packet encoding/decoding
    - Mesh flooding algorithm
    - Message routing
    - Node management
    """
    
    # Protocol constants
    BROADCAST_ADDR = 0xFFFFFFFF
    REBROADCAST_DELAY_MS = (100, 200)  # Random delay range
    PACKET_TIMEOUT_MS = 300000  # 5 minutes
    
    def __init__(self, node_id: int = None):
        """
        Initialize Meshtastic protocol.
        
        Args:
            node_id: Node ID (random if None)
        """
        self.logger = logging.getLogger("cyberdeck.meshtastic")
        
        # Generate random node ID if not provided
        if node_id is None:
            self.node_id = random.randint(0x10000000, 0xFFFFFFFF)
        else:
            self.node_id = node_id
            
        # Packet tracking
        self.packet_id_counter = random.randint(0, 0xFFFFFFFF)
        self.seen_packets: Dict[int, float] = {}  # packet_id -> timestamp
        
        # Mesh nodes
        self.nodes: Dict[int, Dict] = {}
        
        self.logger.info(f"Meshtastic protocol initialized, Node ID: 0x{self.node_id:08X}")
    
    def encode_packet(self, packet: MeshPacket) -> bytes:
        """
        Encode MeshPacket to bytes.
        
        Format (simplified):
        - 4 bytes: to
        - 4 bytes: from
        - 4 bytes: id
        - 1 byte: flags (hop_limit, want_ack)
        - 1 byte: port_num
        - 2 bytes: payload length
        - N bytes: payload
        
        Args:
            packet: MeshPacket to encode
            
        Returns:
            bytes: Encoded packet
        """
        try:
            # Build header
            flags = (packet.hop_limit & 0x07)  # 3 bits for hop_limit
            if packet.want_ack:
                flags |= 0x08  # Bit 3 for want_ack
                
            header = struct.pack(
                '<IIIBBB',
                packet.to,
                packet.from_node,
                packet.id,
                flags,
                packet.port_num,
                len(packet.payload) & 0xFF
            )
            
            # Add payload length (2 bytes)
            length_bytes = struct.pack('<H', len(packet.payload))
            
            # Combine
            data = header + length_bytes + packet.payload
            
            # Add simple checksum
            checksum = sum(data) & 0xFF
            data += bytes([checksum])
            
            return data
            
        except Exception as e:
            self.logger.error(f"Encode error: {e}")
            return b''
    
    def decode_packet(self, data: bytes) -> Optional[MeshPacket]:
        """
        Decode bytes to MeshPacket.
        
        Args:
            data: Raw packet data
            
        Returns:
            MeshPacket or None
        """
        try:
            if len(data) < 16:  # Minimum packet size
                return None
                
            # Parse header
            to, from_node, packet_id, flags, port_num, payload_len_byte = struct.unpack(
                '<IIIBBB',
                data[:15]
            )
            
            # Parse payload length
            payload_length = struct.unpack('<H', data[15:17])[0]
            
            # Extract payload
            payload = data[17:17+payload_length]
            
            # Verify checksum
            expected_checksum = data[-1]
            actual_checksum = sum(data[:-1]) & 0xFF
            
            if expected_checksum != actual_checksum:
                self.logger.warning("Checksum mismatch")
                return None
            
            # Parse flags
            hop_limit = flags & 0x07
            want_ack = bool(flags & 0x08)
            
            # Create packet
            packet = MeshPacket(
                to=to,
                from_node=from_node,
                id=packet_id,
                hop_limit=hop_limit,
                want_ack=want_ack,
                port_num=port_num,
                payload=payload
            )
            
            return packet
            
        except Exception as e:
            self.logger.error(f"Decode error: {e}")
            return None
    
    def send_text(self, text: str, to: int = BROADCAST_ADDR) -> MeshPacket:
        """
        Send text message.
        
        Args:
            text: Message text
            to: Destination (BROADCAST_ADDR for all)
            
        Returns:
            MeshPacket: Created packet
        """
        # Create packet
        packet = MeshPacket(
            to=to,
            from_node=self.node_id,
            id=self._get_next_packet_id(),
            hop_limit=3,
            want_ack=False,
            port_num=PortNum.TEXT_MESSAGE_APP,
            payload=text.encode('utf-8')
        )
        
        # Record as seen
        self.seen_packets[packet.id] = time.time()
        
        return packet
    
    def should_rebroadcast(self, packet: MeshPacket) -> bool:
        """
        Determine if packet should be rebroadcasted (mesh flooding).
        
        Args:
            packet: Received packet
            
        Returns:
            bool: True if should rebroadcast
        """
        # Check if we've seen this packet before
        if packet.id in self.seen_packets:
            return False
            
        # Check hop limit
        if packet.hop_limit <= 0:
            return False
            
        # Check if it's for us specifically
        if packet.to == self.node_id:
            return False  # Don't rebroadcast messages to us
            
        # Broadcast or not for us - rebroadcast
        return True
    
    def process_received_packet(self, packet: MeshPacket) -> Optional[str]:
        """
        Process received packet.
        
        Args:
            packet: Received MeshPacket
            
        Returns:
            str: Decoded message if for us, None otherwise
        """
        # Record as seen
        self.seen_packets[packet.id] = time.time()
        
        # Clean old packets
        self._clean_old_packets()
        
        # Update node info
        self._update_node(packet.from_node, packet)
        
        # Check if message is for us or broadcast
        if packet.to == self.node_id or packet.to == self.BROADCAST_ADDR:
            # Decode based on port
            if packet.port_num == PortNum.TEXT_MESSAGE_APP:
                try:
                    message = packet.payload.decode('utf-8')
                    self.logger.info(f"Message from 0x{packet.from_node:08X}: {message}")
                    return message
                except:
                    return None
            elif packet.port_num == PortNum.NODEINFO_APP:
                self.logger.info(f"NodeInfo from 0x{packet.from_node:08X}")
                return None
            elif packet.port_num == PortNum.POSITION_APP:
                self.logger.info(f"Position from 0x{packet.from_node:08X}")
                return None
        
        return None
    
    def rebroadcast_packet(self, packet: MeshPacket) -> MeshPacket:
        """
        Create rebroadcast packet (decrease hop limit).
        
        Args:
            packet: Original packet
            
        Returns:
            MeshPacket: Rebroadcast packet
        """
        # Decrease hop limit
        new_packet = MeshPacket(
            to=packet.to,
            from_node=packet.from_node,
            id=packet.id,
            hop_limit=packet.hop_limit - 1,
            want_ack=packet.want_ack,
            port_num=packet.port_num,
            payload=packet.payload
        )
        
        return new_packet
    
    def send_node_info(self) -> MeshPacket:
        """
        Send node info broadcast.
        
        Returns:
            MeshPacket: NodeInfo packet
        """
        # Simple node info (could include name, hardware, etc)
        node_info = f"Node:0x{self.node_id:08X}".encode('utf-8')
        
        packet = MeshPacket(
            to=self.BROADCAST_ADDR,
            from_node=self.node_id,
            id=self._get_next_packet_id(),
            hop_limit=3,
            want_ack=False,
            port_num=PortNum.NODEINFO_APP,
            payload=node_info
        )
        
        return packet
    
    def _get_next_packet_id(self) -> int:
        """Get next packet ID"""
        self.packet_id_counter += 1
        if self.packet_id_counter > 0xFFFFFFFF:
            self.packet_id_counter = 0
        return self.packet_id_counter
    
    def _clean_old_packets(self):
        """Clean old seen packets"""
        now = time.time()
        timeout = self.PACKET_TIMEOUT_MS / 1000.0
        
        old_ids = [
            pid for pid, ts in self.seen_packets.items()
            if (now - ts) > timeout
        ]
        
        for pid in old_ids:
            del self.seen_packets[pid]
    
    def _update_node(self, node_id: int, packet: MeshPacket):
        """Update node information"""
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                'id': node_id,
                'last_seen': time.time(),
                'rssi': packet.rx_rssi,
                'snr': packet.rx_snr
            }
        else:
            self.nodes[node_id]['last_seen'] = time.time()
            self.nodes[node_id]['rssi'] = packet.rx_rssi
            self.nodes[node_id]['snr'] = packet.rx_snr
    
    def get_mesh_nodes(self) -> List[Dict]:
        """Get list of mesh nodes"""
        # Remove stale nodes (not seen in 10 minutes)
        now = time.time()
        stale_timeout = 600  # 10 minutes
        
        active_nodes = [
            node for node in self.nodes.values()
            if (now - node['last_seen']) < stale_timeout
        ]
        
        return active_nodes


def get_meshtastic_lora_config() -> Dict:
    """
    Get recommended LoRa configuration for Meshtastic.
    
    Returns:
        dict: LoRa parameters
    """
    # Meshtastic uses these LoRa parameters for long range
    return {
        'frequency': 868000000,  # 868 MHz (EU), use 915 MHz for US
        'bandwidth': 125000,  # 125 kHz
        'spreading_factor': 11,  # SF11 for long range
        'coding_rate': 8,  # 4/8
        'tx_power': 22,  # dBm
        'preamble_length': 32,
        'sync_word': 0x12,  # Private sync word
    }
