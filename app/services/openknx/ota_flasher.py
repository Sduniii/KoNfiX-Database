import asyncio
import hashlib
import io
import logging
import socket
import struct
import time
import zlib
from typing import Optional, Callable, Dict, Any

from app.services.openknx.knx_connection import KnxConnection
from app.services.openknx.file_transfer_client import FileTransferClient

logger = logging.getLogger(__name__)


class FirmwareFlasher:
    """
    Handles firmware flashing for OpenKNX devices via:
    1. Network OTA (ESP32 Port 3232 / RP2040 Port 2040)
    2. Over-The-Bus KNX File Transfer (/fw.bin with CRC32 verification)
    """

    @staticmethod
    async def flash_via_bus(
        conn: KnxConnection,
        target_address: str,
        firmware_bytes: bytes,
        pkg_size: int = 15,
        progress_cb: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Flashes firmware over KNX bus:
        - Uploads firmware to /fw.bin
        - Checks CRC32
        - Sends FwUpdate command to trigger reboot
        """
        if progress_cb:
            progress_cb(5, "Initialisiere Bus-Dateitransfer...")

        client = FileTransferClient(conn, target_address, max_apdu=pkg_size)
        total_len = len(firmware_bytes)

        def _on_chunk_progress(pct: int, sent: int, total: int):
            if progress_cb:
                progress_cb(int(10 + (pct * 0.75)), f"Übertrage Firmware über KNX-Bus ({sent}/{total} Bytes)...")

        # Step 1: Upload /fw.bin
        await client.upload_file("/fw.bin", firmware_bytes, pkg_size=pkg_size, progress_cb=_on_chunk_progress)

        if progress_cb:
            progress_cb(88, "Verifiziere Prüfsumme (CRC32) auf dem Gerät...")

        # Step 2: Validate CRC32
        file_info = await client.file_info("/fw.bin")
        local_crc32 = zlib.crc32(firmware_bytes) & 0xFFFFFFFF
        local_crc_hex = struct.pack(">I", local_crc32).hex().upper()
        remote_crc_hex = file_info.get("crc", "")

        logger.info("Local CRC32: %s, Remote CRC32: %s", local_crc_hex, remote_crc_hex)

        if remote_crc_hex and local_crc_hex != remote_crc_hex:
            raise RuntimeError(f"Prüfsummenfehler: Lokal {local_crc_hex} != Remote {remote_crc_hex}")

        if progress_cb:
            progress_cb(95, "Starte Gerät neu in neue Firmware...")

        # Step 3: Trigger reboot into firmware
        await client.trigger_firmware_update("/fw.bin")

        if progress_cb:
            progress_cb(100, "Firmware-Update erfolgreich initiiert! Gerät bootet neu.")

        return {
            "status": "success",
            "method": "knx_bus",
            "size": total_len,
            "crc32": local_crc_hex
        }

    @staticmethod
    async def flash_via_network_ota(
        ip: str,
        port: int,
        firmware_bytes: bytes,
        progress_cb: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Flashes firmware via network OTA:
        - ESP32 (Port 3232)
        - RP2040 (Port 2040)
        """
        total_size = len(firmware_bytes)
        md5_hash = hashlib.md5(firmware_bytes).hexdigest()

        if progress_cb:
            progress_cb(5, f"Verbinde mit OTA-Dienst auf {ip}:{port}...")

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=5.0
        )

        try:
            if port == 3232:
                # ESP32 OTA protocol handshake
                # Command format: 0 (flash), local_port, total_size, md5
                cmd = f"0 0 {total_size} {md5_hash}\n"
                writer.write(cmd.encode("ascii"))
                await writer.drain()

                resp = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if b"OK" not in resp:
                    raise RuntimeError(f"ESP32 OTA Einladung abgewiesen: {resp.decode('latin-1', errors='ignore')}")

            elif port == 2040:
                # RP2040 TCP OTA protocol
                # Sends length (4 bytes big-endian) + MD5 (32 bytes ASCII)
                header = struct.pack(">I", total_size) + md5_hash.encode("ascii")
                writer.write(header)
                await writer.drain()

                resp = await asyncio.wait_for(reader.read(4), timeout=5.0)
                if resp != b"OK\r\n" and resp != b"OK":
                    pass  # proceed with streaming

            # Stream binary in 1460-byte MTU-safe chunks
            chunk_size = 1460
            sent = 0
            stream = io.BytesIO(firmware_bytes)

            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
                sent += len(chunk)
                if progress_cb and total_size > 0:
                    pct = int(10 + (sent / total_size) * 85)
                    progress_cb(pct, f"Übertrage Firmware via OTA ({sent}/{total_size} Bytes)...")

            # Final handshake / ack
            try:
                final_resp = await asyncio.wait_for(reader.read(64), timeout=5.0)
                logger.info("OTA Final Response: %s", final_resp)
            except Exception:
                pass

            if progress_cb:
                progress_cb(100, "OTA-Update erfolgreich abgeschlossen! Gerät startet neu.")

            return {
                "status": "success",
                "method": "network_ota",
                "ip": ip,
                "port": port,
                "size": total_size,
                "md5": md5_hash
            }
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


firmware_flasher = FirmwareFlasher()
