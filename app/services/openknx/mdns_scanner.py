import asyncio
import logging
import socket
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

from app.services.openknx.release_service import release_service, compare_semver

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredOpenKnxDevice:
    hostname: str
    ip: str
    port: int
    architecture: str
    individual_address: str = "0.0.0"
    app_id: str = ""
    firmware_name: str = ""
    firmware_version: str = ""
    serial_number: str = ""
    configured: bool = False
    update_available: bool = False
    latest_version: Optional[str] = None
    help_thread: Optional[str] = None
    discovered_via: str = "mdns"
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hostname": self.hostname,
            "ip": self.ip,
            "port": self.port,
            "architecture": self.architecture,
            "individual_address": self.individual_address,
            "app_id": self.app_id,
            "firmware_name": self.firmware_name,
            "firmware_version": self.firmware_version,
            "serial_number": self.serial_number,
            "configured": self.configured,
            "update_available": self.update_available,
            "latest_version": self.latest_version,
            "help_thread": self.help_thread,
            "discovered_via": self.discovered_via,
            "last_seen": self.last_seen
        }


if ZEROCONF_AVAILABLE:
    class OpenKnxListener(ServiceListener):
        def __init__(self, devices_dict: Dict[str, DiscoveredOpenKnxDevice]):
            self.devices = devices_dict

        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            info = zc.get_service_info(type_, name)
            if not info:
                return

            addresses = info.parsed_scoped_addresses()
            ip_str = addresses[0] if addresses else "127.0.0.1"
            port = info.port or 2040

            arch = "RP2040"
            if port == 3232:
                arch = "ESP32"
            elif port == 2040:
                arch = "RP2040"
            else:
                arch = "Unknown"

            txt = {}
            if info.properties:
                for k, v in info.properties.items():
                    k_str = k.decode("utf-8", errors="ignore") if isinstance(k, bytes) else str(k)
                    v_str = v.decode("utf-8", errors="ignore") if isinstance(v, bytes) else str(v)
                    txt[k_str] = v_str

            configured = txt.get("configured") == "1"
            address = txt.get("address", "0.0.0")
            app_id = txt.get("firmware", "").upper()
            version = txt.get("version", "")
            serial = txt.get("serial", "")
            if not serial:
                serial = f"{ip_str}:{port}"

            dev = DiscoveredOpenKnxDevice(
                hostname=info.server or name.split(".")[0],
                ip=ip_str,
                port=port,
                architecture=arch,
                individual_address=address,
                app_id=app_id,
                firmware_version=version,
                serial_number=serial,
                configured=configured,
                discovered_via="mdns"
            )
            self.devices[serial] = dev

        def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            self.add_service(zc, type_, name)

        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            pass


class MdnsScanner:
    def __init__(self):
        self._cached_devices: Dict[str, DiscoveredOpenKnxDevice] = {}

    async def scan(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        """Scans local network for OpenKNX mDNS services and enriches device data with update checks."""
        discovered: Dict[str, DiscoveredOpenKnxDevice] = {}

        if ZEROCONF_AVAILABLE:
            zc = Zeroconf()
            listener = OpenKnxListener(discovered)
            browser = ServiceBrowser(zc, "_openknx._tcp.local.", listener)
            await asyncio.sleep(timeout)
            zc.close()
        else:
            logger.warning("zeroconf ist nicht verfügbar; mDNS-Scan übersprungen.")

        # Update cache
        for k, v in discovered.items():
            self._cached_devices[k] = v

        # Enrich with GitHub release data & check for updates
        app_mappings = await release_service.get_app_mappings()
        result = []

        for serial, dev in list(self._cached_devices.items()):
            if dev.app_id:
                meta = app_mappings.get(dev.app_id)
                if meta:
                    dev.firmware_name = meta.get("repository") or dev.app_id
                    dev.help_thread = meta.get("help_thread")
                
                latest_ver = await release_service.get_latest_version_for_app(dev.app_id)
                if latest_ver:
                    dev.latest_version = latest_ver
                    if dev.firmware_version and compare_semver(latest_ver, dev.firmware_version) > 0:
                        dev.update_available = True
                    else:
                        dev.update_available = False

            result.append(dev.to_dict())

        return result

    def get_cached_devices(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._cached_devices.values()]


mdns_scanner = MdnsScanner()
