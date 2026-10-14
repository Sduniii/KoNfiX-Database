import asyncio
import logging
import socket
import struct
import time
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

KNXNET_IP_PORT = 3671
MULTICAST_ADDRESS = "224.0.23.12"

# Service Types
SEARCH_REQUEST = 0x0201
SEARCH_RESPONSE = 0x0202
DESCRIPTION_REQUEST = 0x0205
DESCRIPTION_RESPONSE = 0x0206
CONNECT_REQUEST = 0x0207
CONNECT_RESPONSE = 0x0208
CONNECTIONSTATE_REQUEST = 0x0209
CONNECTIONSTATE_RESPONSE = 0x020A
DISCONNECT_REQUEST = 0x020B
DISCONNECT_RESPONSE = 0x020C
TUNNELLING_REQUEST = 0x0420
TUNNELLING_ACK = 0x0421
ROUTING_INDICATION = 0x0530

# cEMI Message Codes
L_DATA_REQ = 0x11
L_DATA_CON = 0x2E
L_DATA_IND = 0x29


def parse_knx_address(address_str: str) -> int:
    """Parses individual KNX address 'area.line.device' (e.g. '1.1.30') to 16-bit uint."""
    parts = address_str.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"Ungültige physikalische KNX-Adresse: '{address_str}'")
    area = int(parts[0])
    line = int(parts[1])
    device = int(parts[2])
    return ((area & 0x0F) << 12) | ((line & 0x0F) << 8) | (device & 0xFF)


def format_knx_address(address_int: int) -> str:
    """Formats 16-bit uint to 'area.line.device' (e.g. '1.1.30')."""
    area = (address_int >> 12) & 0x0F
    line = (address_int >> 8) & 0x0F
    device = address_int & 0xFF
    return f"{area}.{line}.{device}"


class KnxGatewayDiscovery:
    @staticmethod
    async def discover(timeout: float = 2.5) -> List[Dict[str, Any]]:
        """
        Sends KNXnet/IP SEARCH_REQUEST via UDP multicast (224.0.23.12:3671)
        and parses incoming SEARCH_RESPONSE messages.
        """
        gateways = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(0.5)

        try:
            # Determine local outbound IP
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_sock.connect(("8.8.8.8", 80))
            local_ip = temp_sock.getsockname()[0]
            temp_sock.close()
        except Exception:
            local_ip = "127.0.0.1"

        sock.bind(("", 0))
        _, local_port = sock.getsockname()

        # Build SEARCH_REQUEST frame
        # Header: 06 10 02 01 00 0E
        # HPAI: 08 01 (UDP) + IP (4 bytes) + Port (2 bytes)
        ip_bytes = socket.inet_aton(local_ip)
        hpai = struct.pack("!BB4sH", 8, 1, ip_bytes, local_port)
        header = struct.pack("!BBHH", 6, 0x10, SEARCH_REQUEST, 6 + len(hpai))
        req_packet = header + hpai

        try:
            sock.sendto(req_packet, (MULTICAST_ADDRESS, KNXNET_IP_PORT))
        except Exception as ex:
            logger.debug("Multicast send failed, trying broadcast: %s", ex)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(req_packet, ("255.255.255.255", KNXNET_IP_PORT))
            except Exception:
                pass

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                if len(data) < 6:
                    continue
                header_len, proto_ver, service_type, total_len = struct.unpack("!BBHH", data[:6])
                if service_type == SEARCH_RESPONSE and len(data) >= 14:
                    gw_ip = addr[0]
                    # Parse HPAI
                    hpai_len, proto, ctrl_ip, ctrl_port = struct.unpack("!BB4sH", data[6:14])
                    ctrl_ip_str = socket.inet_ntoa(ctrl_ip)
                    
                    # Parse DIBs (Device Information Block)
                    offset = 6 + hpai_len
                    friendly_name = f"KNX Gateway ({gw_ip})"
                    knx_addr_str = "0.0.0"
                    mac_str = ""

                    while offset < len(data):
                        dib_len = data[offset]
                        if dib_len == 0 or offset + dib_len > len(data):
                            break
                        dib_type = data[offset + 1]
                        if dib_type == 0x01:  # Device Info
                            if dib_len >= 0x36:
                                knx_addr_raw = struct.unpack("!H", data[offset + 4:offset + 6])[0]
                                knx_addr_str = format_knx_address(knx_addr_raw)
                                mac_bytes = data[offset + 12:offset + 18]
                                mac_str = ":".join(f"{b:02x}" for b in mac_bytes)
                                raw_name = data[offset + 18:offset + 48]
                                friendly_name = raw_name.split(b"\x00")[0].decode("latin-1", errors="ignore").strip()
                        offset += dib_len

                    gateways.append({
                        "name": friendly_name or f"KNX Gateway ({gw_ip})",
                        "host": gw_ip,
                        "port": ctrl_port or KNXNET_IP_PORT,
                        "individual_address": knx_addr_str,
                        "mac": mac_str,
                        "protocol": "tunneling_udp"
                    })
            except socket.timeout:
                await asyncio.sleep(0.05)
            except Exception as ex:
                logger.debug("Fehler beim Empfang von SEARCH_RESPONSE: %s", ex)
                break

        sock.close()
        # Deduplicate by host
        unique = {}
        for g in gateways:
            unique[g["host"]] = g
        return list(unique.values())


class KnxConnection:
    """
    Asynchronous KNXnet/IP Tunneling & Routing Client.
    Supports point-to-point connections, property read/write,
    FunctionProperty execution (FTM Object 159), and restart.
    """

    def __init__(self, host: str, port: int = KNXNET_IP_PORT, protocol: str = "tunneling_udp"):
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
        self.channel_id: Optional[int] = None
        self.sequence_number = 0
        self.individual_address = 0
        self._sock: Optional[socket.socket] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_connected = False
        self._pending_responses: Dict[int, asyncio.Future] = {}
        self._listen_task: Optional[asyncio.Task] = None

    async def connect(self):
        if self._is_connected:
            return

        self._loop = asyncio.get_running_loop()

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock.bind(("", 0))
        _, local_port = self._sock.getsockname()

        # Find local outbound IP
        try:
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_sock.connect((self.host, self.port))
            local_ip = temp_sock.getsockname()[0]
            temp_sock.close()
        except Exception:
            local_ip = "127.0.0.1"

        local_ip_bytes = socket.inet_aton(local_ip)

        # Build CONNECT_REQUEST
        # HPAI Control (8 bytes) + HPAI Data (8 bytes) + CRI Tunneling LinkLayer (4 bytes)
        hpai_ctrl = struct.pack("!BB4sH", 8, 1, local_ip_bytes, local_port)
        hpai_data = struct.pack("!BB4sH", 8, 1, local_ip_bytes, local_port)
        cri = struct.pack("!BBBx", 4, 0x04, 0x02)  # Tunneling, Tunnel_Link_Layer
        body = hpai_ctrl + hpai_data + cri
        header = struct.pack("!BBHH", 6, 0x10, CONNECT_REQUEST, 6 + len(body))

        self._sock.sendto(header + body, (self.host, self.port))

        # Wait for CONNECT_RESPONSE
        start = time.time()
        while time.time() - start < 3.0:
            try:
                data = await self._loop.sock_recv(self._sock, 1024)
                if len(data) >= 8:
                    _, _, s_type, _ = struct.unpack("!BBHH", data[:6])
                    if s_type == CONNECT_RESPONSE:
                        self.channel_id = data[6]
                        status = data[7]
                        if status == 0x00:
                            self._is_connected = True
                            if len(data) >= 18:
                                # CRD assigned address
                                self.individual_address = struct.unpack("!H", data[16:18])[0]
                            break
                        else:
                            raise ConnectionError(f"KNXnet/IP Connect abgewiesen mit Status: 0x{status:02x}")
            except Exception:
                await asyncio.sleep(0.05)

        if not self._is_connected:
            raise ConnectionError(f"Keine Antwort vom KNX Gateway {self.host}:{self.port}")

        self._listen_task = asyncio.create_task(self._listen_loop())

    async def disconnect(self):
        if not self._is_connected or not self._sock or self.channel_id is None:
            return

        try:
            # Build DISCONNECT_REQUEST
            hpai = struct.pack("!BB4sH", 8, 1, b"\x00\x00\x00\x00", 0)
            body = bytes([self.channel_id, 0x00]) + hpai
            header = struct.pack("!BBHH", 6, 0x10, DISCONNECT_REQUEST, 6 + len(body))
            self._sock.sendto(header + body, (self.host, self.port))
        except Exception:
            pass
        finally:
            self._is_connected = False
            if self._listen_task:
                self._listen_task.cancel()
            if self._sock:
                self._sock.close()
                self._sock = None

    async def _listen_loop(self):
        """Background listener for incoming TUNNELLING_REQUEST (confirmations and indications)."""
        while self._is_connected and self._sock:
            try:
                data = await self._loop.sock_recv(self._sock, 2048)
                if len(data) < 6:
                    continue
                _, _, s_type, _ = struct.unpack("!BBHH", data[:6])

                if s_type == TUNNELLING_REQUEST and len(data) >= 10:
                    ch_id = data[6]
                    seq_num = data[7]
                    # Send TUNNELLING_ACK immediately
                    ack_body = struct.pack("!BBBx", 4, ch_id, seq_num)
                    ack_header = struct.pack("!BBHH", 6, 0x10, TUNNELLING_ACK, 6 + len(ack_body))
                    self._sock.sendto(ack_header + ack_body, (self.host, self.port))

                    # Parse cEMI frame
                    cemi = data[10:]
                    if len(cemi) >= 10:
                        msg_code = cemi[0]
                        # Source and Target address
                        dest_addr = struct.unpack("!H", cemi[6:8])[0]
                        apdu_len = cemi[8]
                        apdu = cemi[9:9 + apdu_len + 1]
                        
                        # Match any waiting futures
                        for key, fut in list(self._pending_responses.items()):
                            if not fut.done():
                                fut.set_result(apdu)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.debug("Listen loop exception: %s", ex)
                await asyncio.sleep(0.05)

    async def send_tunnel_request(self, cemi_frame: bytes, timeout: float = 3.0) -> bytes:
        if not self._is_connected or not self._sock or self.channel_id is None:
            raise ConnectionError("Nicht mit dem KNX-Gateway verbunden")

        seq = self.sequence_number
        self.sequence_number = (self.sequence_number + 1) & 0xFF

        conn_header = struct.pack("!BBBB", 4, self.channel_id, seq, 0)
        total_len = 6 + len(conn_header) + len(cemi_frame)
        header = struct.pack("!BBHH", 6, 0x10, TUNNELLING_REQUEST, total_len)
        packet = header + conn_header + cemi_frame

        loop = self._loop or asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending_responses[seq] = fut

        self._sock.sendto(packet, (self.host, self.port))

        try:
            res = await asyncio.wait_for(fut, timeout=timeout)
            return res
        finally:
            self._pending_responses.pop(seq, None)

    # --------------------------------------------------------------------------
    # Higher Level KNX Management & Property Operations
    # --------------------------------------------------------------------------
    def _build_cemi_l_data_req(self, target_addr: int, apdu: bytes) -> bytes:
        """Builds standard cEMI L_Data.req frame."""
        ctrl1 = 0xBC  # standard priority, repeat flag
        ctrl2 = 0x60  # standard hop count 6, unicast target
        source = 0x0000
        length = len(apdu) - 1
        return struct.pack("!BBBBHH", L_DATA_REQ, 0, ctrl1, ctrl2, source, target_addr) + bytes([length]) + apdu

    async def connect_individual(self, target_address: str, timeout: float = 3.0):
        """Establishes point-to-point connection (U_Connect)."""
        target_int = parse_knx_address(target_address)
        # U_Connect APDU: TPCI = 0x80 (connect)
        apdu = bytes([0x80])
        cemi = self._build_cemi_l_data_req(target_int, apdu)
        try:
            await self.send_tunnel_request(cemi, timeout=timeout)
        except Exception:
            pass

    async def disconnect_individual(self, target_address: str):
        """Disconnects point-to-point connection (U_Disconnect)."""
        target_int = parse_knx_address(target_address)
        apdu = bytes([0x81])
        cemi = self._build_cemi_l_data_req(target_int, apdu)
        try:
            await self.send_tunnel_request(cemi, timeout=1.5)
        except Exception:
            pass

    async def property_read(self, target_address: str, obj_idx: int, prop_id: int, count: int = 1, start_idx: int = 1) -> bytes:
        """
        Reads a KNX property from an object on the target device (A_PropertyValue_Read).
        Used to query PID 78 (AppId) and PID 25 (Firmware Version).
        """
        target_int = parse_knx_address(target_address)
        # APCI: 0x03D5 (A_PropertyValue_Read)
        # TPCI = 0x40 (numbered or unnumbered)
        apci_hi = 0x03
        apci_lo = 0xD5
        hi = ((apci_hi & 0x03) << 2) | ((count >> 4) & 0x0F)
        lo = (start_idx & 0x0FFF)
        apdu = bytes([0x40, apci_lo, obj_idx, prop_id]) + struct.pack("!H", ((count & 0x0F) << 12) | lo)
        cemi = self._build_cemi_l_data_req(target_int, apdu)
        resp = await self.send_tunnel_request(cemi, timeout=2.5)
        # Return data bytes from response
        if len(resp) >= 6:
            return resp[6:]
        return resp

    async def restart_device(self, target_address: str):
        """Sends remote restart telegram (A_Restart) to target device."""
        target_int = parse_knx_address(target_address)
        # A_Restart APCI: 0x0380
        apdu = bytes([0x40, 0x80])
        cemi = self._build_cemi_l_data_req(target_int, apdu)
        await self.send_tunnel_request(cemi, timeout=2.0)

    async def invoke_function_property(self, target_address: str, obj_idx: int, prop_id: int, data: bytes = b"") -> bytes:
        """
        Invokes a function property on the device (used for KNX File Transfer Object 159).
        """
        target_int = parse_knx_address(target_address)
        # FunctionPropertyCommand: APCI 0x03D7
        apdu = bytes([0x40, 0xD7, obj_idx, prop_id]) + data
        cemi = self._build_cemi_l_data_req(target_int, apdu)
        resp = await self.send_tunnel_request(cemi, timeout=5.0)
        if len(resp) >= 4:
            return resp[4:]
        return resp
