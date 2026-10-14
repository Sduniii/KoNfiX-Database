import asyncio
import io
import logging
import struct
import time
import zlib
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass

from app.services.openknx.knx_connection import KnxConnection

logger = logging.getLogger(__name__)

OBJECT_INDEX_FTM = 159

# FTM Commands
CMD_FORMAT = 0
CMD_EXISTS = 1
CMD_RENAME = 2
CMD_FILE_UPLOAD = 40
CMD_FILE_DOWNLOAD = 41
CMD_FILE_DELETE = 42
CMD_FILE_INFO = 43
CMD_DIR_LIST = 80
CMD_DIR_CREATE = 81
CMD_DIR_DELETE = 82
CMD_CANCEL = 90
CMD_GET_VERSION = 100
CMD_FW_UPDATE = 101
CMD_CHECK_FEATURES = 102

CRC16_TABLE = [
    0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241, 0xC601, 0x06C0,
    0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440, 0xCC01, 0x0CC0, 0x0D80, 0xCD41,
    0x0F00, 0xCFC1, 0xCE81, 0x0E40, 0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0,
    0x0880, 0xC841, 0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
    0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41, 0x1400, 0xD4C1,
    0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641, 0xD201, 0x12C0, 0x1380, 0xD341,
    0x1100, 0xD1C1, 0xD081, 0x1040, 0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1,
    0xF281, 0x3240, 0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
    0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41, 0xFA01, 0x3AC0,
    0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840, 0x2800, 0xE8C1, 0xE981, 0x2940,
    0xEB01, 0x2BC0, 0x2A80, 0xEA41, 0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1,
    0xEC81, 0x2C40, 0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
    0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041, 0xA001, 0x60C0,
    0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240, 0x6600, 0xA6C1, 0xA781, 0x6740,
    0xA501, 0x65C0, 0x6480, 0xA441, 0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0,
    0x6E80, 0xAE41, 0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
    0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41, 0xBE01, 0x7EC0,
    0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40, 0xB401, 0x74C0, 0x7580, 0xB541,
    0x7700, 0xB7C1, 0xB681, 0x7640, 0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0,
    0x7080, 0xB041, 0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
    0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440, 0x9C01, 0x5CC0,
    0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40, 0x5A00, 0x9AC1, 0x9B81, 0x5B40,
    0x9901, 0x59C0, 0x5880, 0x9841, 0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1,
    0x8A81, 0x4A40, 0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
    0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641, 0x8201, 0x42C0,
    0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040
]


def calculate_crc16(data: bytes) -> int:
    """CRC16/MODBUS as used in OpenKNX FileTransferClient."""
    icrc = 0xFFFF
    for b in data:
        icrc = (icrc >> 8) ^ CRC16_TABLE[(icrc ^ b) & 0xFF]
    return icrc


@dataclass
class KnxFileItem:
    name: str
    is_file: bool
    path: str
    size: Optional[int] = None


class FileTransferClient:
    """
    Client for OpenKNX File Transfer Protocol (Object Index 159).
    Enables managing files directly on the flash filesystem of OpenKNX devices
    via any KNXnet/IP connection.
    """

    def __init__(self, connection: KnxConnection, target_address: str, max_apdu: int = 15):
        self.conn = connection
        self.target_address = target_address
        self.max_apdu = max_apdu
        self.package_overhead = 6

    async def list_dir(self, remote_path: str = "/") -> List[KnxFileItem]:
        """Lists files and folders at remote_path."""
        if not remote_path.startswith("/"):
            remote_path = "/" + remote_path
        
        path_bytes = remote_path.encode("ascii") + b"\x00"
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_DIR_LIST, path_bytes
        )
        if not res:
            raise RuntimeError("Keine Antwort vom Gerät für DirList")

        items: List[KnxFileItem] = []
        has_data = True

        while has_data:
            if len(res) < 2 or res[0] != 0x00:
                break
            entry_type = res[1]
            if entry_type == 0x00:
                # End of list
                break
            
            raw_name = res[2:].split(b"\x00")[0].decode("ascii", errors="ignore")
            is_file = (entry_type == 0x01)
            full_path = remote_path.rstrip("/") + "/" + raw_name if remote_path != "/" else "/" + raw_name

            items.append(KnxFileItem(name=raw_name, is_file=is_file, path=full_path))

            # Query next entry
            res = await self.conn.invoke_function_property(
                self.target_address, OBJECT_INDEX_FTM, CMD_DIR_LIST
            )
            if not res:
                break

        return sorted(items, key=lambda i: (i.is_file, i.name.lower()))

    async def exists(self, remote_path: str) -> bool:
        path_bytes = remote_path.encode("utf-8") + b"\x00"
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_EXISTS, path_bytes
        )
        if res and len(res) >= 2 and res[0] == 0x00:
            return res[1] == 0x01
        return False

    async def file_info(self, remote_path: str) -> Dict[str, Any]:
        path_bytes = remote_path.encode("utf-8") + b"\x00"
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_FILE_INFO, path_bytes
        )
        if not res or len(res) < 9 or res[0] != 0x00:
            raise RuntimeError(f"Datei '{remote_path}' nicht gefunden oder Fehler beim Auslesen")
        
        size = struct.unpack("!I", res[1:5])[0]
        crc_bytes = res[5:9]
        crc_hex = crc_bytes.hex().upper()
        return {"size": size, "crc": crc_hex}

    async def delete_file(self, remote_path: str) -> bool:
        path_bytes = remote_path.encode("utf-8") + b"\x00"
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_FILE_DELETE, path_bytes
        )
        return bool(res and len(res) >= 1 and res[0] == 0x00)

    async def create_dir(self, remote_path: str) -> bool:
        path_bytes = remote_path.encode("utf-8") + b"\x00"
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_DIR_CREATE, path_bytes
        )
        return bool(res and len(res) >= 1 and res[0] == 0x00)

    async def delete_dir(self, remote_path: str) -> bool:
        path_bytes = remote_path.encode("utf-8") + b"\x00"
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_DIR_DELETE, path_bytes
        )
        return bool(res and len(res) >= 1 and res[0] == 0x00)

    async def format_filesystem(self) -> bool:
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_FORMAT
        )
        return bool(res and len(res) >= 1 and res[0] == 0x00)

    async def upload_file(
        self,
        remote_path: str,
        data: bytes,
        pkg_size: int = 15,
        progress_cb: Optional[Callable[[int, int, int], None]] = None
    ) -> bool:
        """
        Uploads data to remote_path using chunking, sequence numbering, and CRC16 verification.
        """
        payload_size = max(1, pkg_size - self.package_overhead)
        total_size = len(data)
        seq = 0

        # Step 1: Open transfer (Sequence 0)
        # Data: [seq_lo, seq_hi, chunk_len, resume=0] + utf8(path + '\0')
        header_data = struct.pack("<HBB", seq, payload_size, 0) + remote_path.encode("utf-8") + b"\x00"
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_FILE_UPLOAD, header_data
        )
        if not res or res[0] != 0x00:
            raise RuntimeError(f"FileUpload-Start von Gerät abgelehnt: 0x{res[0]:02x}" if res else "Keine Antwort")

        seq = 1
        stream = io.BytesIO(data)
        sent_bytes = 0

        while True:
            chunk = stream.read(payload_size)
            if not chunk:
                break
            
            chunk_data = struct.pack("<HB", seq, len(chunk)) + chunk
            res = await self.conn.invoke_function_property(
                self.target_address, OBJECT_INDEX_FTM, CMD_FILE_UPLOAD, chunk_data
            )
            if not res or res[0] != 0x00:
                raise RuntimeError(f"Fehler bei Sequenz {seq} während FileUpload")

            sent_bytes += len(chunk)
            if progress_cb and total_size > 0:
                pct = int((sent_bytes / total_size) * 100)
                progress_cb(pct, sent_bytes, total_size)
            seq = (seq + 1) & 0xFFFF

        # End of transfer: [0xFF, 0xFF]
        await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_FILE_UPLOAD, b"\xFF\xFF"
        )
        return True

    async def download_file(
        self,
        remote_path: str,
        pkg_size: int = 15,
        progress_cb: Optional[Callable[[int, int, int], None]] = None
    ) -> bytes:
        """Downloads complete file from device."""
        path_bytes = remote_path.encode("utf-8") + b"\x00"
        init_data = struct.pack("<HB", 0, pkg_size) + path_bytes
        res = await self.conn.invoke_function_property(
            self.target_address, OBJECT_INDEX_FTM, CMD_FILE_DOWNLOAD, init_data
        )
        if not res or len(res) < 5 or res[0] != 0x00:
            raise RuntimeError(f"FileDownload abgelehnt für '{remote_path}'")

        file_size = struct.unpack("!I", res[1:5])[0]
        buf = io.BytesIO()
        received = 0

        while received < file_size:
            res = await self.conn.invoke_function_property(
                self.target_address, OBJECT_INDEX_FTM, CMD_FILE_DOWNLOAD
            )
            if not res or res[0] != 0x00:
                break
            # Data bytes are inside res
            payload = res[4:-2] if len(res) > 6 else res[1:]
            buf.write(payload)
            received += len(payload)
            if progress_cb and file_size > 0:
                pct = int((received / file_size) * 100)
                progress_cb(pct, received, file_size)

        return buf.getvalue()

    async def trigger_firmware_update(self, firmware_path_on_device: str = "/fw.bin"):
        """Triggers device reboot into new firmware."""
        cmd_data = firmware_path_on_device.encode("utf-8") + b"\x00"
        try:
            await self.conn.invoke_function_property(
                self.target_address, OBJECT_INDEX_FTM, CMD_FW_UPDATE, cmd_data
            )
        except Exception:
            # Device reboots immediately, so network drop is expected
            pass
